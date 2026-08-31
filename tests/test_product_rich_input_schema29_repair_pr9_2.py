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
    return schema29[start:end]


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
  _pr92Schema29MatchRequestPostData(body, prompt, count, expectedCid);
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
const matched = (id, gesture=false) => ({{
  requestId: "r-" + id,
  hasUserGesture: gesture,
  matched: true,
  logicalMessageId: id,
  diagnostics: {{
    postDataPresent: true,
    requestJsonParsed: true,
    actionNext: true,
    conversationIdentityMatches: true,
    exactTextUserMessageCount: 1,
    exactRichUserMessageCount: 1,
    requestMessageIdPresent: true,
    pointerPartCount: 1,
    metadataAttachmentCount: 0,
    attachmentEvidenceChannelCount: 1,
    attachmentCountsMatch: true
  }}
}});
const miss = {{
  requestId: "r-miss",
  hasUserGesture: false,
  matched: false,
  logicalMessageId: null,
  diagnostics: {{
    postDataPresent: true,
    requestJsonParsed: true,
    actionNext: true,
    conversationIdentityMatches: true,
    exactTextUserMessageCount: 0,
    exactRichUserMessageCount: 0,
    requestMessageIdPresent: false,
    pointerPartCount: 0,
    metadataAttachmentCount: 0,
    attachmentEvidenceChannelCount: 0,
    attachmentCountsMatch: false
  }}
}};
const evaluate = (requests, marker=true) => _pr92Schema29EvaluateSubmitCorrelation({{
  schema20ProtectedSubmitMarkerObserved: marker,
  schema29PostArmConversationRequests: requests
}});
console.log(JSON.stringify({{
  one: evaluate([matched("m1")]),
  gesture: evaluate([matched("m1", true)]),
  extraNonMatching: evaluate([matched("m1"), miss, miss]),
  duplicateSameLogical: evaluate([matched("m1"), matched("m1")]),
  distinctMatching: evaluate([matched("m1"), matched("m2")]),
  firstMissThenMatch: evaluate([miss, matched("m1")]),
  noMarker: evaluate([matched("m1")], false)
}}));
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
    assert results["image"]["diagnostics"]["pointerPartCount"] == 1
    assert results["generalFile"]["matched"] is True
    assert results["generalFile"]["diagnostics"]["metadataAttachmentCount"] == 1
    assert results["bothChannels"]["matched"] is True
    assert results["bothChannels"]["diagnostics"]["attachmentEvidenceChannelCount"] == 2
    assert results["continuation"]["matched"] is True
    assert results["continuation"]["logicalMessageId"] == "msg-cont"


def test_schema_29_request_body_rejects_wrong_or_ambiguous_user_message_identity():
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
    assert results["missingPostData"]["diagnostics"]["postDataPresent"] is False
    assert results["malformedJson"]["diagnostics"]["requestJsonParsed"] is False
    assert results["wrongCount"]["diagnostics"]["exactRichUserMessageCount"] == 0
    assert results["multiUserSameText"]["diagnostics"]["exactRichUserMessageCount"] == 2


def test_schema_29_post_arm_multiplicity_is_non_authoritative_after_body_binding():
    results = _run_correlation_cases()
    assert results["one"]["ok"] is True
    assert results["extraNonMatching"]["ok"] is True
    assert results["extraNonMatching"]["postArmConversationRequestCount"] == 3
    assert results["extraNonMatching"]["matchingRequestCount"] == 1
    assert results["duplicateSameLogical"]["ok"] is True
    assert results["duplicateSameLogical"]["matchingRequestCount"] == 2
    assert results["duplicateSameLogical"]["distinctMatchingLogicalMessageCount"] == 1


def test_schema_29_distinct_matching_messages_and_wrong_first_request_fail_closed():
    results = _run_correlation_cases()
    assert results["distinctMatching"]["ok"] is False
    assert results["distinctMatching"]["distinctMatchingLogicalMessageCount"] == 2
    assert results["firstMissThenMatch"]["ok"] is False
    assert results["firstMissThenMatch"]["firstRequestMatched"] is False
    assert results["noMarker"]["ok"] is False


def test_schema_29_user_gesture_is_diagnostic_not_identity_authority():
    result = _run_correlation_cases()["gesture"]
    assert result["ok"] is True
    assert result["postArmUserGestureRequestCount"] == 1
    assert result["hasUserGestureAuthoritative"] is False


def test_schema_29_replaces_only_schema20_final_gate_and_keeps_validated_arm_boundary():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("executeOfficialPageTurn = async function _pr92Schema29ExecuteOfficialPageTurn")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "_pr92Schema20ObserveArmMarker(context, params)" in block
    assert "_pr92Schema29RecordPostArmConversationRequest(context, params)" in block
    assert "chrome.debugger.onEvent.addListener(observer)" in block
    assert "await _pr92Schema20PriorExecuteOfficialPageTurn(args)" in block
    assert block.index("chrome.debugger.onEvent.addListener(observer)") < block.index(
        "await _pr92Schema20PriorExecuteOfficialPageTurn(args)"
    )
    assert "context.schema20ProtectedSubmitArmed = false" in block
    assert "_pr92Schema29PriorExecuteOfficialPageTurn(args)" in block


def test_schema_29_request_matcher_has_no_route_or_response_identity_authority():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema29MatchRequestPostData")
    end = text.index("function _pr92Schema29RecordPostArmConversationRequest", start)
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
    assert "firstRequestPostDataPresent" in block
    assert "matchingRequestCount" in block
    assert "distinctMatchingLogicalMessageCount" in block


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
        "exact_user_text_required_for_protected_submit_correlation": True,
        "request_message_id_required_for_protected_submit_correlation": True,
        "request_attachment_count_required_for_protected_submit_correlation": True,
        "continuation_conversation_id_required_for_protected_submit_correlation": True,
        "new_chat_conversation_id_must_be_absent_for_protected_submit_correlation": True,
        "additional_post_arm_conversation_requests_authoritative": False,
        "duplicate_same_logical_message_request_allowed": True,
        "distinct_matching_logical_messages_fail_closed": True,
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
        "request_post_data_required_for_protected_submit_correlation",
        "exact_user_text_required_for_protected_submit_correlation",
        "request_message_id_required_for_protected_submit_correlation",
        "request_attachment_count_required_for_protected_submit_correlation",
        "continuation_conversation_id_required_for_protected_submit_correlation",
        "additional_post_arm_conversation_requests_authoritative",
        "duplicate_same_logical_message_request_allowed",
        "distinct_matching_logical_messages_fail_closed",
        "has_user_gesture_authoritative",
    ):
        assert needle in text
