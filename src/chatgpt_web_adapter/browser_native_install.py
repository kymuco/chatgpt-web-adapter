from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .browser_native_protocol import HOST_NAME, default_browser_native_state_dir

EXTENSION_PUBLIC_KEY = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5mWXlQie901Dp/YyR4fgMEn6OmidZgODbcv1HDKoAo7xTMuer648M5jxrkfTHZCiq2uxPQYGhe7gSbqFeYZsX9YPQW12OGHykz5WKl2y3e+9tKqnvoWRbmHlegU3d+Sx+Nu6k4sXePP91aeJotorM8T8DMl7SY9djvUR2MHgvU7PmnHJRXpy0YC/J0avUa208J5lRxMw1rabaHaRVO96g0bnRLGt0hpGG2Hz6EklU2s/wtfnhWjVk6eFy6EHFLk9c97r8iQYGgO1/syAWK4d4Mqe1rx+3sqv6tQzk6iyyG7Q1l6g58yMuM3O76AWlB+H5UPquFsnK/5Atgx06h9GvwIDAQAB"
EXTENSION_ID = "kjfnkhajljnkbhikmfijcchenlfglaie"
DEPLOYMENT_SCHEMA = 1
_PACKAGE_NAME = "chatgpt-web-adapter"


@dataclass(frozen=True)
class BrowserNativeInstallResult:
    host_name: str
    extension_id: str
    extension_dir: Path
    host_manifest: Path
    host_executable: Path


def extension_id_from_public_key(value: str = EXTENSION_PUBLIC_KEY) -> str:
    digest = hashlib.sha256(base64.b64decode(value)).digest()[:16]
    alphabet = "abcdefghijklmnop"
    return "".join(alphabet[byte >> 4] + alphabet[byte & 15] for byte in digest)


def packaged_browser_native_extension_dir() -> Path:
    """Return the immutable extension source shipped by the current Python package."""

    return Path(__file__).resolve().parent / "browser_native_extension"


def installed_browser_native_extension_dir() -> Path:
    """Return the stable per-user unpacked-extension deployment path."""

    return default_browser_native_state_dir() / "extension"


def browser_native_deployment_manifest_path() -> Path:
    return default_browser_native_state_dir() / "deployment.json"


def browser_native_extension_dir() -> Path:
    """Return the stable installed extension when present, else the packaged source.

    The fallback keeps source-tree and wheel inspection compatible before the first
    browser-native install. Chrome should be pointed at this command only after
    `browser-native install`, at which point the returned path is stable across
    checkout, virtual-environment, and package-source changes.
    """

    installed = installed_browser_native_extension_dir()
    if (installed / "manifest.json").is_file():
        return installed
    return packaged_browser_native_extension_dir()


def _extension_tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise FileNotFoundError(f"browser-native extension is empty: {root}")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _package_identity() -> dict[str, Any]:
    version: str | None = None
    source_revision: str | None = None
    try:
        distribution = importlib.metadata.distribution(_PACKAGE_NAME)
        version = distribution.version
        direct_url = distribution.read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        direct_url = None
    if direct_url:
        try:
            payload = json.loads(direct_url)
            vcs_info = payload.get("vcs_info") if isinstance(payload, dict) else None
            revision = vcs_info.get("commit_id") if isinstance(vcs_info, dict) else None
            if isinstance(revision, str) and revision.strip():
                source_revision = revision.strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            source_revision = None
    return {
        "package": _PACKAGE_NAME,
        "package_version": version,
        "source_revision": source_revision,
    }


def _materialize_extension(source: Path, target: Path) -> str:
    """Stage and swap one exact extension tree into the stable runtime path."""

    source = source.resolve()
    target = target.resolve()
    source_manifest = source / "manifest.json"
    if not source.is_dir() or not source_manifest.is_file():
        raise FileNotFoundError(f"packaged browser-native extension is incomplete: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_digest = _extension_tree_digest(source)

    staging = Path(tempfile.mkdtemp(prefix=".extension-stage-", dir=target.parent))
    backup = target.parent / ".extension-backup"
    try:
        shutil.rmtree(staging)
        shutil.copytree(source, staging)
        staged_digest = _extension_tree_digest(staging)
        if staged_digest != source_digest:
            raise OSError("staged browser-native extension digest mismatch")

        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.replace(backup)
        try:
            staging.replace(target)
        except Exception:
            if backup.exists() and not target.exists():
                backup.replace(target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return source_digest


def _write_deployment_manifest(
    *,
    extension_id: str,
    extension_digest: str,
    host_executable: Path,
) -> None:
    path = browser_native_deployment_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": DEPLOYMENT_SCHEMA,
        "extension_id": extension_id,
        "extension_digest": extension_digest,
        "extension_dir": str(installed_browser_native_extension_dir().resolve()),
        "host_executable": str(host_executable.resolve()),
        **_package_identity(),
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _resolve_host_executable(value: str | Path | None = None) -> Path:
    if value is not None:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    candidates = [
        shutil.which("chatgpt-web-adapter-native-host"),
        shutil.which("chatgpt-web-adapter-native-host.exe"),
    ]
    for candidate in candidates:
        if candidate:
            return Path(candidate).resolve()
    suffix = ".exe" if os.name == "nt" else ""
    adjacent = Path(sys.executable).resolve().parent / f"chatgpt-web-adapter-native-host{suffix}"
    if adjacent.is_file():
        return adjacent
    raise FileNotFoundError(
        "chatgpt-web-adapter-native-host executable not found; reinstall the package so console scripts are generated"
    )


def _user_native_manifest_path() -> Path:
    if os.name == "nt":
        return default_browser_native_state_dir() / f"{HOST_NAME}.json"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "NativeMessagingHosts"
            / f"{HOST_NAME}.json"
        )
    return Path.home() / ".config" / "google-chrome" / "NativeMessagingHosts" / f"{HOST_NAME}.json"


def install_native_messaging_host(
    *,
    extension_id: str = EXTENSION_ID,
    host_executable: str | Path | None = None,
) -> BrowserNativeInstallResult:
    extension_id = extension_id.strip().lower()
    if len(extension_id) != 32 or any(char < "a" or char > "p" for char in extension_id):
        raise ValueError("extension_id must be a 32-character Chrome extension id")

    source_extension = packaged_browser_native_extension_dir()
    installed_extension = installed_browser_native_extension_dir()
    extension_digest = _materialize_extension(source_extension, installed_extension)

    executable = _resolve_host_executable(host_executable)
    manifest_path = _user_native_manifest_path()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": HOST_NAME,
        "description": "ChatGPT Web Adapter browser-native bridge",
        "path": str(executable),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(manifest_path, 0o600)
    if os.name == "nt":
        import winreg

        key_path = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(manifest_path.resolve()))

    _write_deployment_manifest(
        extension_id=extension_id,
        extension_digest=extension_digest,
        host_executable=executable,
    )
    return BrowserNativeInstallResult(
        host_name=HOST_NAME,
        extension_id=extension_id,
        extension_dir=installed_extension,
        host_manifest=manifest_path,
        host_executable=executable,
    )
