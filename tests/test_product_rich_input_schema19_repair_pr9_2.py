from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA19 = EXT / "service_worker_rich_input_schema19_repair_pr9_2.js"
GATE19 = PKG / "product_rich_input_live_gate_schema19_pr9_2.py"


def test_schema_19_overlay_is_loaded_after_schema_18():
    text = LOADER.read_text(encoding="utf-8")
    schema18 = 'importScripts("service_worker_rich_input_schema18_repair_pr9_2.js");'
    schema19 = 'importScripts("service_worker_rich_input_schema19_repair_pr9_2.js");'
    assert schema18 in text
    assert schema19 in text
    assert text.index(schema18) < text.index(schema19)


def test_schema_19_turn_context_records_new_chat_vs_continuation_identity():
    text = SCHEMA19.read_text(encoding="utf-8")
    start = text.index("_pr92CreateTurnContext = function")
    end = text.index("extractSafeStreamMetadata = function", start)
    block = text[start:end]
    assert 'typeof message?.conversationId === "string"' in block
    assert "context.schema19RequestedConversationId = requestedConversationId" in block
    assert "context.schema19CausalConversationId = null" in block
    assert "context.schema19CausalTurnExchangeId = null" in block


def test_schema_19_causal_identity_is_captured_only_from_safe_stream_metadata():
    text = SCHEMA19.read_text(encoding="utf-8")
    start = text.index("extractSafeStreamMetadata = function")
    end = text.index("_pr92Schema17OptionalPostWrite = async function", start)
    block = text[start:end]
    assert "_pr92Schema19PriorExtractSafeStreamMetadata(body, base64Encoded)" in block
    assert "context.schema19CausalConversationId = metadata.conversationId.trim()" in block
    assert "context.schema19CausalTurnExchangeId = metadata.turnExchangeId.trim()" in block
    assert "conversationIdFromUrl" not in block
    assert "chrome.tabs" not in block


def test_schema_19_new_chat_response_body_gets_causal_identity_budget():
    text = SCHEMA19.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA19_CAUSAL_RESPONSE_BODY_CAP_MS = 2_000;" in text
    assert "const PR92_SCHEMA19_RPC_RETURN_RESERVE_MS = 500;" in text
    start = text.index("_pr92Schema17OptionalPostWrite = async function")
    end = text.index("executeOfficialPageTurn = async function", start)
    block = text[start:end]
    assert 'stage === "SCHEMA17_POSTWRITE_RESPONSE_BODY"' in block
    assert "context?.schema19RequestedConversationId == null" in block
    assert "remaining - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS" in block
    assert "context.deadlineAt - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS" in block
    assert "PR92_SCHEMA19_CAUSAL_RESPONSE_BODY_CAP_MS" in block
    assert "_pr92Schema19PriorOptionalPostWrite(context, stage, operation, capMs)" in block


def test_schema_19_new_chat_bypasses_schema_18_route_identity_fallback():
    text = SCHEMA19.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "if (context.schema19RequestedConversationId !== null)" in block
    assert "return _pr92Schema19PriorExecuteOfficialPageTurn(args);" in block
    assert "const result = await _pr92Schema18PriorExecuteOfficialPageTurn(args);" in block
    assert "_pr92Schema18ResolvePostWriteConversationIdentity" not in block
    assert "chrome.tabs.onUpdated" not in block
    assert "chrome.tabs.get" not in block


def test_schema_19_route_can_neither_satisfy_nor_override_new_chat_identity():
    text = SCHEMA19.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "const causalConversationId" in block
    assert "if (!causalConversationId)" in block
    assert "throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);" in block
    assert "const routeConversationId = conversationIdFromUrl" in block
    assert "const routeMatchesCausalIdentity = routeConversationId === causalConversationId" in block
    assert "finalUrl: routeMatchesCausalIdentity ? result.finalUrl : null" in block
    assert "conversationId: causalConversationId" in block
    assert "routeConversationIdentityAuthoritative: false" in block
    assert "routeConversationId: routeConversationId || null" in block
    assert "routeMatchesCausalIdentity," in block
    assert block.index("if (!causalConversationId)") < block.index(
        "const routeConversationId = conversationIdFromUrl"
    )


def test_schema_19_completed_write_proof_remains_required_before_identity_success():
    text = SCHEMA19.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "result?.diagnostics?.conversationRequestSeen !== true" in block
    assert "result?.diagnostics?.loadingFinished !== true" in block
    assert "PR9_2_CONVERSATION_ID_MISSING_WITHOUT_WRITE_COMPLETION_PROOF" in block
    assert block.index("conversationRequestSeen") < block.index("const causalConversationId")


def test_schema_19_support_contract_denies_route_identity_authority():
    text = SCHEMA19.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA19_REPAIR_SCHEMA = 19;" in text
    assert '"NETWORK_REQUEST_BOUND_STREAM_HANDOFF"' in text
    required = [
        "newChatConversationIdentityAuthority: PR92_SCHEMA19_IDENTITY_AUTHORITY",
        "responseBodyConversationIdentityRequestBound: true",
        "routeConversationIdentityAuthoritative: false",
        "manualRouteNavigationCanSatisfyNewChatIdentity: false",
        "causalConversationIdentityReadDeadlineBounded: true",
        "causalConversationIdentityRpcReturnReserveMs: PR92_SCHEMA19_RPC_RETURN_RESERVE_MS",
        "missingRequestBoundConversationIdentitySignalsCommittedReadbackIncomplete: true",
        "automaticWriteRetryAfterCausalIdentityFailure: false",
    ]
    for field in required:
        assert field in text


def test_schema_19_gate_preserves_schema_18_and_requires_causal_identity_fields():
    text = GATE19.read_text(encoding="utf-8")
    assert "SCHEMA = 19" in text
    assert "class ProductRichInputSchema19LiveProvider" in text
    assert 'legacy["schema"] = _v18.SCHEMA' in text
    assert "_v18._validate_support(legacy)" in text
    required = [
        "new_chat_conversation_identity_authority",
        "response_body_conversation_identity_request_bound",
        "route_conversation_identity_authoritative",
        "manual_route_navigation_can_satisfy_new_chat_identity",
        "causal_conversation_identity_read_deadline_bounded",
        "causal_conversation_identity_rpc_return_reserve_ms",
        "missing_request_bound_conversation_identity_signals_committed_readback_incomplete",
        "automatic_write_retry_after_causal_identity_failure",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v18.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_19_support_probe_is_thirteenth_no_write_characterization_rpc():
    text = GATE19.read_text(encoding="utf-8")
    assert "Thirteenth characterization-only RPC: no text and no attachment paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
