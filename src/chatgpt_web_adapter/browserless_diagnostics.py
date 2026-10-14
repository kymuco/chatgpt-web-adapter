"""Browser-free, read/preflight-only diagnostics; never claims inference success."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .auth import CHAT_URL
from .browserless_request_transport_core import _strip_ephemeral_write_headers
from .client import ChatGPTWebClient
from .sentinel_requirements import (
    SENTINEL_PREPARE_PATH,
    build_sentinel_prepare_headers,
)
from .web_session import _sync_device_header, suppress_web_session_debug_trace


def _config_string(value: str) -> str:
    if any(char in value for char in "\r\n\0"):
        raise ValueError("curl configuration values cannot contain control lines")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def connection_samples(client: Any, *, samples: int = 5) -> list[dict[str, Any]]:
    """Use one curl process to distinguish fresh connections from actual reuse.

    Credentials travel through stdin, not command arguments. Response bodies and
    curl's extended metadata are discarded; only timing/status fields survive.
    """
    if not 1 <= samples <= 20:
        raise ValueError("samples must be between 1 and 20")
    config = ["silent", "show-error", 'max-time = "20"', 'write-out = "%{json}\\n"']
    headers = _strip_ephemeral_write_headers(client._build_headers())
    for name, value in headers.items():
        config.append("header = " + _config_string(f"{name}: {value}"))
    for _ in range(samples):
        config.extend(
            [
                'url = "https://chatgpt.com/backend-api/models"',
                "output = " + _config_string(os.devnull),
            ]
        )
    result = subprocess.run(
        [client.curl_bin, "--config", "-"],
        input="\n".join(config),
        capture_output=True,
        text=True,
        timeout=20 * samples + 5,
    )
    fields = (
        "http_code",
        "http_version",
        "num_connects",
        "time_namelookup",
        "time_connect",
        "time_appconnect",
        "time_pretransfer",
        "time_starttransfer",
        "time_total",
        "exitcode",
    )
    rows = []
    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        row = {key: data.get(key) for key in fields}
        row["connection_reused"] = data.get("num_connects") == 0
        rows.append(row)
    if result.returncode or len(rows) != samples:
        # stderr and arbitrary server responses must never enter diagnostics.
        raise RuntimeError("connection timing probe failed or returned incomplete data")
    return rows


def inspect_client(client: Any, *, samples: int = 5) -> dict[str, Any]:
    """Inspect a dedicated client. Does not attach or send to conversations."""
    if not 1 <= samples <= 20:
        raise ValueError("samples must be between 1 and 20")
    client.base_headers = _strip_ephemeral_write_headers(client.base_headers)
    _sync_device_header(client)
    report: dict[str, Any] = {
        "schema": 1,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "browser_started": False,
        "conversation_write_attempts": 0,
        "inference_verified": False,
        "ttft_seconds": None,
    }
    with suppress_web_session_debug_trace():
        start = perf_counter()
        status, data = client._json_request(
            "GET", f"{CHAT_URL}backend-api/models", None, client._build_headers()
        )
        models = data.get("models", []) if isinstance(data, dict) else []
        report["catalogue"] = {
            "status_code": status,
            "elapsed_seconds": perf_counter() - start,
            "default_model_slug": data.get("default_model_slug")
            if isinstance(data, dict)
            else None,
            "models": [
                {key: item.get(key) for key in ("slug", "title", "max_tokens")}
                for item in models
                if isinstance(item, dict)
            ]
            if isinstance(models, list)
            else [],
            "note": "Catalogue presence does not prove inference access or model selection.",
        }
        start = perf_counter()
        status, data = client._json_request(
            "POST",
            f"{CHAT_URL.rstrip('/')}{SENTINEL_PREPARE_PATH}",
            {"p": None},
            build_sentinel_prepare_headers(client),
        )
        payload = data if isinstance(data, dict) else {}
        report["sentinel_prepare"] = {
            "status_code": status,
            "elapsed_seconds": perf_counter() - start,
            "prepare_token_present": bool(payload.get("prepare_token")),
            "required": {
                key: payload[key].get("required")
                if isinstance(payload.get(key), dict)
                else None
                for key in ("proofofwork", "turnstile", "so")
            },
            "prepare_input": "null (existing strict transport)",
        }
        report["connection_samples"] = connection_samples(client, samples=samples)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.samples <= 20:
        parser.error("--samples must be between 1 and 20")
    try:
        client = ChatGPTWebClient(
            auth_file=args.auth_file,
            auto_login=False,
            auto_sentinel=False,
            auto_refresh_auth=False,
            persist_refreshed_auth=False,
            timeout=20,
        )
        report = inspect_client(client, samples=args.samples)
    except Exception as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__}))
        return 1
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
