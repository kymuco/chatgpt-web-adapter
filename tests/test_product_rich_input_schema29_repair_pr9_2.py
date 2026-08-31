from __future__ import annotations

import json
from pathlib import Path
import subprocess

from chatgpt_web_adapter import product_rich_input_live_gate_schema29_pr9_2 as gate29


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA28 = EXT / "service_worker_rich_input_schema28_repair_pr9_2.js"
SCHEMA29 = EXT / "service_worker_rich_input_schema29_repair_pr9_2.js"
GATE29 = PKG / "product_rich_input_live_gate_schema29_pr9_2.py"


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def _response_parser_source() -> str:
    schema28 = SCHEMA28.read_text(encoding="utf-8")
    decode_start = schema28.index("function _pr92Schema28DecodeResponseBody")
    decode_end = schema28.index(
        "function _pr92Schema28ExtractRequestBoundStreamMetadata", decode_start
    )
    decode = schema28[decode_start:decode_end]

    schema29 = SCHEMA29.read_text(encoding="utf-8")
    start = schema29.index("function _pr92Schema29NonEmptyString")
    end = schema29.index(
        "function _pr92Schema29RequestMessageAttachmentChannels", start
    )
    return decode + "\n" + schema29[start:end]


def _request_correlation_source() -> str:
    schema29 = SCHEMA29.read_text(encoding="utf-8")
    start = schema29.index("function _pr92Schema29NonEmptyString")
    end = schema29.index("extractSafeStreamMetadata = function", start)
    return "const PR92_SCHEMA29_POSTDATA_SETTLE_CAP_MS = 1000;\n" + schema29[start:end]


def _run_response_parser_cases() -> dict[str, object]:
    source = _response_parser_source()
    return _run_node(
        f"""
{source}
const cid = "11111111-2222-3333-4444-555555555555";
const other = "99999999-8888-7777-6666-555555555555";
const turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const resumeOnly = `data: {{"type":"resume_conversation_token","conversation_id":"${{cid}}"}}\n`;
const messageOnly = `data: {{"message":{{"id":"m1"}},"conversation_id":"${{cid}}"}}\n`;
const rootAddOnly = `data: {{"p":"","o":"add","v":{{"message":{{"id":"m1"}},"conversation_id":"${{cid}}"}},"c":1}}\n`;
const topAndRootSame = `data: {{"type":"message_marker","conversation_id":"${{cid}}"}}\ndata: {{"p":"","o":"add","v":{{"conversation_id":"${{cid}}"}}}}\n`;
const oldHandoff = `data: {{"type":"resume_conversation_token","conversation_id":"${{cid}}"}}\ndata: {{"type":"stream_handoff","conversation_id":"${{cid}}","turn_exchange_id":"${{turn}}"}}\n`;
const nestedOnly = `data: {{"type":"message","message":{{"conversation_id":"${{cid}}"}}}}\n`;
const conflict = `data: {{"type":"message","conversation_id":"${{cid}}"}}\ndata: {{"p":"","o":"add","v":{{"conversation_id":"${{other}}"}}}}\n`;
const encoded = Buffer.from(rootAddOnly, "utf8").toString("base64");
console.log(JSON.stringify({{
  resumeOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(resumeOnly, false),
  messageOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(messageOnly, false),
  rootAddOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(rootAddOnly, false),
  topAndRootSame: _pr92Schema29ExtractRequestBoundConversationMetadata(topAndRootSame, false),
  oldHandoff: _pr92Schema29ExtractRequestBoundConversationMetadata(oldHandoff, false),
  nestedOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(nestedOnly, false),
  conflict: _pr92Schema29ExtractRequestBoundConversationMetadata(conflict, false),
  base64: _pr92Schema29ExtractRequestBoundConversationMetadata(encoded, true)
}}));
"""
    )


