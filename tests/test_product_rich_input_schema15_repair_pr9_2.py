from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA15 = EXT / "service_worker_rich_input_schema15_repair_pr9_2.js"
GATE15 = PKG / "product_rich_input_live_gate_schema15_pr9_2.py"


def test_schema_15_overlay_is_loaded_after_schema_14():
    text = LOADER.read_text(encoding="utf-8")
    schema14 = 'importScripts("service_worker_rich_input_schema14_repair_pr9_2.js");'
    schema15 = 'importScripts("service_worker_rich_input_schema15_repair_pr9_2.js");'
    assert schema14 in text
    assert schema15 in text
    assert text.index(schema14) < text.index(schema15)


def test_schema_15_pre_stage_success_detach_is_deadline_bounded_before_return():
    text = SCHEMA15.read_text(encoding="utf-8")
    start = text.index(
        "_pr92Schema10RequireOfficialCleanComposerBeforeStaging = async function"
    )
    end = text.index(
        "_pr92Schema12ObservePostStageAttachmentEvidence = async function",
        start,
    )
    block = text[start:end]
    detach = '"SCHEMA15_PRESTAGE_CLEAN_DEBUGGER_DETACH"'
    assert "const PR92_SCHEMA15_REPAIR_SCHEMA = 15;" in text
    assert detach in block
    assert "await _pr92Schema15DetachWithinDeadline(" in block
    assert "attached = false;" in block
    success_detached = block.rindex("attached = false;")
    assert block.index(detach) < success_detached
    assert "if (attached) _pr92Schema10BestEffortDetach(debuggee);" in block


def test_schema_15_post_stage_success_detach_is_deadline_bounded_before_evidence_return():
    text = SCHEMA15.read_text(encoding="utf-8")
    start = text.index(
        "_pr92Schema12ObservePostStageAttachmentEvidence = async function"
    )
    end = text.index(
        "executeNativeTurn = async function _executeNativeTurnWithPr92Schema15Repair",
        start,
    )
    block = text[start:end]
    detach = '"SCHEMA15_POSTSTAGE_DEBUGGER_DETACH"'
    assert detach in block
    assert "await _pr92Schema15DetachWithinDeadline(" in block
    assert "attached = false;" in block
    assert "return pageOwnedCount;" in block
    success_detached = block.rindex("attached = false;")
    assert block.index(detach) < success_detached < block.index("return pageOwnedCount;")
    assert "if (attached) _pr92Schema12BestEffortDetach(debuggee);" in block


def test_schema_15_detach_helper_uses_same_outer_deadline():
    text = SCHEMA15.read_text(encoding="utf-8")
    start = text.index("async function _pr92Schema15DetachWithinDeadline")
    end = text.index(
        "_pr92Schema10RequireOfficialCleanComposerBeforeStaging = async function",
        start,
    )
    block = text[start:end]
    assert "_pr92RemainingTurnMs(context, stage);" in block
    assert "_pr92Schema7RunUntil(" in block
    assert "context.deadlineAt" in block
    assert "chrome.debugger.detach(debuggee)" in block


def test_schema_15_support_contract_requires_completed_ownership_handoff():
    text = SCHEMA15.read_text(encoding="utf-8")
    required = [
        "preStageSuccessfulDebuggerDetachDeadlineBounded: true",
        "postStageSuccessfulDebuggerDetachDeadlineBounded: true",
        "debuggerOwnershipHandoffCompletedBeforeNextAttach: true",
        "failurePathDebuggerDetachBestEffort: true",
    ]
    for field in required:
        assert field in text


def test_schema_15_gate_preserves_schema_14_and_requires_both_handoffs():
    text = GATE15.read_text(encoding="utf-8")
    assert "SCHEMA = 15" in text
    assert "class ProductRichInputSchema15LiveProvider" in text
    assert "legacy[\"schema\"] = _v14.SCHEMA" in text
    assert "_v14._validate_support(legacy)" in text
    required = [
        "pre_stage_successful_debugger_detach_deadline_bounded",
        "post_stage_successful_debugger_detach_deadline_bounded",
        "debugger_ownership_handoff_completed_before_next_attach",
        "failure_path_debugger_detach_best_effort",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v14.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_15_support_probe_is_ninth_no_write_characterization_rpc():
    text = GATE15.read_text(encoding="utf-8")
    assert "This ninth characterization-only RPC carries neither text nor paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
