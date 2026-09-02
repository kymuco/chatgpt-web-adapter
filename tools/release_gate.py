from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Any

PROJECT_NAME = "chatgpt-web-adapter"
DIST_BASENAME = "chatgpt_web_adapter"
EXPECTED_ENTRY_POINTS = {
    "cwa": "chatgpt_web_adapter.cli_v02:main",
    "chatgpt-web-adapter": "chatgpt_web_adapter.cli_v02:main",
    "chatgpt-web-adapter-native-host": "chatgpt_web_adapter.browser_native_host:main",
}
EXTENSION_PACKAGE_PATTERNS = ("*.json", "*.js", "*.html", "*.css", "*.png")
EXTENSION_PACKAGE_SUFFIXES = (".json", ".js", ".html", ".css", ".png")
REQUIRED_WHEEL_FILES = {
    # Stable CLI / diagnostics baseline retained from CWA 0.2.
    "chatgpt_web_adapter/cli_v02.py",
    "chatgpt_web_adapter/doctor.py",
    "chatgpt_web_adapter/artifact_manifest.py",
    "chatgpt_web_adapter/conversation_snapshot.py",
    "chatgpt_web_adapter/export.py",
    # CWA 0.3 product-runtime/public-surface freeze.
    "chatgpt_web_adapter/product_runtime.py",
    "chatgpt_web_adapter/product_transport.py",
    "chatgpt_web_adapter/product_contract.py",
    "chatgpt_web_adapter/product_support.py",
    "chatgpt_web_adapter/product_capabilities.py",
    "chatgpt_web_adapter/product_provenance.py",
    "chatgpt_web_adapter/product_observations.py",
    "chatgpt_web_adapter/public_surface.py",
    "chatgpt_web_adapter/product_rich_input_capability_gate_pr9_4.py",
    "chatgpt_web_adapter/product_web_search_capability_gate_pr9_3.py",
    # Browser-owned package entrypoints/assets.
    "chatgpt_web_adapter/browser_native_extension/manifest.json",
    "chatgpt_web_adapter/browser_native_extension/service_worker.js",
    "chatgpt_web_adapter/browser_native_extension/service_worker_product_surface_pr11_0.js",
    "chatgpt_web_adapter/browser_native_extension/popup.html",
    "chatgpt_web_adapter/browser_native_extension/popup.css",
    "chatgpt_web_adapter/browser_native_extension/popup.js",
    "chatgpt_web_adapter/browser_native_extension/icon16.png",
    "chatgpt_web_adapter/browser_native_extension/icon32.png",
    "chatgpt_web_adapter/browser_native_extension/icon48.png",
    "chatgpt_web_adapter/browser_native_extension/icon128.png",
}
REQUIRED_SDIST_SUFFIXES = {
    "/pyproject.toml",
    "/README.md",
    "/CHANGELOG.md",
    "/LICENSE",
    "/src/chatgpt_web_adapter/product_runtime.py",
    "/src/chatgpt_web_adapter/product_observations.py",
    "/src/chatgpt_web_adapter/public_surface.py",
    "/src/chatgpt_web_adapter/product_rich_input_capability_gate_pr9_4.py",
    "/src/chatgpt_web_adapter/browser_native_extension/manifest.json",
    "/src/chatgpt_web_adapter/browser_native_extension/service_worker.js",
    "/src/chatgpt_web_adapter/browser_native_extension/service_worker_product_surface_pr11_0.js",
    "/src/chatgpt_web_adapter/browser_native_extension/popup.html",
    "/src/chatgpt_web_adapter/browser_native_extension/popup.css",
    "/src/chatgpt_web_adapter/browser_native_extension/popup.js",
    "/src/chatgpt_web_adapter/browser_native_extension/icon128.png",
}
_VERSION_RE = re.compile(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
_PROJECT_RE = re.compile(r"^\[project\]\s*$([\s\S]*?)(?=^\[[^\n]+\]\s*$|\Z)", re.MULTILINE)
_RELEASE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ReleaseGateError(RuntimeError):
    pass


def project_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    section = _PROJECT_RE.search(text)
    if section is None:
        raise ReleaseGateError("pyproject.toml is missing [project]")
    match = _VERSION_RE.search(section.group(1))
    if match is None:
        raise ReleaseGateError("[project] must contain a static version")
    return match.group(1).strip()


def changelog_release_date(changelog: Path, version: str) -> str | None:
    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^##\s+{re.escape(version)}(?:\s+-\s+([^\n]+))?\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        raise ReleaseGateError(f"CHANGELOG.md has no {version} release heading")
    suffix = match.group(1)
    return suffix.strip() if suffix is not None else None


def normalize_release_tag(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("refs/tags/"):
        normalized = normalized[len("refs/tags/") :]
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized:
        raise ReleaseGateError("release tag is empty")
    return normalized


def _entry_points(text: str) -> dict[str, str]:
    section = None
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "console_scripts" and "=" in line:
            name, target = line.split("=", 1)
            result[name.strip()] = target.strip()
    return result


def _source_extension_files(root: Path) -> set[str]:
    extension_dir = root / "src" / "chatgpt_web_adapter" / "browser_native_extension"
    files = {
        path.name
        for pattern in EXTENSION_PACKAGE_PATTERNS
        for path in extension_dir.glob(pattern)
        if path.is_file()
    }
    if not files:
        raise ReleaseGateError("source browser extension package-data set is empty")
    return files


def verify_wheel(wheel: Path, *, root: Path, version: str) -> dict[str, Any]:
    expected_name = f"{DIST_BASENAME}-{version}-py3-none-any.whl"
    if wheel.name != expected_name:
        raise ReleaseGateError(f"unexpected wheel filename: {wheel.name}; expected {expected_name}")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        dist_info = f"{DIST_BASENAME}-{version}.dist-info"
        metadata_name = f"{dist_info}/METADATA"
        entry_points_name = f"{dist_info}/entry_points.txt"
        if metadata_name not in names:
            raise ReleaseGateError("wheel is missing METADATA")
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        if metadata.get("Name") != PROJECT_NAME:
            raise ReleaseGateError(f"wheel metadata Name mismatch: {metadata.get('Name')!r}")
        if metadata.get("Version") != version:
            raise ReleaseGateError(f"wheel metadata Version mismatch: {metadata.get('Version')!r}")
        missing_required = sorted(REQUIRED_WHEEL_FILES - names)
        if missing_required:
            raise ReleaseGateError(f"wheel is missing required files: {missing_required}")
        source_extension_files = _source_extension_files(root)
        wheel_extension_files = {
            Path(name).name
            for name in names
            if name.startswith("chatgpt_web_adapter/browser_native_extension/")
            and name.endswith(EXTENSION_PACKAGE_SUFFIXES)
        }
        missing_extension = sorted(source_extension_files - wheel_extension_files)
        if missing_extension:
            raise ReleaseGateError(
                f"wheel omitted packaged browser extension files: {missing_extension}"
            )
        if entry_points_name not in names:
            raise ReleaseGateError("wheel is missing console entry-point metadata")
        actual_entry_points = _entry_points(archive.read(entry_points_name).decode("utf-8"))
        if actual_entry_points != EXPECTED_ENTRY_POINTS:
            raise ReleaseGateError(f"console entry points mismatch: {actual_entry_points!r}")
    return {
        "path": str(wheel),
        "filename": wheel.name,
        "required_files": len(REQUIRED_WHEEL_FILES),
        "extension_files": len(source_extension_files),
        "entry_points": sorted(EXPECTED_ENTRY_POINTS),
    }


def verify_sdist(sdist: Path, *, version: str) -> dict[str, Any]:
    expected_name = f"{DIST_BASENAME}-{version}.tar.gz"
    if sdist.name != expected_name:
        raise ReleaseGateError(f"unexpected sdist filename: {sdist.name}; expected {expected_name}")
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
    missing = [
        suffix
        for suffix in sorted(REQUIRED_SDIST_SUFFIXES)
        if not any(name.endswith(suffix) for name in names)
    ]
    if missing:
        raise ReleaseGateError(f"sdist is missing required files: {missing}")
    return {
        "path": str(sdist),
        "filename": sdist.name,
        "required_files": len(REQUIRED_SDIST_SUFFIXES),
    }


def verify_dist(root: Path, dist_dir: Path, version: str) -> dict[str, Any]:
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1:
        raise ReleaseGateError(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        raise ReleaseGateError(f"expected exactly one sdist, found {len(sdists)}")
    return {
        "wheel": verify_wheel(wheels[0], root=root, version=version),
        "sdist": verify_sdist(sdists[0], version=version),
    }


def run_release_gate(
    *,
    root: Path,
    dist_dir: Path | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    version = project_version(root / "pyproject.toml")
    normalized_tag = normalize_release_tag(tag) if tag is not None else None
    try:
        release_date = changelog_release_date(root / "CHANGELOG.md", version)
    except ReleaseGateError:
        if normalized_tag is not None:
            raise
        release_date = None

    if normalized_tag is not None:
        if normalized_tag != version:
            raise ReleaseGateError(
                f"release tag/version mismatch: tag={normalized_tag!r} package={version!r}"
            )
        if release_date is None or not _RELEASE_DATE_RE.fullmatch(release_date):
            raise ReleaseGateError(
                "tagged release requires CHANGELOG heading with YYYY-MM-DD release date"
            )

    artifacts = None
    if dist_dir is not None:
        artifacts = verify_dist(root, dist_dir.resolve(), version)
    return {
        "schema": 1,
        "ok": True,
        "project": PROJECT_NAME,
        "version": version,
        "changelog_release_date": release_date,
        "tag": normalized_tag,
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the CWA release candidate contract")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_release_gate(root=args.root, dist_dir=args.dist_dir, tag=args.tag)
    except (OSError, ValueError, ReleaseGateError, zipfile.BadZipFile, tarfile.TarError) as error:
        if args.json:
            print(json.dumps({"schema": 1, "ok": False, "error": str(error)}, indent=2))
        else:
            print(f"release gate: FAIL: {error}")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"release gate: PASS ({report['project']} {report['version']})")
        if report["tag"] is not None:
            print(f"tag: {report['tag']}")
        if report["artifacts"] is not None:
            print(f"wheel: {report['artifacts']['wheel']['filename']}")
            print(f"sdist: {report['artifacts']['sdist']['filename']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
