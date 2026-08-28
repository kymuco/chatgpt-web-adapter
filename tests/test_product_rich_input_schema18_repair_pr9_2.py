from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA18 = EXT / "service_worker_rich_input_schema18_repair_pr9_2.js"
GATE18 = PKG / "product_rich_input_live_gate_schema18_pr9_2.py"
PROVIDER = PKG / "browser_native_provider.py"


def test_schema_18_overlay_is_loaded_after_schema_17():
    text = LOADER.read_text(encoding="utf-8")
    schema17 = 'importScripts("service_worker_rich_input_schema17_repair_pr9_2.js");'
    schema18 = 'importScripts("service_worker_rich_input_schema18_repair_pr9_2.js");'
    assert schema17 in text
    assert schema18 in text
    assert text.index(schema17) < text.index(schema18)


def test_schema_18_optional_postwrite_work_preserves_dedicated_identity_reserve():
    text = SCHEMA18.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA18_IDENTITY_RESERVE_MS = 2_500;" in text
    start = text.index("_pr92Schema17OptionalPostWrite = async function")
    end = text.index("function _pr92Schema18ConversationIdentityFromUrl", start)
    block = text[start:end]
    assert "remaining - PR92_SCHEMA18_IDENTITY_RESERVE_MS" in block
    assert "context.deadlineAt - PR92_SCHEMA18_IDENTITY_RESERVE_MS" in block
    assert "_pr92Schema7RunUntil(localDeadlineAt, stage, operation)" in block


def test_schema_18_identity_resolution_is_deadline_bounded_and_has_no_write_primitive():
    text = SCHEMA18.read_text(encoding="utf-8")
    start = text.index("async function _pr92Schema18ResolvePostWriteConversationIdentity")
    end = text.index("executeOfficialPageTurn = async function", start)
    block = text[start:end]
    assert "chrome.tabs.onUpdated.addListener(routeListener);" in block
    assert "chrome.tabs.onUpdated.removeListener(routeListener);" in block
    assert '"SCHEMA18_POSTWRITE_CONVERSATION_ID_TAB_READ"' in block
    assert "_pr92Schema7RunUntil(" in block
    assert "context.deadlineAt - PR92_SCHEMA18_RPC_RETURN_RESERVE_MS" in block
    assert "() => chrome.tabs.get(tabId)" in block
    assert "conversationIdFromUrl" in text
    for forbidden in [
        "button.click()",
        "DOM.setFileInputFiles",
        "Input.insertText",
        "submitOfficialPageTurn",
    ]:
        assert forbidden not in block


def test_schema_18_success_requires_real_identity_after_write_completion_proof():
    text = SCHEMA18.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "result?.diagnostics?.conversationRequestSeen !== true" in block
    assert "result?.diagnostics?.loadingFinished !== true" in block
    assert "_pr92Schema18ResolvePostWriteConversationIdentity(" in block
    assert "conversationId: resolved.conversationId" in block
    assert "PR9_2_CONVERSATION_ID_MISSING_WITHOUT_WRITE_COMPLETION_PROOF" in block


def test_schema_18_unresolved_identity_is_explicit_committed_failure_not_success():
    text = SCHEMA18.read_text(encoding="utf-8")
    assert '"PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED"' in text
    resolver_start = text.index("async function _pr92Schema18ResolvePostWriteConversationIdentity")
    resolver_end = text.index("executeOfficialPageTurn = async function", resolver_start)
    resolver = text[resolver_start:resolver_end]
    assert "throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);" in resolver

    native_start = text.index("executeNativeTurn = async function")
    native = text[native_start:]
    assert "detail.includes(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR)" in native
    assert "throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR);" in native
    assert "missingConversationIdentityCanReturnTransportSuccess: false" in native
    assert "unresolvedConversationIdentitySignalsCommittedReadbackIncomplete: true" in native
    assert "automaticWriteRetryAfterIdentityFailure: false" in native


def test_provider_maps_committed_identity_failure_to_readback_incomplete_timeout_semantics():
    text = PROVIDER.read_text(encoding="utf-8")
    assert "from .exceptions import ConversationTimeoutError, RequestError" in text
    start = text.index('if not response.get("ok"):')
    end = text.index("result_conversation_id = response.get", start)
    block = text[start:end]
    assert 'error.startswith("PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED")' in block
    assert "raise ConversationTimeoutError(" in block
    assert 'last_status="browser_native_write_completed_identity_unresolved"' in block
    assert block.index("raise ConversationTimeoutError(") < block.index(
        'raise RequestError(error, request_stage="browser_native_turn")'
    )


def test_schema_18_support_contract_covers_identity_authority_finding():
    text = SCHEMA18.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA18_REPAIR_SCHEMA = 18;" in text
    required = [
        "newChatConversationIdentityRequiredBeforeSuccess: true",
        "postWriteConversationIdentityResolutionDeadlineBounded: true",
        "postWriteConversationIdentityDedicatedReserveMs: PR92_SCHEMA18_IDENTITY_RESERVE_MS",
        "missingConversationIdentityCanReturnTransportSuccess: false",
        "unresolvedConversationIdentitySignalsCommittedReadbackIncomplete: true",
        "automaticWriteRetryAfterIdentityFailure: false",
    ]
    for field in required:
        assert field in text


def test_schema_18_gate_preserves_schema_17_and_requires_identity_fields():
    text = GATE18.read_text(encoding="utf-8")
    assert "SCHEMA = 18" in text
    assert "class ProductRichInputSchema18LiveProvider" in text
    assert 'legacy["schema"] = _v17.SCHEMA' in text
    assert "_v17._validate_support(legacy)" in text
    required = [
        "new_chat_conversation_identity_required_before_success",
        "post_write_conversation_identity_resolution_deadline_bounded",
        "post_write_conversation_identity_dedicated_reserve_ms",
        "missing_conversation_identity_can_return_transport_success",
        "unresolved_conversation_identity_signals_committed_readback_incomplete",
        "automatic_write_retry_after_identity_failure",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v17.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_18_support_probe_is_twelfth_no_write_characterization_rpc():
    text = GATE18.read_text(encoding="utf-8")
    assert "This twelfth characterization-only RPC carries neither text nor paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
