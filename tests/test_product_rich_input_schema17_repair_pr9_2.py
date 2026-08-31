from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA17 = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"
GATE17 = PKG / "product_rich_input_live_gate_schema17_pr9_2.py"


def test_schema_17_overlay_is_loaded_after_schema_16():
    text = LOADER.read_text(encoding="utf-8")
    schema16 = 'importScripts("service_worker_rich_input_schema16_repair_pr9_2.js");'
    schema17 = 'importScripts("service_worker_rich_input_schema17_repair_pr9_2.js");'
    assert schema16 in text
    assert schema17 in text
    assert text.index(schema16) < text.index(schema17)


def test_schema_17_page_turn_attach_is_deadline_bounded_with_late_release():
    text = SCHEMA17.read_text(encoding="utf-8")
    start = text.index("async function _pr92Schema17AttachWithinDeadline")
    end = text.index("async function _pr92Schema17RunUntil", start)
    block = text[start:end]
    assert '"SCHEMA17_PAGE_TURN_DEBUGGER_ATTACH"' in block
    assert "context.deadlineAt" in block
    assert "_pr92Schema7RunUntil(" in block
    assert "chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION)" in block
    assert "attachPending.then(" in block
    assert "_pr92Schema17BestEffortDetach(debuggee)" in block


def test_schema_17_complete_prewrite_page_turn_setup_uses_outer_deadline_runner():
    text = SCHEMA17.read_text(encoding="utf-8")
    start = text.index("async function _pr92Schema17ExecuteOfficialPageTurn")
    end = text.index("let conversationRequestId = null;", start)
    block = text[start:end]
    required_stages = [
        "SCHEMA17_PAGE_TURN_TAB_LOOKUP",
        "SCHEMA17_PAGE_TURN_NETWORK_ENABLE",
        "SCHEMA17_PAGE_TURN_RUNTIME_ENABLE",
        "SCHEMA17_PAGE_TURN_COMPOSER_READY",
    ]
    for stage in required_stages:
        assert f'"{stage}"' in block
    assert "_pr92Schema17AttachWithinDeadline(debuggee, context)" in block
    assert "_pr92Schema17RunUntil(" in block
    assert "() => chrome.tabs.get(tabId)" in block
    assert '() => chrome.debugger.sendCommand(debuggee, "Network.enable")' in block
    assert '() => chrome.debugger.sendCommand(debuggee, "Runtime.enable")' in block
    assert "() => waitForComposerReady(debuggee, readyBudget)" in block


def test_schema_17_composer_mutation_setup_is_outer_deadline_bounded_before_submit():
    text = SCHEMA17.read_text(encoding="utf-8")
    start = text.index("diagnostics.composerStrategy = await _pr92Schema17RunUntil")
    end = text.index("const submitStartedAt", start)
    block = text[start:end]
    required_stages = [
        "SCHEMA17_PAGE_TURN_COMPOSER_FOCUS",
        "SCHEMA17_PAGE_TURN_COMPOSER_CLEAR",
        "SCHEMA17_PAGE_TURN_TEXT_INSERT",
    ]
    for stage in required_stages:
        assert f'"{stage}"' in block
    assert "() => locateAndFocusComposer(debuggee)" in block
    assert "() => clearComposer(debuggee)" in block
    assert '() => chrome.debugger.sendCommand(debuggee, "Input.insertText", { text })' in block


