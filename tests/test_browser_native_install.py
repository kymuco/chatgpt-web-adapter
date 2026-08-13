from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import (
    EXTENSION_ID,
    browser_native_extension_dir,
    extension_id_from_public_key,
)


def test_packaged_extension_identity_and_manifest() -> None:
    assert extension_id_from_public_key() == EXTENSION_ID
    assert EXTENSION_ID == "kjfnkhajljnkbhikmfijcchenlfglaie"
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["minimum_chrome_version"] == "118"
    assert manifest["version"] == "0.1.3"
    assert manifest["background"]["service_worker"] == "service_worker_recovery.js"
    assert set(manifest["permissions"]) == {"debugger", "tabs", "storage", "nativeMessaging"}
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]
