from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA12 = EXT / "service_worker_rich_input_schema12_repair_pr9_2.js"
GATE12 = PKG / "product_rich_input_live_gate_schema12_pr9_2.py"


def test_schema_12_overlay_is_loaded_after_schema_11():
    text = LOADER.read_text(encoding="utf-8")
    schema11 = 'importScripts("service_worker_rich_input_schema11_repair_pr9_2.js");'
    schema12 = 'importScripts("service_worker_rich_input_schema12_repair_pr9_2.js");'
    assert schema11 in text
    assert schema12 in text
    assert text.index(schema11) < text.index(schema12)


def test_schema_12_bounds_poststage_debugger_setup_and_late_attach_cleanup():
    text = SCHEMA12.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA12_REPAIR_SCHEMA = 12;" in text
    assert '"SCHEMA12_POSTSTAGE_DEBUGGER_ATTACH"' in text
    assert '"SCHEMA12_POSTSTAGE_RUNTIME_ENABLE"' in text
    assert "await _pr92Schema7RunUntil(" in text
    assert "attachPending.then(" in text
    assert "() => _pr92Schema12BestEffortDetach(debuggee)" in text
    assert "postStageDebuggerSetupDeadlineBounded: true" in text
    assert "latePostStageDebuggerAttachAutoDetached: true" in text


def test_schema_12_preserves_clean_staging_and_latest_page_owned_evidence():
    text = SCHEMA12.read_text(encoding="utf-8")
    assert "await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(" in text
    assert "const stagedCount = await _pr92ClosurePriorStageOfficialPageAttachments(" in text
    assert "const pageOwnedCount = await _pr92ClosureWaitForPageOwnedAttachmentEvidence(" in text
    assert "PR92_PAGE_ATTACHMENT_STABLE_POLLS" in text
    assert 'throw new Error("PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH")' in text


def test_schema_12_bounds_the_complete_send_readiness_helper():
    text = SCHEMA12.read_text(encoding="utf-8")
    assert "const _pr92Schema12PriorWaitForSendButtonPoint = waitForSendButtonPoint;" in text
    assert "waitForSendButtonPoint = async function _pr92Schema12DeadlineBoundedSendReadiness(" in text
    assert '"SCHEMA12_SEND_READINESS_WAIT"' in text
    assert "() => _pr92Schema12PriorWaitForSendButtonPoint(debuggee, timeoutMs)" in text
    assert "sendReadinessWaitDeadlineBounded: true" in text


def test_schema_12_gate_rejects_schema_11_and_requires_new_deadline_guarantees():
    text = GATE12.read_text(encoding="utf-8")
    assert "SCHEMA = 12" in text
    assert "class ProductRichInputSchema12LiveProvider" in text
    assert "legacy[\"schema\"] = _v11.SCHEMA" in text
    assert "poststage_debugger_setup_deadline_bounded" in text
    assert "late_poststage_debugger_attach_auto_detached" in text
    assert "send_readiness_wait_deadline_bounded" in text
    assert "PRODUCT_WRITE_BUDGET = _v11.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
