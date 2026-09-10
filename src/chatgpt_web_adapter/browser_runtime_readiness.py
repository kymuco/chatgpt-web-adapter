"""Deterministic CWA browser runtime readiness gate (pre-write, read-only).

Proves the EXACT deployed service-worker identity before any protected write
without using a live review request as a version probe:

- bridge liveness: the native host reports the extension connected;
- load sentinel: ``cwaSseConversationIdentityLoadedV1`` (written by the
  request-bound SSE identity authority module when it is imported by the
  running service worker) must exist in the profile's
  ``Local Extension Settings`` storage and carry the expected bundle tag;
- freshness: the sentinel's ``loadedAtMs`` must be >= the newest mtime of the
  extension source files. Chrome can otherwise keep serving a stale
  ``Service Worker/ScriptCache`` snapshot across browser restarts (proven
  root cause of pre-authority behavior).

``repair_stale_runtime`` is a TARGETED deterministic repair, never a blind
global cleanup: it runs only when the sentinel proves the runtime is STALE
(source newer than last SW load), stops only the Chrome instance that owns
the given profile, deletes only ``<profile>/Service Worker``, relaunches with
the SAME captured command line, then re-reads the identity.

CLI: ``python runtime_readiness.py --user-data DIR --profile "Profile 1"
--extension-id ID [--bundle TAG] [--repair]`` -> JSON; exit 0 ready, 5 not.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SSE_SENTINEL_KEY = "cwaSseConversationIdentityLoadedV1"
EXPECTED_BUNDLE = "worktree-cwa-main-test"
_EXTENSION_SOURCE_DIR = Path(__file__).resolve().parent / "browser_native_extension"


def _extension_storage_dir(user_data: Path, profile: str, extension_id: str) -> Path:
    return user_data / profile / "Local Extension Settings" / extension_id


def read_sentinel(
    *, user_data: str, profile: str, extension_id: str, key: str = SSE_SENTINEL_KEY
) -> dict[str, Any] | None:
    """Return the newest sentinel record {loadedAtMs, bundle} or None."""
    storage = _extension_storage_dir(Path(user_data), profile, extension_id)
    if not storage.is_dir():
        return None
    newest: dict[str, Any] | None = None
    for log in sorted(storage.glob("*.log")):
        try:
            data = log.read_bytes()
        except OSError:
            # Chrome holds the log open; share-read like the LevelDB reader.
            try:
                with open(log, "rb") as handle:
                    data = handle.read()
            except OSError:
                continue
        text = data.decode("latin-1", errors="replace")
        for match in re.finditer(re.escape(key), text):
            window = text[match.end() : match.end() + 400]
            at = re.search(r"(?:loadedAtMs|at)[\"\\:. ]{0,8}(\d{13})", window)
            if not at:
                continue
            bundle = re.search(r"bundle[\"\\:. ]{0,8}([A-Za-z0-9._-]{1,64})", window)
            record = {
                "loadedAtMs": int(at.group(1)),
                "bundle": bundle.group(1) if bundle else None,
            }
            if newest is None or record["loadedAtMs"] >= newest["loadedAtMs"]:
                newest = record
    return newest


def newest_source_mtime_ms(source_dir: Path = _EXTENSION_SOURCE_DIR) -> int:
    newest = 0
    for f in source_dir.glob("*.js"):
        try:
            newest = max(newest, int(f.stat().st_mtime * 1000))
        except OSError:
            continue
    return newest


def bridge_connected() -> bool:
    try:
        from .browser_native_provider import BrowserNativeTurnProvider

        status = BrowserNativeTurnProvider().status()
    except Exception:  # noqa: BLE001 - probe boundary
        return False
    return bool(status.available and status.extension_connected)


def check_readiness(
    *,
    user_data: str,
    profile: str,
    extension_id: str,
    bundle: str = EXPECTED_BUNDLE,
    source_dir: Path = _EXTENSION_SOURCE_DIR,
) -> dict[str, Any]:
    reasons: list[str] = []
    connected = bridge_connected()
    if not connected:
        reasons.append("CWA_BRIDGE_NOT_CONNECTED")
    sentinel = read_sentinel(
        user_data=user_data, profile=profile, extension_id=extension_id
    )
    if sentinel is None:
        reasons.append("CWA_SENTINEL_MISSING")
    newest_source_ms = newest_source_mtime_ms(source_dir)
    stale = bool(
        sentinel is not None and sentinel["loadedAtMs"] < newest_source_ms
    )
    if stale:
        reasons.append("CWA_SENTINEL_STALE")
    if sentinel is not None and sentinel.get("bundle") != bundle:
        reasons.append("CWA_BUNDLE_MISMATCH")
    return {
        "ready": not reasons,
        "reasons": reasons,
        "extensionConnected": connected,
        "sentinel": sentinel,
        "newestSourceMtimeMs": newest_source_ms,
        "expectedBundle": bundle,
    }


def _stale_chrome_processes(user_data: str) -> list[int]:
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -notmatch '--type=' -and "
        "$_.CommandLine -match [regex]::Escape($env:CWA_USER_DATA) } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    import os

    env = dict(os.environ, CWA_USER_DATA=user_data)
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return [int(line) for line in out.stdout.split() if line.strip().isdigit()]


def repair_stale_runtime(
    *, user_data: str, profile: str, extension_id: str, timeout_s: float = 40.0
) -> dict[str, Any]:
    """Targeted deterministic reload; caller MUST first observe
    CWA_SENTINEL_STALE. Never invoked on unproven staleness."""
    before = check_readiness(
        user_data=user_data, profile=profile, extension_id=extension_id
    )
    if "CWA_SENTINEL_STALE" not in before["reasons"]:
        return {"repaired": False, "reason": "CWA_REPAIR_REQUIRES_STALE_PROOF", "before": before}
    pids = _stale_chrome_processes(user_data)
    if not pids:
        return {"repaired": False, "reason": "CWA_REPAIR_NO_OWNER_PROCESS", "before": before}
    cmd_script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -notmatch '--type=' } | "
        "Select-Object -ExpandProperty CommandLine -First 1"
    )
    launch_line = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd_script],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip().strip('"')
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    time.sleep(3)
    sw_dir = Path(user_data) / profile / "Service Worker"
    import shutil

    if sw_dir.is_dir():
        shutil.rmtree(sw_dir, ignore_errors=True)
    if launch_line:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", f"Start-Process {launch_line}"],
            shell=False,
        )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(2)
        after = check_readiness(
            user_data=user_data, profile=profile, extension_id=extension_id
        )
        if after["ready"]:
            return {"repaired": True, "before": before, "after": after}
    after = check_readiness(
        user_data=user_data, profile=profile, extension_id=extension_id
    )
    return {"repaired": False, "reason": "CWA_REPAIR_NOT_READY", "before": before, "after": after}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cwa-runtime-readiness")
    parser.add_argument("--user-data", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--extension-id", required=True)
    parser.add_argument("--bundle", default=EXPECTED_BUNDLE)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args(argv)
    report = check_readiness(
        user_data=args.user_data,
        profile=args.profile,
        extension_id=args.extension_id,
        bundle=args.bundle,
    )
    if not report["ready"] and args.repair and "CWA_SENTINEL_STALE" in report["reasons"]:
        report["repair"] = repair_stale_runtime(
            user_data=args.user_data, profile=args.profile, extension_id=args.extension_id
        )
        report = report["repair"].get("after", report)
    print(json.dumps(report, ensure_ascii=False, default=str))
    return 0 if report["ready"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
