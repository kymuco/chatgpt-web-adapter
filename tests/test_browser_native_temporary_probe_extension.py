from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_temporary_probe_is_layered_above_reconciled_worker() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]

    assert manifest["version"] == "0.1.11"
    assert worker_name == "service_worker_temporary_chat_history_probe.js"

    history_worker = (root / worker_name).read_text(encoding="utf-8")
    assert 'importScripts("service_worker_temporary_chat_turn_probe.js")' in history_worker
    turn_worker = (root / "service_worker_temporary_chat_turn_probe.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_temporary_chat_semantic_notice.js")' in turn_worker
    semantic_worker = (root / "service_worker_temporary_chat_semantic_notice.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_temporary_chat_ax_semantics.js")' in semantic_worker
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


def test_temporary_page_semantics_are_ui_markers_not_selection_proof() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_semantic_notice.js").read_text(
        encoding="utf-8"
    )

    assert "semantic:product-notice" in worker
    assert "semantic:document-title-temporary" in worker
    assert "semantic:url-temporary" in worker
    assert "modeMarkerObserved" in worker
    assert "modeMarkerSignals" in worker
    assert "selectionProven: false" in worker
    assert "proofSignals: []" in worker
    assert "MUST NOT be promoted into selected-state proof" in worker
    assert "semantic-category:" in worker
    for category in ("history", "memory", "training", "temporary"):
        assert f"{category}: [" in worker
    assert "closest('[role=\"tooltip\"],[data-radix-popper-content-wrapper]')" in worker
    assert 'type: "mouseMoved"' in worker
    assert "x: 1" in worker
    assert "y: 1" in worker


def test_temporary_turn_probe_is_explicit_isolated_single_write_characterization() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_turn_probe.js").read_text(
        encoding="utf-8"
    )

    assert "characterizeTemporaryTurn" in worker
    assert "acknowledgeDurableRisk" in worker
    assert "TEMPORARY_CHAT_TURN_PROBE_DURABLE_RISK_ACK_REQUIRED" in worker
    assert 'chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false })' in worker
    assert "chrome.tabs.remove(tabId)" in worker
    assert "click_unique_control_without_selected_state_proof" in worker
    assert "conversationWriteCount += 1" in worker
    assert "conversationWriteCount !== 1" in worker
    assert "Network.getResponseBody" in worker
    assert "extractSafeStreamMetadata" in worker
    assert "Input.insertText" in worker
    assert "uiModeMarkerObservedAfterTurn" in worker
    assert "postTurnUiModeSignals" in worker
    assert "automatic retry" not in worker.lower()
    assert "Raw prompt/assistant text" in worker


def test_temporary_history_probe_is_fresh_root_no_write_exact_link_observation() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_history_probe.js").read_text(
        encoding="utf-8"
    )

    assert "probeTemporaryHistoryPresence" in worker
    assert 'chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false })' in worker
    assert "chrome.tabs.remove(tabId)" in worker
    assert "document.querySelectorAll('a[href]')" in worker
    assert "exactLinkPresent" in worker
    assert "exactVisibleLinkPresent" in worker
    assert "conversationLinkCount" in worker
    assert "Input.insertText" not in worker
    assert "submitOfficialPageTurn" not in worker
    assert "Conversation titles, link text, raw DOM" in worker


def test_temporary_probe_bypasses_submit_mouse_hotfix_for_mode_control_click() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    assert "chrome.debugger.sendCommand(debuggee, method, params)" in worker
    assert "_pr87RawSendCommand" in worker
