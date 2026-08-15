from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_temporary_probe_is_layered_above_reconciled_worker() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]

    assert manifest["version"] == "0.1.7"
    assert worker_name == "service_worker_temporary_chat_state_semantics.js"

    worker = (root / worker_name).read_text(encoding="utf-8")
    assert 'importScripts("service_worker_temporary_chat.js")' in worker
    base_worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")
    assert 'importScripts("service_worker_runtime_tab_reconciliation.js")' in base_worker
    assert "probeTemporaryMode" in base_worker
    assert "isolated_new_chat" in base_worker


def test_temporary_probe_is_no_write_and_uses_isolated_disposable_tab() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    assert 'chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false })' in worker
    assert "chrome.tabs.remove(tabId)" in worker
    assert "isConversationWrite" in worker
    assert "TEMPORARY_CHAT_PROBE_UNEXPECTED_CONVERSATION_WRITE" in worker
    assert "message?.text != null" in worker
    assert "Input.insertText" not in worker


def test_temporary_probe_requires_explicit_selected_state_evidence() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    for signal in (
        "aria-pressed:true",
        "aria-checked:true",
        "aria-current:true",
        "data-selected:true",
        "data-state:",
    ):
        assert signal in worker

    assert "TEMPORARY_CHAT_CONTROL_AMBIGUOUS" in worker
    assert "modeSelectionProven" in worker
    assert "after?.selected === true" in worker


def test_temporary_probe_accepts_accessibility_action_semantics_as_state_evidence() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_state_semantics.js").read_text(
        encoding="utf-8"
    )

    # Current live ChatGPT exposed the Temporary control through aria-label but
    # without aria-pressed/data-state. The label's action semantics are still
    # explicit accessibility state evidence: an available "turn off" action
    # implies the mode is selected; "turn on" implies it is not selected.
    for signal in (
        "aria-label:turn-off-action",
        "aria-label:disable-action",
        "aria-label:turn-on-action",
        "aria-label:enable-action",
        "aria-label:ru-turn-off-action",
        "aria-label:ru-turn-on-action",
    ):
        assert signal in worker

    assert "Raw aria-label text still never leaves the browser context" in worker
    assert 'temporaryStateSemantics: "aria_label_action_v1"' in worker


def test_temporary_probe_bypasses_submit_mouse_hotfix_for_mode_control_click() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    # The existing hotfix wraps global sendCommand() mouse events to repair
    # submit behavior. Temporary-control probing must use raw CDP commands so a
    # selector click can never trigger the send-button fallback ladder.
    assert "chrome.debugger.sendCommand(debuggee, method, params)" in worker
    assert "_pr87RawSendCommand" in worker
