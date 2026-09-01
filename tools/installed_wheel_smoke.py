from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PROJECT_NAME = "chatgpt-web-adapter"
EXPECTED_ENTRY_POINTS = {
    "cwa": "chatgpt_web_adapter.cli_v02:main",
    "chatgpt-web-adapter": "chatgpt_web_adapter.cli_v02:main",
    "chatgpt-web-adapter-native-host": "chatgpt_web_adapter.browser_native_host:main",
}
HELP_COMMANDS = (
    ("cwa", "--help"),
    ("chatgpt-web-adapter", "--help"),
    ("cwa", "doctor", "--help"),
    ("cwa", "status", "--help"),
    ("cwa", "capabilities", "--help"),
    ("cwa", "messages", "--help"),
    ("cwa", "snapshot", "--help"),
    ("cwa", "export", "--help"),
    ("cwa", "send", "--help"),
)
_VERSION_RE = re.compile(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
_PROJECT_RE = re.compile(r"^\[project\]\s*$([\s\S]*?)(?=^\[[^\n]+\]\s*$|\Z)", re.MULTILINE)


def normalize_expected_version(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("refs/tags/"):
        normalized = normalized[len("refs/tags/") :]
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized:
        raise RuntimeError("expected version is empty")
    return normalized


def source_project_version(pyproject: Path) -> str:
    """Read the static project version without requiring TOML support beyond Python 3.10."""

    text = pyproject.read_text(encoding="utf-8")
    section = _PROJECT_RE.search(text)
    if section is None:
        raise RuntimeError("pyproject.toml is missing [project]")
    match = _VERSION_RE.search(section.group(1))
    if match is None:
        raise RuntimeError("[project] must contain a static version")
    return normalize_expected_version(match.group(1))


def _one_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.resolve().glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one wheel, found {len(wheels)}")
    return wheels[0]


def _venv_python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_bin(env_dir: Path) -> Path:
    return env_dir / ("Scripts" if os.name == "nt" else "bin")


def _console_scripts() -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in importlib.metadata.entry_points(group="console_scripts"):
        if entry.name in EXPECTED_ENTRY_POINTS:
            result[entry.name] = entry.value
    return result


def _run_help(command: tuple[str, ...], *, cwd: Path) -> None:
    executable = shutil.which(command[0])
    if executable is None:
        raise RuntimeError(f"console executable not found: {command[0]}")
    completed = subprocess.run(
        [executable, *command[1:]],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"help command failed ({' '.join(command)}): rc={completed.returncode} stderr={completed.stderr}"
        )


def _installed_checks(*, expected_version: str) -> dict[str, object]:
    expected_version = normalize_expected_version(expected_version)
    version = importlib.metadata.version(PROJECT_NAME)
    if version != expected_version:
        raise RuntimeError(f"installed version mismatch: {version!r} != {expected_version!r}")

    package = importlib.import_module("chatgpt_web_adapter")
    package_path = Path(package.__file__).resolve()
    if "site-packages" not in str(package_path).lower().replace("\\", "/"):
        raise RuntimeError(f"smoke did not import installed wheel from site-packages: {package_path}")

    cli_v02 = importlib.import_module("chatgpt_web_adapter.cli_v02")
    doctor = importlib.import_module("chatgpt_web_adapter.doctor")
    artifact_manifest = importlib.import_module("chatgpt_web_adapter.artifact_manifest")
    if not callable(getattr(cli_v02, "main", None)):
        raise RuntimeError("installed cli_v02.main is missing")
    if not callable(getattr(doctor, "run_doctor", None)):
        raise RuntimeError("installed doctor.run_doctor is missing")
    if not hasattr(artifact_manifest, "ARTIFACT_MANIFEST_SCHEMA"):
        raise RuntimeError("installed artifact manifest contract is missing")

    from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

    extension_dir = browser_native_extension_dir().resolve()
    required_extension_files = [extension_dir / "manifest.json", extension_dir / "service_worker.js"]
    if not all(path.is_file() for path in required_extension_files):
        raise RuntimeError(f"installed browser extension package data is incomplete: {extension_dir}")
    if not list(extension_dir.glob("*.js")):
        raise RuntimeError("installed browser extension contains no JavaScript files")

    entry_points = _console_scripts()
    if entry_points != EXPECTED_ENTRY_POINTS:
        raise RuntimeError(f"installed console entry points mismatch: {entry_points!r}")

    cwd = Path.cwd()
    for command in HELP_COMMANDS:
        _run_help(command, cwd=cwd)

    missing_auth = cwd / "missing-auth.json"
    cwa = shutil.which("cwa")
    if cwa is None:
        raise RuntimeError("cwa executable not found")
    completed = subprocess.run(
        [cwa, "doctor", "--auth-file", str(missing_auth), "--json"],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 1:
        raise RuntimeError(
            f"pre-setup doctor should classify unavailable state with exit 1; got {completed.returncode}: {completed.stderr}"
        )
    payload = json.loads(completed.stdout)
    if payload.get("schema") != 1 or payload.get("command") != "doctor" or payload.get("ok") is not False:
        raise RuntimeError(f"unexpected pre-setup doctor payload: {payload!r}")
    checks = {item.get("id"): item for item in payload.get("checks", []) if isinstance(item, dict)}
    for check_id in (
        "environment.python",
        "environment.package_metadata",
        "environment.extension_id_integrity",
        "install.extension_package",
    ):
        if checks.get(check_id, {}).get("status") != "PASS":
            raise RuntimeError(f"installed static doctor check did not pass: {check_id}")
    if checks.get("auth.file", {}).get("status") != "FAIL":
        raise RuntimeError("pre-setup doctor did not classify missing auth as FAIL")

    return {
        "schema": 1,
        "ok": True,
        "version": version,
        "package_path": str(package_path),
        "extension_dir": str(extension_dir),
        "entry_points": sorted(entry_points),
        "help_commands": len(HELP_COMMANDS),
        "pre_setup_doctor_exit": 1,
    }


def run_smoke(*, wheel: Path, expected_version: str) -> dict[str, object]:
    expected_version = normalize_expected_version(expected_version)
    wheel = wheel.resolve()
    script = Path(__file__).resolve()
    with tempfile.TemporaryDirectory(prefix="cwa-wheel-venv-") as tmp:
        tmp_path = Path(tmp)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        python = _venv_python(env_dir)
        if not python.is_file():
            raise RuntimeError(f"isolated venv python was not created: {python}")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(wheel)],
            cwd=tmp_path,
            check=True,
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = str(_venv_bin(env_dir)) + os.pathsep + env.get("PATH", "")
        completed = subprocess.run(
            [
                str(python),
                str(script),
                "--inside-installed-venv",
                "--expected-version",
                expected_version,
                "--json",
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"isolated installed-wheel checks failed: rc={completed.returncode} stdout={completed.stdout} stderr={completed.stderr}"
            )
        return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and smoke-test a built CWA wheel")
    parser.add_argument("--wheel-dir", type=Path)
    parser.add_argument(
        "--expected-version",
        help=(
            "expected installed version; defaults to the static [project].version from "
            "the checkout pyproject.toml"
        ),
    )
    parser.add_argument("--inside-installed-venv", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.inside_installed_venv:
            if args.expected_version is None:
                raise RuntimeError("--expected-version is required inside the isolated installed-wheel venv")
            report = _installed_checks(expected_version=args.expected_version)
        else:
            if args.wheel_dir is None:
                raise RuntimeError("--wheel-dir is required")
            expected_version = (
                normalize_expected_version(args.expected_version)
                if args.expected_version is not None
                else source_project_version(
                    Path(__file__).resolve().parents[1] / "pyproject.toml"
                )
            )
            report = run_smoke(
                wheel=_one_wheel(args.wheel_dir),
                expected_version=expected_version,
            )
    except Exception as error:
        if args.json:
            print(json.dumps({"schema": 1, "ok": False, "error": str(error)}, indent=2))
        else:
            print(f"installed-wheel smoke: FAIL: {error}")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"installed-wheel smoke: PASS ({report['version']})")
        print(f"package: {report['package_path']}")
        print(f"extension: {report['extension_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
