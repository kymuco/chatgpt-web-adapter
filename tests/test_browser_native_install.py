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
    shim = (root / "service_worker_hotfix.js").read_text(encoding="utf-8")

    assert manifest["minimum_chrome_version"] == "118"
    assert manifest["version"] == "0.1.2"
    assert manifest["background"]["service_worker"] == "service_worker_hotfix.js"
    assert "type" not in manifest["background"]
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
    for source in (worker, shim):
        assert "fetch(" not in source
        assert "chrome.cookies" not in source
        assert "sentinel/chat-requirements" not in source
        assert "resume_conversation_token" not in source
        assert "responseBody:" not in source
    assert "Network.getResponseBody" in worker


def test_packaged_extension_uses_ack_aware_submit_activation_ladder() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker.js").read_text(encoding="utf-8")
    shim = (root / "service_worker_hotfix.js").read_text(encoding="utf-8")

    assert 'button[data-testid="send-button"]' in worker
    assert "Input.dispatchMouseEvent" in worker
    assert 'strategy: "send_button_click"' in worker
    assert 'strategy: "enter_fallback"' in worker
    assert "CHATGPT_SUBMIT_NOT_OBSERVED" in worker
    assert "submitAckMs" in worker
    assert ".click()" not in worker

    assert shim.startswith('importScripts("service_worker.js")')
    assert "_originalCoreSendCommand = sendCommand" in shim
    assert "sendCommand = _patchedCoreSendCommand" in shim
    assert "chrome.debugger.sendCommand =" not in shim
    assert "Object.defineProperty" not in shim
    assert "buttons: 1" in shim
    assert "buttons: 0" in shim
    assert "Network.requestWillBeSent" in shim
    assert "focused_button_enter" in shim
    assert "focused_button_space" in shim
    assert "page_button_click" in shim
    assert "button.click()" in shim
    assert "state.observed" in shim