def test_schema_17_postwrite_reads_are_optional_bounded_and_reserve_rpc_return_budget():
    text = SCHEMA17.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS = 1_000;" in text
    assert "const PR92_SCHEMA17_RPC_RETURN_RESERVE_MS = 500;" in text

    helper_start = text.index("async function _pr92Schema17OptionalPostWrite")
    helper_end = text.index("async function _pr92Schema17ExecuteOfficialPageTurn", helper_start)
    helper = text[helper_start:helper_end]
    assert "remaining - PR92_SCHEMA17_RPC_RETURN_RESERVE_MS" in helper
    assert "context.deadlineAt - PR92_SCHEMA17_RPC_RETURN_RESERVE_MS" in helper
    assert "_pr92Schema7RunUntil(localDeadlineAt, stage, operation)" in helper
    assert "return { ok: false, value: null };" in helper

    start = text.index("const requestId = await _pr92Schema17RunUntil")
    end = text.index("const urlConversationId = conversationIdFromUrl(latestUrl);", start)
    block = text[start:end]
    required_stages = [
        "SCHEMA17_POSTWRITE_RESPONSE_BODY",
        "SCHEMA17_POSTWRITE_FINAL_TAB",
        "SCHEMA17_POSTWRITE_COMPOSER_READINESS",
    ]
    for stage in required_stages:
        assert f'"{stage}"' in block
    assert "_pr92Schema17OptionalPostWrite(" in block
    assert "await Promise.all([" in block
    assert '() => chrome.debugger.sendCommand(debuggee, "Network.getResponseBody", { requestId })' in block
    assert "() => chrome.tabs.get(tabId)" in block
    assert "() => waitForComposerReady(debuggee, readinessBudget)" in block
    assert 'await chrome.debugger.sendCommand(debuggee, "Network.getResponseBody"' not in block
    assert "await chrome.tabs.get(tabId)" not in block
    assert "await waitForComposerReady(" not in block


def test_schema_17_tracks_route_without_requiring_postwrite_tab_read_for_identity():
    text = SCHEMA17.read_text(encoding="utf-8")
    start = text.index("tabUpdateListener = (updatedTabId")
    end = text.index("diagnostics.composerStrategy", start)
    block = text[start:end]
    assert "chrome.tabs.onUpdated.addListener(tabUpdateListener);" in block
    assert "latestUrl = changeInfo.url;" in block
    assert "latestUrl = updatedTab.url;" in block
    finalizer = text[text.index("} finally {") :]
    assert "chrome.tabs.onUpdated.removeListener(tabUpdateListener);" in finalizer


def test_schema_17_support_contract_covers_both_fresh_review_findings():
    text = SCHEMA17.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA17_REPAIR_SCHEMA = 17;" in text
    required = [
        "pageTurnPrewriteSetupDeadlineBounded: true",
        "latePageTurnDebuggerAttachAutoDetached: true",
        "postWriteResponseBodyDeadlineBounded: true",
        "postWriteComposerReadinessDeadlineBounded: true",
        "postWriteFinalTabReadDeadlineBounded: true",
        "postWriteOptionalReadsNonAuthoritative: true",
        "postWriteOptionalReadsCanRewriteSubmittedOutcome: false",
        "postWriteRpcReturnReserveMs: PR92_SCHEMA17_RPC_RETURN_RESERVE_MS",
    ]
    for field in required:
        assert field in text


def test_schema_17_gate_preserves_schema_16_and_requires_new_closure_fields():
    text = GATE17.read_text(encoding="utf-8")
    assert "SCHEMA = 17" in text
    assert "class ProductRichInputSchema17LiveProvider" in text
    assert 'legacy["schema"] = _v16.SCHEMA' in text
    assert "_v16._validate_support(legacy)" in text
    required = [
        "page_turn_prewrite_setup_deadline_bounded",
        "late_page_turn_debugger_attach_auto_detached",
        "post_write_response_body_deadline_bounded",
        "post_write_composer_readiness_deadline_bounded",
        "post_write_final_tab_read_deadline_bounded",
        "post_write_optional_reads_non_authoritative",
        "post_write_optional_reads_can_rewrite_submitted_outcome",
        "post_write_rpc_return_reserve_ms",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v16.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_17_support_probe_is_eleventh_no_write_characterization_rpc():
    text = GATE17.read_text(encoding="utf-8")
    assert "This eleventh characterization-only RPC carries neither text nor paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