def _run_request_match_cases() -> dict[str, object]:
    source = _request_correlation_source()
    return _run_node(
        f"""
{source}
const prompt = "inspect this attachment exactly";
const cid = "11111111-2222-3333-4444-555555555555";
const image = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-image",
    author: {{role: "user"}},
    content: {{
      content_type: "multimodal_text",
      parts: [
        {{content_type: "image_asset_pointer", asset_pointer: "sediment://file-image"}},
        prompt
      ]
    }},
    metadata: {{}}
  }}]
}});
const generalFile = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-file",
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [prompt]}},
    metadata: {{attachments: [{{id: "file-1", name: "evidence.txt"}}]}}
  }}]
}});
const bothChannels = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-both",
    author: {{role: "user"}},
    content: {{
      content_type: "multimodal_text",
      parts: [{{asset_pointer: "sediment://file-1"}}, prompt]
    }},
    metadata: {{attachments: [{{id: "file-1"}}]}}
  }}]
}});
const continuation = JSON.stringify({{
  action: "next",
  conversation_id: cid,
  messages: [{{
    id: "msg-cont",
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [prompt]}},
    metadata: {{attachments: [{{id: "file-2"}}]}}
  }}]
}});
const wrongText = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-wrong-text",
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [{{asset_pointer: "sediment://file-1"}}, "other"]}}
  }}]
}});
const wrongCount = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-wrong-count",
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [
      {{asset_pointer: "sediment://file-1"}},
      {{asset_pointer: "sediment://file-2"}},
      prompt
    ]}}
  }}]
}});
const newChatWithConversation = JSON.stringify({{
  action: "next",
  conversation_id: cid,
  messages: [{{
    id: "msg-new-with-cid",
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [{{asset_pointer: "sediment://file-1"}}, prompt]}}
  }}]
}});
const missingMessageId = JSON.stringify({{
  action: "next",
  messages: [{{
    author: {{role: "user"}},
    content: {{content_type: "multimodal_text", parts: [{{asset_pointer: "sediment://file-1"}}, prompt]}}
  }}]
}});
const multiUserSameText = JSON.stringify({{
  action: "next",
  messages: [
    {{id: "m1", author: {{role: "user"}}, content: {{parts: [{{asset_pointer: "sediment://a"}}, prompt]}}}},
    {{id: "m2", author: {{role: "user"}}, content: {{parts: [{{asset_pointer: "sediment://b"}}, prompt]}}}}
  ]
}});
const run = (body, count, expectedCid = null) =>
  _pr92Schema29InspectRequestPostData(body, prompt, count, expectedCid);
console.log(JSON.stringify({{
  image: run(image, 1),
  generalFile: run(generalFile, 1),
  bothChannels: run(bothChannels, 1),
  continuation: run(continuation, 1, cid),
  continuationWrongId: run(continuation, 1, "other"),
  wrongText: run(wrongText, 1),
  wrongCount: run(wrongCount, 1),
  newChatWithConversation: run(newChatWithConversation, 1),
  missingMessageId: run(missingMessageId, 1),
  missingPostData: run(null, 1),
  malformedJson: run("not-json", 1),
  multiUserSameText: run(multiUserSameText, 1)
}}));
"""
    )


