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
_DEPLOYMENT_UNHEALTHY_MARKER = ".deployment-unhealthy"


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


def _current_environment_host_executable() -> Path | None:
    suffix = ".exe" if os.name == "nt" else ""
    adjacent = (
        Path(sys.executable).resolve().parent
        / f"chatgpt-web-adapter-native-host{suffix}"
    )
    return adjacent if adjacent.is_file() else None


def browser_native_deployment_status() -> dict[str, Any]:
    """Return deterministic package/install identity evidence without browser mutation."""

    packaged = packaged_browser_native_extension_dir()
    installed = installed_browser_native_extension_dir()
    deployment_path = browser_native_deployment_manifest_path()
    package_identity = _package_identity()
    packaged_digest = _extension_tree_digest(packaged) if packaged.is_dir() else None
    installed_digest = _extension_tree_digest(installed) if installed.is_dir() else None

    deployment: dict[str, Any] | None = None
    if deployment_path.is_file():
        try:
            value = json.loads(deployment_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                deployment = value
        except (OSError, ValueError, json.JSONDecodeError):
            deployment = None

    current_host = _current_environment_host_executable()
    expected_source_revision = package_identity.get("source_revision")
    deployed_source_revision = deployment.get("source_revision") if deployment else None
    source_revision_matches = (
        expected_source_revision is None
        or deployed_source_revision is None
        or deployed_source_revision == expected_source_revision
    )
    expected_package_version = package_identity.get("package_version")
    deployed_package_version = deployment.get("package_version") if deployment else None
    package_version_matches = (
        expected_package_version is None
        or deployed_package_version is None
        or deployed_package_version == expected_package_version
    )
    deployed_host = deployment.get("host_executable") if deployment else None
    host_matches_current_environment = (
        current_host is not None
        and isinstance(deployed_host, str)
        and Path(deployed_host).expanduser().resolve() == current_host
    )
    digest_matches = (
        packaged_digest is not None
        and installed_digest is not None
        and packaged_digest == installed_digest
        and deployment is not None
        and deployment.get("extension_digest") == installed_digest
    )
    deployment_schema_matches = (
        deployment is not None and deployment.get("schema") == DEPLOYMENT_SCHEMA
    )
    extension_id_matches = (
        deployment is not None and deployment.get("extension_id") == EXTENSION_ID
    )
    healthy = all(
        (
            deployment_schema_matches,
            extension_id_matches,
            digest_matches,
            source_revision_matches,
            package_version_matches,
            host_matches_current_environment,
        )
    )
    return {
        "healthy": healthy,
        "packaged_extension_dir": str(packaged.resolve()),
        "installed_extension_dir": str(installed.resolve()),
        "deployment_manifest": str(deployment_path.resolve()),
        "packaged_extension_digest": packaged_digest,
        "installed_extension_digest": installed_digest,
        "current_host_executable": str(current_host)
        if current_host is not None
        else None,
        "deployment": deployment,
        "deployment_schema_matches": deployment_schema_matches,
        "extension_id_matches": extension_id_matches,
        "extension_digest_matches": digest_matches,
        "source_revision_matches": source_revision_matches,
        "package_version_matches": package_version_matches,
        "host_matches_current_environment": host_matches_current_environment,
        **package_identity,
    }


def browser_native_extension_dir() -> Path:
    """Return the Chrome load target for the current browser-native deployment.

    Before first install, source inspection may use the packaged extension. Once a
    legacy host registration or stable extension exists, deployment identity must
    be healthy. A stale/mixed deployment maps to a deliberately missing sentinel
    path so required doctor install checks fail closed instead of false-green.
    """

    packaged = packaged_browser_native_extension_dir()
    installed = installed_browser_native_extension_dir()
    stable_present = (installed / "manifest.json").is_file()
    legacy_or_installed = stable_present or _user_native_manifest_path().is_file()
    if not legacy_or_installed:
        return packaged
    if stable_present and browser_native_deployment_status()["healthy"]:
        return installed
    return installed / _DEPLOYMENT_UNHEALTHY_MARKER


def _materialize_extension(source: Path, target: Path) -> str:
    """Stage and swap one exact extension tree into the stable runtime path."""

    source = source.resolve()
    target = target.resolve()
    source_manifest = source / "manifest.json"
    if not source.is_dir() or not source_manifest.is_file():
        raise FileNotFoundError(
            f"packaged browser-native extension is incomplete: {source}"
        )
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
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _resolve_host_executable(value: str | Path | None = None) -> Path:
    if value is not None:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    adjacent = _current_environment_host_executable()
    if adjacent is not None:
        return adjacent

    candidates = [
        shutil.which("chatgpt-web-adapter-native-host"),
        shutil.which("chatgpt-web-adapter-native-host.exe"),
    ]
    for candidate in candidates:
        if candidate:
            return Path(candidate).resolve()
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
    return (
        Path.home()
        / ".config"
        / "google-chrome"
        / "NativeMessagingHosts"
        / f"{HOST_NAME}.json"
    )


def install_native_messaging_host(
    *,
    extension_id: str = EXTENSION_ID,
    host_executable: str | Path | None = None,
) -> BrowserNativeInstallResult:
    extension_id = extension_id.strip().lower()
    if len(extension_id) != 32 or any(
        char < "a" or char > "p" for char in extension_id
    ):
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
