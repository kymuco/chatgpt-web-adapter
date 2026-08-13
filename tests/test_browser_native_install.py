from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import (
    EXTENSION_ID,
    browser_native_extension_dir,
    extension_id_from_public_key,
)


def test_packaged_extension_key_has_stable_expected_id() -> None:
    assert extension_id_from_public_key() == EXTENSION_ID
    assert EXTENSION_ID == "kjfnkhajljnkbhikmfijcchenlfglaie"


def test_packaged_extension_has_narrow_runtime_contract() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker = (root / "service_worker.js").read_text(encoding="utf-8")

    assert manifest["minimum_chrome_version"] == "118"
    assert manifest["version"] == "0.1.1"
    assert set(manifest["permissions"]) == {
        "debugger",
        "tabs",
        "storage",
        "nativeMessaging",
    }
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]
    assert "chrome.runtime.connectNative(HOST_NAME)" in worker
    assert "chrome.tabs.create({ url: targetUrl, active: false })" in worker
    assert "chrome.storage.local" in worker
    assert "fetch(" not in worker
    assert "chrome.cookies" not in worker
    assert "sentinel/chat-requirements" not in worker
    assert "resume_conversation_token" not in worker
    assert "responseBody:" not in worker
    assert "Network.getResponseBody" in worker


def test_packaged_extension_uses_trusted_send_button_submit_with_bounded_fallback() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker.js").read_text(encoding="utf-8")

    assert 'button[data-testid="send-button"]' in worker
    assert "Input.dispatchMouseEvent" in worker
    assert 'strategy: "send_button_click"' in worker
    assert 'strategy: "enter_fallback"' in worker
    assert "CHATGPT_SUBMIT_NOT_OBSERVED" in worker
    assert "submitAckMs" in worker
    assert ".click()" not in worker