def _run_correlation_cases() -> dict[str, object]:
    source = _request_correlation_source()
    return _run_node(
        f"""
{source}
const diagnostics = (exact=1) => ({{
  postDataPresent: true,
  requestJsonParsed: true,
  actionNext: true,
  conversationIdentityMatches: true,
  userMessageCount: exact ? 1 : 0,
  userMessageIdCount: exact ? 1 : 0,
  exactTextUserMessageCount: exact,
  exactRichUserMessageCount: exact,
  requestMessageIdPresent: Boolean(exact),
  pointerPartCount: exact ? 1 : 0,
  metadataAttachmentCount: 0,
  attachmentEvidenceChannelCount: exact ? 1 : 0,
  attachmentCountsMatch: Boolean(exact)
}});
const matched = (id, gesture=false) => ({{
  requestId: "r-" + id,
  hasUserGesture: gesture,
  matched: true,
  logicalMessageId: id,
  logicalUserMessageIds: [id],
  diagnostics: diagnostics(1),
  requestBodyResolved: true,
  requestBodySource: "request-event-post-data"
}});
const service = {{
  requestId: "r-service",
  hasUserGesture: false,
  matched: false,
  logicalMessageId: null,
  logicalUserMessageIds: [],
  diagnostics: diagnostics(0),
  requestBodyResolved: true,
  requestBodySource: "request-event-post-data"
}};
const foreignUser = {{
  requestId: "r-foreign",
  hasUserGesture: false,
  matched: false,
  logicalMessageId: null,
  logicalUserMessageIds: ["manual-message"],
  diagnostics: diagnostics(0),
  requestBodyResolved: true,
  requestBodySource: "request-event-post-data"
}};
const unresolved = {{
  requestId: "r-unresolved",
  hasUserGesture: false,
  matched: false,
  logicalMessageId: null,
  logicalUserMessageIds: [],
  diagnostics: null,
  requestBodyResolved: false,
  requestBodySource: "unresolved"
}};
const evaluate = (requests, marker=true) => _pr92Schema29EvaluateSubmitCorrelation({{
  schema20ProtectedSubmitMarkerObserved: marker,
  schema29PostArmConversationRequests: requests
}});
console.log(JSON.stringify({{
  one: evaluate([matched("m1")]),
  gesture: evaluate([matched("m1", true)]),
  extraService: evaluate([matched("m1"), service, service]),
  duplicateSameLogical: evaluate([matched("m1"), matched("m1")]),
  distinctMatching: evaluate([matched("m1"), matched("m2")]),
  foreignUser: evaluate([matched("m1"), foreignUser]),
  firstServiceThenMatch: evaluate([service, matched("m1")]),
  unresolved: evaluate([matched("m1"), unresolved]),
  noMarker: evaluate([matched("m1")], false)
}}));
"""
    )


def _run_postdata_fallback_cases() -> dict[str, object]:
    source = _request_correlation_source()
    return _run_node(
        f"""
const PR92_SCHEMA19_RPC_RETURN_RESERVE_MS = 500;
const _pr92Schema20PriorIsConversationWrite = () => true;
function _pr92Schema28DecodeResponseBody(body, base64Encoded) {{
  if (typeof body !== "string") return null;
  return base64Encoded ? Buffer.from(body, "base64").toString("utf8") : body;
}}
function _pr92RemainingTurnMsOrZero() {{ return 5000; }}
function _pr92Schema7RunUntil(_deadline, _stage, operation) {{ return Promise.resolve().then(operation); }}
const performance = {{ now: () => 1000 }};
{source}
const prompt = "inspect this attachment exactly";
const body = JSON.stringify({{
  action: "next",
  messages: [{{
    id: "msg-fallback",
    author: {{role: "user"}},
    content: {{parts: [{{asset_pointer: "sediment://file"}}, prompt]}}
  }}]
}});
async function run() {{
  const calls = [];
  global.chrome = {{debugger: {{sendCommand: (_debuggee, method, args) => {{
    calls.push([method, args.requestId]);
    return Promise.resolve({{
      postData: Buffer.from(body, "utf8").toString("base64"),
      base64Encoded: true
    }});
  }}}}}};
  const context = {{
    schema20ProtectedSubmitArmed: true,
    schema20ProtectedSubmitMarkerObserved: true,
    schema29ExpectedText: prompt,
    schema29ExpectedAttachmentCount: 1,
    schema19RequestedConversationId: null,
    schema29PostArmConversationRequests: [],
    deadlineAt: 10000
  }};
  _pr92Schema29RecordPostArmConversationRequest(
    {{tabId: 7}},
    context,
    {{
      requestId: "request-1",
      request: {{url: "https://chatgpt.com/backend-api/f/conversation", method: "POST", hasPostData: true}},
      hasUserGesture: true
    }}
  );
  await _pr92Schema29AwaitPostDataLookups(context);
  const entry = context.schema29PostArmConversationRequests[0];
  const correlation = _pr92Schema29EvaluateSubmitCorrelation(context);

  global.chrome = {{debugger: {{sendCommand: () => Promise.reject(new Error("missing"))}}}};
  const failedContext = {{
    schema20ProtectedSubmitArmed: true,
    schema20ProtectedSubmitMarkerObserved: true,
    schema29ExpectedText: prompt,
    schema29ExpectedAttachmentCount: 1,
    schema19RequestedConversationId: null,
    schema29PostArmConversationRequests: [],
    deadlineAt: 10000
  }};
  _pr92Schema29RecordPostArmConversationRequest(
    {{tabId: 7}},
    failedContext,
    {{
      requestId: "request-2",
      request: {{url: "https://chatgpt.com/backend-api/f/conversation", method: "POST", hasPostData: true}}
    }}
  );
  await _pr92Schema29AwaitPostDataLookups(failedContext);
  const failedCorrelation = _pr92Schema29EvaluateSubmitCorrelation(failedContext);

  console.log(JSON.stringify({{
    calls,
    resolved: {{
      source: entry.requestBodySource,
      bodyResolved: entry.requestBodyResolved,
      matched: entry.matched,
      logicalUserMessageCount: entry.logicalUserMessageIds.length,
      correlation
    }},
    failed: failedCorrelation
  }}));
}}
run();
"""
    )


