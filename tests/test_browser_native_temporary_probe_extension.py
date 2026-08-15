from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_temporary_probe_is_layered_above_reconciled_worker() -> None:
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]

    assert manifest["version"] == "0.1.8"
    assert worker_name == "service_worker_temporary_chat_ax_semantics.js"

    worker = (root / worker_name).read_text(encoding="utf-8")
    assert 'importScripts("service_worker_temporary_chat_state_semantics.js")' in worker
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

    # Live run #2 showed that current ChatGPT's aria-label matched Temporary but
    # still did not expose actionable on/off wording. This layer remains a
    # bounded historical characterization input rather than a production claim.
    assert "aria-label:temporary-neutral" in worker
    assert "Raw aria-label text still never leaves the browser context" in worker


def test_temporary_probe_adds_accessibility_tree_state_characterization() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat_ax_semantics.js").read_text(
        encoding="utf-8"
    )

    assert 'Accessibility.getFullAXTree' in worker
    assert 'Accessibility.enable' in worker
    assert '["pressed", "checked", "selected"]' in worker
    assert '["expanded", "haspopup", "disabled", "focused"]' in worker
    assert "actionableCandidateCount" in worker
    assert "selectionProofSignals" in worker
    assert "axBefore" in worker
    assert "axAfter" in worker
    assert "Accessible names and raw AX nodes remain browser-local" in worker


def test_temporary_probe_bypasses_submit_mouse_hotfix_for_mode_control_click() -> None:
    root = browser_native_extension_dir()
    worker = (root / "service_worker_temporary_chat.js").read_text(encoding="utf-8")

    # The existing hotfix wraps global sendCommand() mouse events to repair
    # submit behavior. Temporary-control probing must use raw CDP commands so a
    # selector click can never trigger the send-button fallback ladder.
    assert "chrome.debugger.sendCommand(debuggee, method, params)" in worker
    assert "_pr87RawSendCommand" in worker
