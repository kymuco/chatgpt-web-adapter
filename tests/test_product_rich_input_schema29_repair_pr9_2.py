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


def _run_parser_cases() -> dict[str, object]:
    schema28 = SCHEMA28.read_text(encoding="utf-8")
    decode_start = schema28.index("function _pr92Schema28DecodeResponseBody")
    decode_end = schema28.index(
        "function _pr92Schema28ExtractRequestBoundStreamMetadata", decode_start
    )
    decode = schema28[decode_start:decode_end]

    schema29 = SCHEMA29.read_text(encoding="utf-8")
    helper_start = schema29.index("function _pr92Schema29NonEmptyString")
    parser_end = schema29.index("extractSafeStreamMetadata = function", helper_start)
    parser = schema29[helper_start:parser_end]

    script = f"""
{decode}
{parser}
const cid = "11111111-2222-3333-4444-555555555555";
const other = "99999999-8888-7777-6666-555555555555";
const turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const resumeOnly = `data: {{"type":"resume_conversation_token","conversation_id":"${{cid}}"}}\n`;
const messageOnly = `data: {{"message":{{"id":"m1"}},"conversation_id":"${{cid}}"}}\n`;
const rootAddOnly = `data: {{"p":"","o":"add","v":{{"message":{{"id":"m1"}},"conversation_id":"${{cid}}"}},"c":1}}\n`;
const topAndRootSame = `data: {{"type":"message_marker","conversation_id":"${{cid}}"}}\ndata: {{"p":"","o":"add","v":{{"conversation_id":"${{cid}}"}}}}\n`;
const oldHandoff = `data: {{"type":"resume_conversation_token","conversation_id":"${{cid}}"}}\ndata: {{"type":"stream_handoff","conversation_id":"${{cid}}","turn_exchange_id":"${{turn}}"}}\n`;
const nestedOnly = `data: {{"type":"message","message":{{"conversation_id":"${{cid}}"}}}}\n`;
const nonRootPatchNested = `data: {{"p":"/message","o":"add","v":{{"conversation_id":"${{cid}}"}}}}\n`;
const conflict = `data: {{"type":"message","conversation_id":"${{cid}}"}}\ndata: {{"p":"","o":"add","v":{{"conversation_id":"${{other}}"}}}}\n`;
const encoded = Buffer.from(rootAddOnly, "utf8").toString("base64");
console.log(JSON.stringify({{
  resumeOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(resumeOnly, false),
  messageOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(messageOnly, false),
  rootAddOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(rootAddOnly, false),
  topAndRootSame: _pr92Schema29ExtractRequestBoundConversationMetadata(topAndRootSame, false),
  oldHandoff: _pr92Schema29ExtractRequestBoundConversationMetadata(oldHandoff, false),
  nestedOnly: _pr92Schema29ExtractRequestBoundConversationMetadata(nestedOnly, false),
  nonRootPatchNested: _pr92Schema29ExtractRequestBoundConversationMetadata(nonRootPatchNested, false),
  conflict: _pr92Schema29ExtractRequestBoundConversationMetadata(conflict, false),
  base64: _pr92Schema29ExtractRequestBoundConversationMetadata(encoded, true)
}}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_schema_29_is_loaded_after_schema_28_diagnostic_overlay():
    text = LOADER.read_text(encoding="utf-8")
    schema28 = 'importScripts("service_worker_rich_input_schema28_repair_pr9_2.js");'
    diagnostic28 = 'importScripts("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js");'
    schema29 = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    assert schema28 in text
    assert diagnostic28 in text
    assert schema29 in text
    assert text.index(schema28) < text.index(diagnostic28) < text.index(schema29)


def test_schema_29_accepts_recognized_exact_request_protocol_id_without_stream_handoff():
    results = _run_parser_cases()
    expected = "11111111-2222-3333-4444-555555555555"
    for key in ("resumeOnly", "messageOnly", "rootAddOnly", "base64"):
        parsed = results[key]
        assert parsed["conversationId"] == expected
        assert parsed["diagnostics"]["distinctProtocolConversationIdCount"] == 1
        assert parsed["diagnostics"]["streamHandoffCount"] == 0
        assert parsed["diagnostics"]["conflictingConversationIds"] is False
    assert results["rootAddOnly"]["diagnostics"]["rootAddValueConversationIdRecordCount"] == 1
    assert results["messageOnly"]["diagnostics"]["topLevelConversationIdRecordCount"] == 1
    assert results["base64"]["diagnostics"]["base64Encoded"] is True
    assert results["base64"]["diagnostics"]["bodyDecoded"] is True


def test_schema_29_requires_consensus_across_top_level_and_root_add_slots():
    parsed = _run_parser_cases()["topAndRootSame"]
    assert parsed["conversationId"] == "11111111-2222-3333-4444-555555555555"
    assert parsed["diagnostics"]["protocolConversationIdRecordCount"] == 2
    assert parsed["diagnostics"]["distinctProtocolConversationIdCount"] == 1
    assert parsed["diagnostics"]["protocolConversationIdSourceKinds"] == [
        "root-add-v",
        "top-level",
    ]


def test_schema_29_preserves_old_stream_handoff_as_consistent_special_case():
    parsed = _run_parser_cases()["oldHandoff"]
    assert parsed["conversationId"] == "11111111-2222-3333-4444-555555555555"
    assert parsed["turnExchangeId"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert parsed["diagnostics"]["protocolConversationIdRecordCount"] == 2
    assert parsed["diagnostics"]["distinctProtocolConversationIdCount"] == 1
    assert parsed["diagnostics"]["streamHandoffCount"] == 1


def test_schema_29_unrecognized_nested_ids_have_zero_authority_and_conflicts_fail_closed():
    results = _run_parser_cases()
    for key in ("nestedOnly", "nonRootPatchNested"):
        parsed = results[key]
        assert parsed["conversationId"] is None
        assert parsed["diagnostics"]["protocolConversationIdRecordCount"] == 0

    conflict = results["conflict"]
    assert conflict["conversationId"] is None
    assert conflict["diagnostics"]["distinctProtocolConversationIdCount"] == 2
    assert conflict["diagnostics"]["conflictingConversationIds"] is True


def test_schema_29_parser_uses_only_recognized_exact_request_protocol_slots():
    text = SCHEMA29.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema29ExtractRequestBoundConversationMetadata")
    end = text.index("extractSafeStreamMetadata = function", start)
    block = text[start:end]
    assert 'Object.prototype.hasOwnProperty.call(payload, "conversation_id")' in block
    assert 'payload.p === ""' in block
    assert 'payload.o === "add"' in block
    assert 'Object.prototype.hasOwnProperty.call(rootAddValue, "conversation_id")' in block
    assert "conversationIdFromUrl" not in block
    assert "chrome.tabs" not in block
    assert "JSON.stringify(payload)" not in block


def test_schema_29_overwrites_schema_19_authority_name_and_keeps_route_diagnostic_only():
    text = SCHEMA29.read_text(encoding="utf-8")
    assert "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS" in text
    assert "conversationIdentityAuthority: PR92_SCHEMA29_IDENTITY_AUTHORITY" in text
    assert "routeConversationIdentityAuthoritative: false" in text
    assert "automaticWriteRetryAfterCausalIdentityFailure: false" in text
    assert "unrecognizedNestedConversationIdCanSatisfyIdentity: false" in text
    assert "streamHandoffRequiredForCausalConversationIdentity: false" in text


def test_schema_29_support_gate_preserves_schema_28_and_requires_consensus_contract():
    text = GATE29.read_text(encoding="utf-8")
    assert "SCHEMA = 29" in text
    assert "class ProductRichInputSchema29LiveProvider" in text
    assert 'legacy["schema"] = _v28.SCHEMA' in text
    assert 'legacy["new_chat_conversation_identity_authority"]' in text
    assert "NETWORK_REQUEST_BOUND_STREAM_HANDOFF" in text
    assert "_v28._validate_support(legacy)" in text
    assert "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS" in text
    assert "request_bound_protocol_conversation_id_consensus_required" in text
    assert "top_level_conversation_id_authority" in text
    assert "root_add_value_conversation_id_authority" in text
    assert "unrecognized_nested_conversation_id_can_satisfy_identity" in text
    assert "stream_handoff_required_for_causal_conversation_identity" in text
    assert "conflicting_request_bound_conversation_ids_fail_closed" in text
    assert "PRODUCT_WRITE_BUDGET = _v28.PRODUCT_WRITE_BUDGET" in text


def test_schema_29_validator_reconstructs_historical_schema19_authority(monkeypatch):
    captured: dict[str, object] = {}

    def fake_validate(legacy: dict[str, object]) -> None:
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
        "automatic_write_retry_after_causal_identity_failure": False,
    }

    gate29._validate_support(support)
    assert captured["schema"] == 28
    assert captured["new_chat_conversation_identity_authority"] == (
        "NETWORK_REQUEST_BOUND_STREAM_HANDOFF"
    )