def test_schema_29_is_loaded_after_schema_28_diagnostic_overlay():
    text = LOADER.read_text(encoding="utf-8")
    schema28 = 'importScripts("service_worker_rich_input_schema28_repair_pr9_2.js");'
    diagnostic28 = 'importScripts("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js");'
    schema29 = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    assert text.index(schema28) < text.index(diagnostic28) < text.index(schema29)


def test_schema_29_response_identity_accepts_current_protocol_without_stream_handoff():
    results = _run_response_parser_cases()
    expected = "11111111-2222-3333-4444-555555555555"
    for key in ("resumeOnly", "messageOnly", "rootAddOnly", "base64"):
        parsed = results[key]
        assert parsed["conversationId"] == expected
        assert parsed["diagnostics"]["distinctProtocolConversationIdCount"] == 1
        assert parsed["diagnostics"]["conflictingConversationIds"] is False
    assert results["resumeOnly"]["diagnostics"]["streamHandoffCount"] == 0
    assert results["base64"]["diagnostics"]["bodyDecoded"] is True
    assert results["base64"]["diagnostics"]["base64Encoded"] is True


def test_schema_29_response_identity_keeps_handoff_and_conflict_fail_closed():
    results = _run_response_parser_cases()
    handoff = results["oldHandoff"]
    assert handoff["conversationId"] == "11111111-2222-3333-4444-555555555555"
    assert handoff["turnExchangeId"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert handoff["diagnostics"]["streamHandoffCount"] == 1
    assert results["nestedOnly"]["conversationId"] is None
    assert results["conflict"]["conversationId"] is None
    assert results["conflict"]["diagnostics"]["conflictingConversationIds"] is True


def test_schema_29_request_body_matches_image_file_and_continuation_shapes():
    results = _run_request_match_cases()
    assert results["image"]["matched"] is True
    assert results["image"]["logicalMessageId"] == "msg-image"
    assert results["image"]["logicalUserMessageIds"] == ["msg-image"]
    assert results["image"]["diagnostics"]["pointerPartCount"] == 1
    assert results["generalFile"]["matched"] is True
    assert results["generalFile"]["diagnostics"]["metadataAttachmentCount"] == 1
    assert results["bothChannels"]["matched"] is True
    assert results["bothChannels"]["diagnostics"]["attachmentEvidenceChannelCount"] == 2
    assert results["continuation"]["matched"] is True


def test_schema_29_request_body_rejects_wrong_intended_identity_but_classifies_user_turns():
    results = _run_request_match_cases()
    for key in (
        "continuationWrongId",
        "wrongText",
        "wrongCount",
        "newChatWithConversation",
        "missingMessageId",
        "missingPostData",
        "malformedJson",
        "multiUserSameText",
    ):
        assert results[key]["matched"] is False, key
    assert results["wrongText"]["logicalUserMessageIds"] == ["msg-wrong-text"]
    assert results["wrongCount"]["logicalUserMessageIds"] == ["msg-wrong-count"]
    assert results["multiUserSameText"]["logicalUserMessageIds"] == ["m1", "m2"]
    assert results["missingPostData"]["diagnostics"]["postDataPresent"] is False
    assert results["malformedJson"]["diagnostics"]["requestJsonParsed"] is False


def test_schema_29_service_post_multiplicity_and_same_logical_retry_are_safe():
    results = _run_correlation_cases()
    assert results["one"]["ok"] is True
    assert results["extraService"]["ok"] is True
    assert results["extraService"]["postArmConversationRequestCount"] == 3
    assert results["extraService"]["distinctPostArmUserMessageCount"] == 1
    assert results["duplicateSameLogical"]["ok"] is True
    assert results["duplicateSameLogical"]["matchingRequestCount"] == 2
    assert results["duplicateSameLogical"]["distinctPostArmUserMessageCount"] == 1


def test_schema_29_distinct_or_concurrent_user_turns_fail_closed():
    results = _run_correlation_cases()
    assert results["distinctMatching"]["ok"] is False
    assert results["distinctMatching"]["foreignPostArmUserMessageCount"] == 1
    assert results["foreignUser"]["ok"] is False
    assert results["foreignUser"]["foreignPostArmUserMessageCount"] == 1
    assert results["firstServiceThenMatch"]["ok"] is False
    assert results["firstServiceThenMatch"]["firstRequestMatched"] is False
    assert results["noMarker"]["ok"] is False


def test_schema_29_unresolved_request_body_fails_closed():
    result = _run_correlation_cases()["unresolved"]
    assert result["ok"] is False
    assert result["unresolvedRequestBodyCount"] == 1


def test_schema_29_user_gesture_is_diagnostic_not_identity_authority():
    result = _run_correlation_cases()["gesture"]
    assert result["ok"] is True
    assert result["postArmUserGestureRequestCount"] == 1
    assert result["hasUserGestureAuthoritative"] is False


def test_schema_29_missing_event_postdata_uses_exact_request_fallback():
    result = _run_postdata_fallback_cases()
    assert result["calls"] == [["Network.getRequestPostData", "request-1"]]
    resolved = result["resolved"]
    assert resolved["source"] == "network-get-request-post-data"
    assert resolved["bodyResolved"] is True
    assert resolved["matched"] is True
    assert resolved["logicalUserMessageCount"] == 1
    assert resolved["correlation"]["ok"] is True
    assert resolved["correlation"]["fallbackRequestBodyCount"] == 1


def test_schema_29_failed_postdata_fallback_remains_fail_closed():
    result = _run_postdata_fallback_cases()["failed"]
    assert result["ok"] is False
    assert result["unresolvedRequestBodyCount"] == 1


def test_schema_29_replaces_only_schema20_final_gate_and_keeps_validated_arm_boundary():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function _pr92Schema29ExecuteOfficialPageTurn")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "_pr92Schema20ObserveArmMarker(context, params)" in block
    assert "_pr92Schema29RecordPostArmConversationRequest(debuggee, context, params)" in block
    assert "chrome.debugger.onEvent.addListener(observer)" in block
    assert "await _pr92Schema20PriorExecuteOfficialPageTurn(args)" in block
    assert "await _pr92Schema29AwaitPostDataLookups(context)" in block
    assert "context.schema20ProtectedSubmitArmed = false" in block
    assert "_pr92Schema29PriorExecuteOfficialPageTurn(args)" in block


def test_schema_29_request_body_fallback_is_exact_request_bound_and_bounded():
    text = SCHEMA29.read_text(encoding="utf-8")
    assert '"Network.getRequestPostData"' in text
    assert "{ requestId }" in text
    assert "PR92_SCHEMA29_POSTDATA_SETTLE_CAP_MS" in text
    assert "PR92_SCHEMA19_RPC_RETURN_RESERVE_MS" in text
    assert '"SCHEMA29_REQUEST_POST_DATA_SETTLE"' in text
    assert "Promise.allSettled(pending)" in text


def test_schema_29_request_matcher_has_no_route_or_response_identity_authority():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema29InspectRequestPostData")
    end = text.index("function _pr92Schema29ApplyRequestInspection", start)
    block = text[start:end]
    assert 'payload.action === "next"' in block
    assert 'message?.author?.role !== "user"' in block
    assert 'textParts.join("") !== expectedText' in block
    assert "conversationIdFromUrl" not in block
    assert "chrome.tabs" not in block
    assert "Network.getResponseBody" not in block


def test_schema_29_committed_error_diagnostics_do_not_expose_request_content_or_ids():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("const correlationSuffix = correlation")
    end = text.index("throw new Error(", start)
    block = text[start:end]
    assert "requestId=" not in block
    assert "logicalMessageId=" not in block
    assert "expectedText" not in block
    assert "conversationId=" not in block
    assert "foreignPostArmUserMessageCount" in block
    assert "unresolvedRequestBodyCount" in block
    assert "fallbackRequestBodyCount" in block


def test_schema_29_support_gate_adapts_legacy_schema20_then_requires_new_authority(monkeypatch):
    captured: dict[str, object] = {}

    def fake_validate(legacy: dict[str, object]) -> None:
        assert legacy["schema"] == gate29._v28.SCHEMA
        assert legacy["new_chat_conversation_identity_authority"] == (
            "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF"
        )
        assert legacy["protected_submit_request_correlation"] == (
            "PAGE_SIDE_ARMED_SINGLE_CONVERSATION_POST"
        )
        assert legacy["exactly_one_post_arm_conversation_request_required"] is True
        assert (
            legacy[
                "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete"
            ]
            is True
        )
        captured.update(legacy)

    monkeypatch.setattr(gate29._v28, "_validate_support", fake_validate)
    support = {
        "supported": True,
        "schema": 29,
        "new_chat_conversation_identity_authority": (
            "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS"
        ),
        "request_bound_protocol_conversation_id_authority": True,
        "request_bound_protocol_conversation_id_consensus_required": True,
        "top_level_conversation_id_authority": True,
        "root_add_value_conversation_id_authority": True,
        "unrecognized_nested_conversation_id_can_satisfy_identity": False,
        "stream_handoff_required_for_causal_conversation_identity": False,
        "conflicting_request_bound_conversation_ids_fail_closed": True,
        "route_conversation_identity_authoritative": False,
        "protected_submit_request_correlation": (
            "VALIDATED_CLICK_REQUEST_BODY_USER_MESSAGE_IDENTITY"
        ),
        "validated_click_request_body_correlation": True,
        "request_post_data_required_for_protected_submit_correlation": True,
        "request_post_data_fallback_supported": True,
        "request_post_data_fallback_exact_request_bound": True,
        "unresolved_request_body_fails_closed": True,
        "exact_user_text_required_for_protected_submit_correlation": True,
        "request_message_id_required_for_protected_submit_correlation": True,
        "request_attachment_count_required_for_protected_submit_correlation": True,
        "continuation_conversation_id_required_for_protected_submit_correlation": True,
        "new_chat_conversation_id_must_be_absent_for_protected_submit_correlation": True,
        "additional_service_post_arm_requests_allowed": True,
        "additional_post_arm_conversation_requests_authoritative": False,
        "duplicate_same_logical_message_request_allowed": True,
        "distinct_post_arm_user_messages_fail_closed": True,
        "has_user_gesture_authoritative": False,
        "exactly_one_post_arm_conversation_request_required": False,
        "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete": False,
        "submit_correlation_failure_diagnostics_available": True,
        "automatic_write_retry_after_submit_correlation_failure": False,
        "automatic_write_retry_after_causal_identity_failure": False,
    }

    gate29._validate_support(support)
    assert captured["schema"] == gate29._v28.SCHEMA


def test_schema_29_support_source_requires_request_body_causal_contract():
    text = GATE29.read_text(encoding="utf-8")
    for needle in (
        "VALIDATED_CLICK_REQUEST_BODY_USER_MESSAGE_IDENTITY",
        "validated_click_request_body_correlation",
        "request_post_data_fallback_supported",
        "request_post_data_fallback_exact_request_bound",
        "unresolved_request_body_fails_closed",
        "exact_user_text_required_for_protected_submit_correlation",
        "request_message_id_required_for_protected_submit_correlation",
        "request_attachment_count_required_for_protected_submit_correlation",
        "continuation_conversation_id_required_for_protected_submit_correlation",
        "additional_service_post_arm_requests_allowed",
        "distinct_post_arm_user_messages_fail_closed",
        "has_user_gesture_authoritative",
    ):
        assert needle in text



def test_schema29_unclassified_request_bodies_remain_unresolved() -> None:
    source = _request_correlation_source()
    result = _run_node(
        f"""
{source}
const prompt = "inspect this attachment exactly";

function classify(body, sourceName) {{
  const inspected = _pr92Schema29InspectRequestPostData(
    body,
    prompt,
    1,
    null
  );
  const entry = {{
    matched: false,
    logicalMessageId: null,
    logicalUserMessageIds: [],
    diagnostics: null,
    requestBodyResolved: false,
    requestBodySource: "unresolved"
  }};
  _pr92Schema29ApplyRequestInspection(entry, inspected, sourceName);
  return {{
    resolved: entry.requestBodyResolved,
    source: entry.requestBodySource,
    matched: entry.matched,
    classified:
      entry.diagnostics?.userMessageIdentityClassified === true
  }};
}}

const missingMessageId = JSON.stringify({{
  action: "next",
  messages: [{{
    author: {{role: "user"}},
    content: {{
      parts: [
        {{asset_pointer: "sediment://file"}},
        prompt
      ]
    }}
  }}]
}});

const harmlessService = JSON.stringify({{
  action: "service",
  messages: []
}});

const malformedMessagesShape = JSON.stringify({{
  action: "next",
  messages: {{"unexpected": true}}
}});

console.log(JSON.stringify({{
  malformedJson:
    classify("not-json", "request-event-post-data"),
  missingMessageId:
    classify(missingMessageId, "request-event-post-data"),
  malformedMessagesShape:
    classify(malformedMessagesShape, "request-event-post-data"),
  harmlessService:
    classify(harmlessService, "request-event-post-data"),
  explicitlyBodyless:
    classify(null, "request-event-no-post-data")
}}));
"""
    )

    assert result["malformedJson"]["resolved"] is False
    assert result["malformedJson"]["source"] == "unresolved"

    assert result["missingMessageId"]["resolved"] is False
    assert result["missingMessageId"]["classified"] is False
    assert result["missingMessageId"]["source"] == "unresolved"

    assert result["malformedMessagesShape"]["resolved"] is False
    assert result["malformedMessagesShape"]["source"] == "unresolved"

    assert result["harmlessService"]["resolved"] is True
    assert result["harmlessService"]["classified"] is True
    assert result["harmlessService"]["matched"] is False

    assert result["explicitlyBodyless"]["resolved"] is True


def test_schema29_committed_error_does_not_settle_postdata_twice() -> None:
    source = SCHEMA29.read_text(encoding="utf-8")

    execute_start = source.index(
        "executeOfficialPageTurn = async function "
        "_pr92Schema29ExecuteOfficialPageTurn"
    )
    catch_start = source.index("  } catch (error) {", execute_start)
    finally_start = source.index("  } finally {", catch_start)
    catch_source = source[catch_start:finally_start]

    assert (
        "await _pr92Schema29AwaitPostDataLookups(context);"
        not in catch_source
    )
    assert (
        "_pr92Schema29LastSubmitCorrelationDiagnostics === null"
        in catch_source
    )
    assert (
        "_pr92Schema29EvaluateSubmitCorrelation(context)"
        in catch_source
    )
