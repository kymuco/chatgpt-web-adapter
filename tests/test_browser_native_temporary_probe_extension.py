from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_temporary_probe_is_layered_above_reconciled_worker() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]

    assert manifest["version"] == "0.1.9"
    assert worker_name == "service_worker_temporary_chat_semantic_notice.js"

    worker = (root / worker_name).read_text(encoding="utf-8")
    assert 'importScripts("service_worker_temporary_chat_ax_semantics.js")' in worker
    ax_worker = (root / "service_worker_temporary_chat_ax_semantics.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_temporary_chat_state_semantics.js")' in ax_worker
    state_worker = (root / "service_worker_temporary_chat_state_semantics.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_temporary_chat.js")' in state_worker
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


def test_temporary_probe_keeps_failed_aria_action_hypothesis_isolated() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_state_semantics.js").read_text(
        encoding="utf-8"
    )

    assert "aria-label:temporary-neutral" in worker
    assert "Raw aria-label text still never leaves the browser context" in worker


def test_temporary_probe_adds_accessibility_tree_state_characterization() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_ax_semantics.js").read_text(
        encoding="utf-8"
    )

    assert "Accessibility.getFullAXTree" in worker
    assert "Accessibility.enable" in worker
    assert '["pressed", "checked", "selected"]' in worker
    assert '["expanded", "haspopup", "disabled", "focused"]' in worker
    assert "actionableCandidateCount" in worker
    assert "selectionProofSignals" in worker
    assert "axBefore" in worker
    assert "axAfter" in worker
    assert "Accessible names and raw AX nodes remain browser-local" in worker


def test_temporary_probe_adds_semantic_notice_characterization_and_dismisses_tooltip() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_semantic_notice.js").read_text(
        encoding="utf-8"
    )

    assert "semantic:product-notice" in worker
    assert "semantic:document-title-temporary" in worker
    assert "semantic:url-temporary" in worker
    assert "semantic-category:history" in worker
    assert "semantic-category:memory" in worker
    assert "semantic-category:training" in worker
    assert "semantic-category:temporary" in worker
    assert "closest('[role=\"tooltip\"],[data-radix-popper-content-wrapper]')" in worker
    assert 'type: "mouseMoved"' in worker
    assert "x: 1" in worker
    assert "y: 1" in worker
    assert "Raw text" not in worker
    assert "raw text" in worker


def test_temporary_probe_bypasses_submit_mouse_hotfix_for_mode_control_click() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    assert "chrome.debugger.sendCommand(debuggee, method, params)" in worker
    assert "_pr87RawSendCommand" in worker
