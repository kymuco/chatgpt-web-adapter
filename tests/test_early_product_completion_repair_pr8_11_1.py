from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RECOVERY = EXTENSION / "service_worker_recovery.js"
REPAIR = EXTENSION / "service_worker_early_product_completion_repair_pr8_11_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_repair_overlay_loads_after_characterization() -> None:
    source = _read(OBSERVABILITY)
    characterization = 'importScripts("service_worker_early_product_completion_pr8_11_1.js");'
    repair = 'importScripts("service_worker_early_product_completion_repair_pr8_11_1.js");'
    assert characterization in source and repair in source
    assert source.index(characterization) < source.index(repair)


def test_core_page_boundary_is_fail_closed() -> None:
    source = _read(RECOVERY)
    assert "_cwaInstallOfficialPageEarlyCompletionSignal" in source
    assert 'kind: "assistant_terminal_candidate"' in source
    assert 'kind: "network_complete"' in source
    assert "diagnostics.conversationResponseSeen !== true" in source
    assert "diagnostics.responseStatus !== 200" in source
    assert '"conversation_route_not_resolved"' in source
    assert 'diagnostics.completionBoundary = "assistant_terminal"' in source
    assert 'diagnostics.completionBoundary = "network_loading_finished"' in source


def test_network_fallback_preserves_response_body_and_composer_proof() -> None:
    source = _read(RECOVERY)
    start = source.index("if (diagnostics.earlyCompletionAccepted !== true)")
    end = source.index("\n    diagnostics.elapsedMs", start)
    fallback = source[start:end]
    assert 'Network.getResponseBody' in fallback
    assert "extractSafeStreamMetadata" in fallback
    assert "waitForComposerReady(" in fallback
    assert "completed" in fallback


def test_accepted_early_boundary_skips_post_network_waits() -> None:
    source = _read(RECOVERY)
    candidate_start = source.index('if (firstBoundary?.kind === "assistant_terminal_candidate")')
    fallback_start = source.index("if (diagnostics.earlyCompletionAccepted !== true)", candidate_start)
    candidate = source[candidate_start:fallback_start]
    assert 'diagnostics.earlyCompletionAccepted = true' in candidate
    assert "Network.getResponseBody" not in candidate
    assert "waitForComposerReady(" not in candidate


def test_early_repair_requires_conjunctive_current_answer_terminal_proof() -> None:
    source = _read(REPAIR)
    assert "firstVisibleAssistantTextAt" in source
    assert "previous === text" in source
    assert 'active.terminalKind = "assistant_terminal_conjunction"' in source
    assert 'completionEvidence !== "end_turn"' in source
    assert 'completionEvidence !== "is_complete"' in source
    assert 'completionEvidence !== "end_turn+is_complete"' in source
    assert "finishCurrent" in source
    assert "endTurnCurrent" in source
    assert "isCompleteCurrent" in source
    assert "finishReason !== null && finishCurrent && (endTurnCurrent || isCompleteCurrent)" in source


def test_terminal_decision_runs_after_established_sse_processing() -> None:
    source = _read(REPAIR)
    start = source.index("_pr89BrowserStreamProcessSseEvent = async function")
    end = source.index("\n// Generic status", start)
    block = source[start:end]
    prior_index = block.index("await _pr8111RepairPriorProcessSseEvent")
    decision_index = block.index("finishReason !== null && finishCurrent")
    assert prior_index < decision_index


def test_pre_text_completed_status_cannot_be_earliest_terminal() -> None:
    source = _read(REPAIR)
    start = source.index("_pr8111FirstTerminal = function")
    end = source.index("\nexecuteOfficialPageTurn =", start)
    block = source[start:end]
    assert "const firstText = context?.firstAssistantTextObservedAt" in block
    assert "at >= firstText" in block
    assert '"assistant_completed_status"' in block


def test_repair_installs_signal_only_around_current_page_turn() -> None:
    source = _read(REPAIR)
    start = source.index("executeOfficialPageTurn = async function")
    end = source.index("\nfunction _pr8111RepairLeaseId", start)
    block = source[start:end]
    assert "_cwaInstallOfficialPageEarlyCompletionSignal(active.terminalPromise)" in block
    assert "finally" in block
    assert "restore();" in block


def test_repair_does_not_add_write_or_retry_operations() -> None:
    source = _read(REPAIR)
    assert "Input.insertText" not in source
    assert "Input.dispatchMouseEvent" not in source
    assert "Input.dispatchKeyEvent" not in source
    assert "submitOfficialPageTurn" not in source
    assert "retry" not in source.lower()
