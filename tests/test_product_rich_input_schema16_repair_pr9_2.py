from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA16 = EXT / "service_worker_rich_input_schema16_repair_pr9_2.js"
GATE16 = PKG / "product_rich_input_live_gate_schema16_pr9_2.py"


def test_schema_16_overlay_is_loaded_after_schema_15():
    text = LOADER.read_text(encoding="utf-8")
    schema15 = 'importScripts("service_worker_rich_input_schema15_repair_pr9_2.js");'
    schema16 = 'importScripts("service_worker_rich_input_schema16_repair_pr9_2.js");'
    assert schema15 in text
    assert schema16 in text
    assert text.index(schema15) < text.index(schema16)


def test_schema_16_durable_fence_read_is_raced_against_outer_deadline():
    text = SCHEMA16.read_text(encoding="utf-8")
    start = text.index(
        "_pr92ReadDirtyAttachmentFence = async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline"
    )
    end = text.index("ensureRuntimeTab = async function", start)
    block = text[start:end]
    assert '"SCHEMA16_STALE_ATTACHMENT_FENCE_READ"' in block
    assert "context.deadlineAt" in block
    assert "_pr92Schema7RunUntil(" in block
    assert "() => chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY)" in block
    assert "if (_pr92DeadlineRepairIsTimeoutError(error)) throw error;" in block


def test_schema_16_rich_runtime_tab_acquisition_is_complete_helper_deadline_race():
    text = SCHEMA16.read_text(encoding="utf-8")
    start = text.index("ensureRuntimeTab = async function _pr92Schema16EnsureRuntimeTabWithinRichDeadline")
    end = text.index("function _pr92Schema16DispatchPostWriteDebuggerTeardown", start)
    block = text[start:end]
    assert "const context = _pr92ActiveRichInputContext;" in block
    assert "if (context === null)" in block
    assert '"SCHEMA16_RUNTIME_TAB_ACQUISITION"' in block
    assert "context.deadlineAt" in block
    assert "() => _pr92Schema16PriorEnsureRuntimeTab(conversationId)" in block


def test_schema_16_post_write_debugger_teardown_is_best_effort_and_non_awaited():
    text = SCHEMA16.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema16DispatchPostWriteDebuggerTeardown")
    end = text.index("async function _pr92Schema16ExecuteOfficialPageTurn", start)
    block = text[start:end]
    assert "chrome.debugger.detach(debuggee)" in block
    assert "chrome.debugger.getTargets()" in block
    assert ".catch(() => {})" in block
    assert "await " not in block


def test_schema_16_page_turn_switches_teardown_authority_after_network_post_proof():
    text = SCHEMA16.read_text(encoding="utf-8")
    start = text.index("async function _pr92Schema16ExecuteOfficialPageTurn")
    end = text.index("executeOfficialPageTurn = async function", start)
    block = text[start:end]
    assert 'method === "Network.requestWillBeSent"' in block
    assert "diagnostics.conversationRequestSeen = true;" in block
    finalizer = block[block.index("} finally {") :]
    assert "if (diagnostics.conversationRequestSeen === true)" in finalizer
    assert "_pr92Schema16DispatchPostWriteDebuggerTeardown(debuggee);" in finalizer
    assert "diagnostics.debuggerAttachedAfter = null;" in finalizer
    assert '"SCHEMA16_PREWRITE_PAGE_TURN_DEBUGGER_DETACH"' in finalizer
    assert '"SCHEMA16_PREWRITE_PAGE_TURN_DEBUGGER_TARGETS"' in finalizer


def test_schema_16_support_contract_covers_all_three_review_findings():
    text = SCHEMA16.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA16_REPAIR_SCHEMA = 16;" in text
    required = [
        "durableFenceReadDeadlineBounded: true",
        "runtimeTabAcquisitionDeadlineBounded: true",
        "inheritedPageTurnPostWriteTeardownNonBlocking: true",
        "postWriteDebuggerDetachBestEffort: true",
        "postWriteDebuggerTargetsProbeBestEffort: true",
        "postWriteTeardownCanRewriteSubmittedOutcome: false",
    ]
    for field in required:
        assert field in text


def test_schema_16_gate_preserves_schema_15_and_requires_new_closure_fields():
    text = GATE16.read_text(encoding="utf-8")
    assert "SCHEMA = 16" in text
    assert "class ProductRichInputSchema16LiveProvider" in text
    assert 'legacy["schema"] = _v15.SCHEMA' in text
    assert "_v15._validate_support(legacy)" in text
    required = [
        "durable_fence_read_deadline_bounded",
        "runtime_tab_acquisition_deadline_bounded",
        "inherited_page_turn_post_write_teardown_non_blocking",
        "post_write_debugger_detach_best_effort",
        "post_write_debugger_targets_probe_best_effort",
        "post_write_teardown_can_rewrite_submitted_outcome",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v15.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_16_support_probe_is_tenth_no_write_characterization_rpc():
    text = GATE16.read_text(encoding="utf-8")
    assert "This tenth characterization-only RPC carries neither text nor paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
