from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA28 = EXT / "service_worker_rich_input_schema28_repair_pr9_2.js"
DIAGNOSTIC_REPAIR28 = EXT / "service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js"
GATE28 = PKG / "product_rich_input_live_gate_schema28_pr9_2.py"
DIAGNOSTIC28 = PKG / "product_rich_input_committed_identity_diagnostic_schema28_pr9_2.py"


def _run_parser_cases() -> dict[str, object]:
    text = SCHEMA28.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema28DecodeResponseBody")
    end = text.index("extractSafeStreamMetadata = function", start)
    functions = text[start:end]
    script = f"""
{functions}
const cid = "11111111-2222-3333-4444-555555555555";
const turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const spaced = `event: delta_encoding\ndata: \"v1\"\n\ndata: {{\"type\": \"stream_handoff\", \"conversation_id\": \"${{cid}}\", \"turn_exchange_id\": \"${{turn}}\"}}\n\ndata: [DONE]\n`;
const compact = `data: {{\"type\":\"stream_handoff\",\"conversation_id\":\"${{cid}}\",\"turn_exchange_id\":\"${{turn}}\"}}\n`;
const unrelated = `data: {{\"type\": \"resume_conversation_token\", \"conversation_id\": \"${{cid}}\"}}\n`;
const conflict = `data: {{\"type\": \"stream_handoff\", \"conversation_id\": \"${{cid}}\"}}\ndata: {{\"type\": \"stream_handoff\", \"conversation_id\": \"different-id\"}}\n`;
const encoded = Buffer.from(spaced, "utf8").toString("base64");
console.log(JSON.stringify({{
  spaced: _pr92Schema28ExtractRequestBoundStreamMetadata(spaced, false),
  compact: _pr92Schema28ExtractRequestBoundStreamMetadata(compact, false),
  base64: _pr92Schema28ExtractRequestBoundStreamMetadata(encoded, true),
  unrelated: _pr92Schema28ExtractRequestBoundStreamMetadata(unrelated, false),
  conflict: _pr92Schema28ExtractRequestBoundStreamMetadata(conflict, false)
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


def _run_observer_preservation_case() -> dict[str, object]:
    text = SCHEMA28.read_text(encoding="utf-8")
    helper_start = text.index("function _pr92Schema28DecodeResponseBody")
    override_start = text.index("extractSafeStreamMetadata = function", helper_start)
    override_end = text.index("async function _pr92Schema28ReadDiagnosticTab", override_start)
    helpers = text[helper_start:override_start]
    override = text[override_start:override_end]
    script = f"""
{helpers}
let priorCalls = 0;
const _pr92Schema28PriorExtractSafeStreamMetadata = (body, base64Encoded) => {{
  priorCalls += 1;
  globalThis.observerSideEffect = `${{base64Encoded === true}}:${{body.length}}`;
  return {{ conversationId: "WRONG_PRIOR_ID", turnExchangeId: "WRONG_PRIOR_TURN" }};
}};
let _pr92Schema28LastIdentityParseDiagnostics = null;
let _pr92ActiveRichInputContext = {{
  schema19CausalConversationId: "OLD_ID",
  schema19CausalTurnExchangeId: "OLD_TURN"
}};
let extractSafeStreamMetadata;
{override}
const cid = "11111111-2222-3333-4444-555555555555";
const turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const body = `data: {{\"type\": \"stream_handoff\", \"conversation_id\": \"${{cid}}\", \"turn_exchange_id\": \"${{turn}}\"}}\n`;
const result = extractSafeStreamMetadata(body, false);
console.log(JSON.stringify({{
  priorCalls,
  observerSideEffect: globalThis.observerSideEffect,
  result,
  context: _pr92ActiveRichInputContext
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


def test_schema_28_overlay_is_loaded_after_schema_27_diagnostic():
    text = LOADER.read_text(encoding="utf-8")
    schema27 = 'importScripts("service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js");'
    schema28 = 'importScripts("service_worker_rich_input_schema28_repair_pr9_2.js");'
    diagnostic_repair28 = 'importScripts("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js");'
    assert schema27 in text
    assert schema28 in text
    assert diagnostic_repair28 in text
    assert text.index(schema27) < text.index(schema28) < text.index(diagnostic_repair28)


def test_schema_28_parser_is_json_first_and_not_serialization_specific():
    text = SCHEMA28.read_text(encoding="utf-8")
    start = text.index("function _pr92Schema28ExtractRequestBoundStreamMetadata")
    end = text.index("extractSafeStreamMetadata = function", start)
    block = text[start:end]
    assert "JSON.parse(payloadText)" in block
    assert 'payload?.type !== "stream_handoff"' in block
    assert '.includes(\'"type":"stream_handoff"\')' not in block
    assert "conversationIdFromUrl" not in block
    assert "chrome.tabs" not in block


def test_schema_28_parser_accepts_spaced_compact_and_base64_exact_request_bodies():
    results = _run_parser_cases()
    expected_cid = "11111111-2222-3333-4444-555555555555"
    expected_turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    for key in ("spaced", "compact", "base64"):
        parsed = results[key]
        assert parsed["conversationId"] == expected_cid
        assert parsed["turnExchangeId"] == expected_turn
        assert parsed["diagnostics"]["streamHandoffCount"] == 1
        assert parsed["diagnostics"]["conflictingConversationIds"] is False
    assert results["base64"]["diagnostics"]["base64Encoded"] is True
    assert results["base64"]["diagnostics"]["bodyDecoded"] is True


def test_schema_28_non_handoff_and_conflicting_handoffs_fail_closed():
    results = _run_parser_cases()
    assert results["unrelated"]["conversationId"] is None
    assert results["unrelated"]["diagnostics"]["streamHandoffCount"] == 0
    assert results["conflict"]["conversationId"] is None
    assert results["conflict"]["turnExchangeId"] is None
    assert results["conflict"]["diagnostics"]["streamHandoffCount"] == 2
    assert results["conflict"]["diagnostics"]["conflictingConversationIds"] is True


def test_schema_28_preserves_prior_metadata_observer_side_effects_without_trusting_its_ids():
    result = _run_observer_preservation_case()
    expected_cid = "11111111-2222-3333-4444-555555555555"
    expected_turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert result["priorCalls"] == 1
    assert result["observerSideEffect"].startswith("false:")
    assert result["result"] == {
        "conversationId": expected_cid,
        "turnExchangeId": expected_turn,
    }
    assert result["context"]["schema19CausalConversationId"] == expected_cid
    assert result["context"]["schema19CausalTurnExchangeId"] == expected_turn
    assert result["result"]["conversationId"] != "WRONG_PRIOR_ID"


def test_schema_28_repaired_metadata_still_populates_schema_19_request_bound_context():
    text = SCHEMA28.read_text(encoding="utf-8")
    assert "const _pr92Schema28PriorExtractSafeStreamMetadata = extractSafeStreamMetadata;" in text
    start = text.index("extractSafeStreamMetadata = function")
    end = text.index("async function _pr92Schema28ReadDiagnosticTab", start)
    block = text[start:end]
    assert "_pr92Schema28PriorExtractSafeStreamMetadata(body, base64Encoded)" in block
    assert "_pr92Schema28ExtractRequestBoundStreamMetadata(body, base64Encoded)" in block
    assert block.index("_pr92Schema28PriorExtractSafeStreamMetadata") < block.index(
        "_pr92Schema28ExtractRequestBoundStreamMetadata"
    )
    assert "context.schema19CausalConversationId" in block
    assert "context.schema19CausalTurnExchangeId" in block
    assert "conversationIdFromUrl" not in block
    assert "chrome.tabs" not in block


def test_schema_28_committed_identity_error_keeps_no_retry_classification_and_safe_diagnostics():
    text = SCHEMA28.read_text(encoding="utf-8")
    assert '"PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED"' in text
    assert "bodyDecoded=" in text
    assert "base64Encoded=" in text
    assert "parsedJsonDataRecords=" in text
    assert "streamHandoffCount=" in text
    assert "conflictingConversationIds=" in text
    assert "automaticWriteRetryAfterCausalIdentityFailure: false" in text
    assert "routeConversationIdentityAuthoritative: false" in text
    assert "priorStreamMetadataObserverSideEffectsPreserved: true" in text


def test_schema_28_support_gate_preserves_schema_27_and_requires_parser_repair_contract():
    text = GATE28.read_text(encoding="utf-8")
    assert "SCHEMA = 28" in text
    assert "class ProductRichInputSchema28LiveProvider" in text
    assert 'legacy["schema"] = _v27.SCHEMA' in text
    assert "_v27._validate_support(legacy)" in text
    required = [
        "causal_stream_handoff_json_parsed_before_type_filter",
        "causal_stream_handoff_json_whitespace_invariant",
        "causal_stream_handoff_base64_body_decoding_supported",
        "conflicting_stream_handoff_conversation_ids_fail_closed",
        "prior_stream_metadata_observer_side_effects_preserved",
    ]
    for key in required:
        assert key in text
    assert "PR9_2_SCHEMA28_PRIOR_METADATA_OBSERVER_NOT_PRESERVED" in text
    assert "PRODUCT_WRITE_BUDGET = _v27.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_28_reconciliation_diagnostic_is_zero_write_and_reserves_cleanup_authority():
    js = DIAGNOSTIC_REPAIR28.read_text(encoding="utf-8")
    assert "message?.text != null || message?.attachmentPaths != null" in js
    assert "PR92_SCHEMA28_DIAGNOSTIC_ROUTE_SAMPLE_MAX_MS = 250" in js
    assert "PR92_SCHEMA28_DIAGNOSTIC_CLEANUP_RESERVE_MS = 10000" in js
    assert "available = remaining - reserve" in js
    assert "skippedForCleanupReserve" in js
    assert "await _pr92ReadDirtyAttachmentFence()" in js
    assert "await _pr92RequireCleanAttachmentState(context)" in js
    assert 'cleanupProofAuthority: cleanupRequired' in js
    assert '"PRODUCTION_REQUIRE_CLEAN_ATTACHMENT_STATE"' in js
    assert '"POST_CLEANUP_TAB_ABSENCE_PROBE"' in js
    assert '"POST_CLEANUP_TAB_PRESENCE_PROBE"' in js
    assert 'tabAfterCleanup.state === "absent"' in js
    assert 'tabAfterCleanup.state === "present"' in js
    assert "writePerformed: false" in js
    assert "conversationWritePerformed: false" in js
    assert "attachmentStagingPerformed: false" in js
    assert "textInsertionPerformed: false" in js
    assert "protectedSubmitAttempted: false" in js
    assert "routeConversationIdentityAuthoritative: false" in js

    py = DIAGNOSTIC28.read_text(encoding="utf-8")
    assert '"diagnosePr92CommittedIdentityStateSchema28": True' in py
    request_start = py.index("response = provider._rpc(")
    request_end = py.index("if response.get", request_start)
    request_block = py[request_start:request_end]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert 'response.get("writePerformed") is not False' in py
    assert 'response.get("protectedSubmitAttempted") is not False' in py
    assert 'response.get("durableFenceCleared") is not True' in py
    assert 'response.get("staleComposerReconciled") is not True' in py
    assert 'cleanup_proof_authority != "PRODUCTION_REQUIRE_CLEAN_ATTACHMENT_STATE"' in py
    assert 'fenced_tab_absent is True' in py
    assert 'fenced_tab_absent is False' in py
    assert '"POST_CLEANUP_TAB_ABSENCE_PROBE"' in py
    assert '"POST_CLEANUP_TAB_PRESENCE_PROBE"' in py
