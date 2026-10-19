"""Independent Qwen deployment and native host."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .browser_native_host import BrowserNativeBroker
from .browser_native_install import linux_native_messaging_manifest_paths
from .browser_native_protocol import (
    default_browser_native_state_dir,
    read_native_message,
)

HOST_NAME = "com.kymuco.qwen_web_adapter"


def state_dir():
    return default_browser_native_state_dir().parent / "qwen-native"


def host_main():
    broker = BrowserNativeBroker(state_dir=state_dir())
    broker.start()
    try:
        while True:
            try:
                message = read_native_message(sys.stdin.buffer)
            except EOFError:
                break
            broker.route_native_message(message)
    finally:
        broker.close()
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension-id")
    args = parser.parse_args()
    root = state_dir()
    extension = root / "extension"
    extension.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "browser_native_extension"
    for name in ["service_worker_qwen_provider.js", "service_worker_qwen_stream.js"]:
        shutil.copyfile(source / name, extension / name)
    shutil.copyfile(
        Path(__file__).with_name("qwen_native_worker.js"), extension / "worker.js"
    )
    manifest = {
        "manifest_version": 3,
        "name": "Qwen Web Adapter (isolated)",
        "version": "0.1.0",
        "minimum_chrome_version": "124",
        "permissions": ["debugger", "tabs", "storage", "nativeMessaging"],
        "host_permissions": ["https://chat.qwen.ai/*"],
        "background": {"service_worker": "worker.js"},
    }
    (extension / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if args.extension_id:
        identity = args.extension_id
        if len(identity) != 32 or any(c not in "abcdefghijklmnop" for c in identity):
            parser.error("Invalid Chrome extension ID")
        if os.name != "nt" and sys.platform != "linux":
            parser.error("Native host registration supports Windows and Linux only")

        suffix = ".exe" if os.name == "nt" else ""
        executable = Path(sys.executable).parent / f"qwen-web-adapter-native-host{suffix}"
        if not executable.is_file():
            parser.error("Run pip install -e . first")
        payload = {
            "name": HOST_NAME,
            "description": "Independent Qwen bridge",
            "path": str(executable.resolve()),
            "type": "stdio",
            "allowed_origins": [f"chrome-extension://{identity}/"],
        }
        if os.name == "nt":
            host = root / "native-host.json"
            host.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            import winreg

            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                rf"Software\\Google\\Chrome\\NativeMessagingHosts\\{HOST_NAME}",
            ) as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(host))
        else:
            for host in linux_native_messaging_manifest_paths(HOST_NAME):
                host.parent.mkdir(parents=True, exist_ok=True)
                host.write_text(
                    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
                )
                os.chmod(host, 0o600)
        print("Qwen native host registered")
    print(extension)


if __name__ == "__main__":
    main()
