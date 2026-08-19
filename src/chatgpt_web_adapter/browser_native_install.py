from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .browser_native_protocol import HOST_NAME, default_browser_native_state_dir

EXTENSION_PUBLIC_KEY = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5mWXlQie901Dp/YyR4fgMEn6OmidZgODbcv1HDKoAo7xTMuer648M5jxrkfTHZCiq2uxPQYGhe7gSbqFeYZsX9YPQW12OGHykz5WKl2y3e+9tKqnvoWRbmHlegU3d+Sx+Nu6k4sXePP91aeJotorM8T8DMl7SY9djvUR2MHgvU7PmnHJRXpy0YC/J0avUa208J5lRxMw1rabaHaRVO96g0bnRLGt0hpGG2Hz6EklU2s/wtfnhWjVk6eFy6EHFLk9c97r8iQYGgO1/syAWK4d4Mqe1rx+3sqv6tQzk6iyyG7Q1l6g58yMuM3O76AWlB+H5UPquFsnK/5Atgx06h9GvwIDAQAB"
EXTENSION_ID = "kjfnkhajljnkbhikmfijcchenlfglaie"


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


def browser_native_extension_dir() -> Path:
    return Path(__file__).resolve().parent / "browser_native_extension"


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
    return BrowserNativeInstallResult(
        host_name=HOST_NAME,
        extension_id=extension_id,
        extension_dir=browser_native_extension_dir(),
        host_manifest=manifest_path,
        host_executable=executable,
    )
