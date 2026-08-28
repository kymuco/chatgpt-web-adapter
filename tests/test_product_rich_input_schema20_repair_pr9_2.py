from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA7 = EXT / "service_worker_rich_input_schema7_core_pr9_2.js"
SCHEMA17 = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"
SCHEMA20 = EXT / "service_worker_rich_input_schema20_repair_pr9_2.js"
GATE20 = PKG / "product_rich_input_live_gate_schema20_pr9_2.py"


def test_schema_20_overlay_is_loaded_after_schema_19():
    text = LOADER.read_text(encoding="utf-8")
    schema19 = 'importScripts("service_worker_rich_input_schema19_repair_pr9_2.js");'
    schema20 = 'importScripts("service_worker_rich_input_schema20_repair_pr9_2.js");'
    assert schema19 in text
    assert schema20 in text
    assert text.index(schema19) < text.index(schema20)


def test_schema_20_turn_context_has_unique_page_side_arm_state():
    text = SCHEMA20.read_text(encoding="utf-8")
    assert "PR92_SCHEMA20_ARM_MARKER_PREFIX" in text
    assert "schema20ProtectedSubmitMarker = _pr92Schema20RandomMarker()" in text
    assert "schema20ProtectedSubmitMarkerObserved = false" in text
    assert "schema20ProtectedSubmitArmed = false" in text
    assert "schema20PostArmConversationRequests = []" in text


def test_schema_20_arm_marker_and_atomic_click_share_one_page_expression():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("_pr92Schema7AtomicAttachmentSubmitExpression = function")
    end = text.index("isConversationWrite = function", start)
    block = text[start:end]
    assert "_pr92Schema20PriorAtomicAttachmentSubmitExpression" in block
    assert "console.debug(${encodedMarker})" in block
    assert "return (${expression});" in block
    assert "await " not in block

    schema7 = SCHEMA7.read_text(encoding="utf-8")
    submit_start = schema7.index("const expression = _pr92Schema7AtomicAttachmentSubmitExpression")
    dispatch = schema7.index(
        'chrome.debugger.sendCommand(debuggee, "Runtime.evaluate"', submit_start
    )
    between = schema7[submit_start:dispatch]
    assert "await " not in between


def test_schema_20_schema17_request_authority_is_closed_before_page_marker():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("isConversationWrite = function")
    end = text.index("function _pr92Schema20ObserveArmMarker", start)
    block = text[start:end]
    assert "_pr92Schema20PriorIsConversationWrite(url, method)" in block
    assert "context.schema20ProtectedSubmitArmed === true" in block

    schema17 = SCHEMA17.read_text(encoding="utf-8")
    listener_start = schema17.index('if (method === "Network.requestWillBeSent")')
    listener_end = schema17.index("return;", listener_start) + len("return;")
    listener = schema17[listener_start:listener_end]
    assert "isConversationWrite(request?.url || \"\", request?.method || \"\")" in listener


def test_schema_20_only_exact_runtime_console_marker_arms_authority():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema20ObserveArmMarker")
    end = text.index("function _pr92Schema20RecordPostArmConversationRequest", start)
    block = text[start:end]
    assert "const expected = context.schema20ProtectedSubmitMarker" in block
    assert "args.some((arg) => arg?.value === expected)" in block
    assert "context.schema20ProtectedSubmitMarkerObserved = true" in block
    assert "context.schema20ProtectedSubmitArmed = true" in block


def test_schema_20_raw_observer_records_post_arm_requests_independently_of_gated_predicate():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema20RecordPostArmConversationRequest")
    end = text.index("executeOfficialPageTurn = async function", start)
    block = text[start:end]
    assert "context.schema20ProtectedSubmitArmed !== true" in block
    assert "_pr92Schema20PriorIsConversationWrite(" in block
    assert "_pr92Schema20SubmitBoundConversationWrite" not in block
    assert "hasUserGesture: params?.hasUserGesture === true" in block
    assert "entry.requestId === requestId" in block


def test_schema_20_success_requires_one_non_user_gesture_request_after_marker():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert 'method === "Runtime.consoleAPICalled"' in block
    assert 'method === "Network.requestWillBeSent"' in block
    assert "const markerObserved = context.schema20ProtectedSubmitMarkerObserved === true" in block
    assert "const exactlyOnePostArmRequest = observed.length === 1" in block
    assert "const soleRequestHasUserGesture = soleRequest?.hasUserGesture === true" in block
    assert "!markerObserved || !exactlyOnePostArmRequest || soleRequestHasUserGesture" in block
    assert "throw new Error(PR92_SCHEMA18_COMMITTED_IDENTITY_ERROR)" in block


def test_schema_20_ambiguous_request_correlation_cannot_trigger_retry():
    text = SCHEMA20.read_text(encoding="utf-8")
    assert "ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: true" in text
    assert "automaticWriteRetryAfterSubmitCorrelationFailure: false" in text
    assert "retry" not in text[text.index("executeOfficialPageTurn = async function"):text.index("executeNativeTurn = async function")].lower().replace("never retry", "")


def test_schema_20_request_id_is_returned_only_as_diagnostic_after_correlation():
    text = SCHEMA20.read_text(encoding="utf-8")
    start = text.index("return {\n      ...result,", text.index("executeOfficialPageTurn = async function"))
    end = text.index("};\n  } finally", start)
    block = text[start:end]
    assert "protectedSubmitRequestId: soleRequest.requestId" in block
    assert "postArmConversationRequestCount: observed.length" in block
    assert "protectedSubmitRequestHadUserGesture: false" in block
    assert "preArmConversationRequestsAuthoritative: false" in block


def test_schema_20_support_contract_advertises_submit_bound_request_authority():
    text = SCHEMA20.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA20_REPAIR_SCHEMA = 20;" in text
    assert '"PAGE_SIDE_ARMED_SINGLE_CONVERSATION_POST"' in text
    assert '"PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF"' in text
    required = [
        "protectedSubmitRequestArmedByPageSideMarker: true",
        "pageSideArmMarkerAndProtectedClickSameTask: true",
        "preArmConversationRequestsAuthoritative: false",
        "exactlyOnePostArmConversationRequestRequired: true",
        "userGesturePostArmRequestCanSatisfyProtectedSubmit: false",
        "ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete: true",
        "automaticWriteRetryAfterSubmitCorrelationFailure: false",
    ]
    for field in required:
        assert field in text


def test_schema_20_gate_preserves_schema_19_and_requires_new_fields():
    text = GATE20.read_text(encoding="utf-8")
    assert "SCHEMA = 20" in text
    assert "class ProductRichInputSchema20LiveProvider" in text
    assert 'legacy["schema"] = _v19.SCHEMA' in text
    assert 'legacy["new_chat_conversation_identity_authority"] = _SCHEMA19_IDENTITY_AUTHORITY' in text
    assert "_v19._validate_support(legacy)" in text
    required = [
        "protected_submit_request_correlation",
        "protected_submit_request_armed_by_page_side_marker",
        "page_side_arm_marker_and_protected_click_same_task",
        "pre_arm_conversation_requests_authoritative",
        "exactly_one_post_arm_conversation_request_required",
        "user_gesture_post_arm_request_can_satisfy_protected_submit",
        "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete",
        "automatic_write_retry_after_submit_correlation_failure",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v19.PRODUCT_WRITE_BUDGET" in text


def test_schema_20_support_probe_is_fourteenth_no_write_characterization_rpc():
    text = GATE20.read_text(encoding="utf-8")
    assert "Fourteenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
