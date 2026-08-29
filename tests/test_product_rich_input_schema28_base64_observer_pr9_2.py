from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCHEMA28 = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_rich_input_schema28_repair_pr9_2.js"
)


def _run_base64_observer_case() -> dict[str, object]:
    text = SCHEMA28.read_text(encoding="utf-8")
    helper_start = text.index("function _pr92Schema28DecodeResponseBody")
    override_start = text.index("extractSafeStreamMetadata = function", helper_start)
    override_end = text.index("async function _pr92Schema28ReadDiagnosticTab", override_start)
    helpers = text[helper_start:override_start]
    override = text[override_start:override_end]
    script = f"""
{helpers}
const priorCalls = [];
let responseHintsObserved = false;
const _pr92Schema28PriorExtractSafeStreamMetadata = (body, base64Encoded) => {{
  priorCalls.push({{ body, base64Encoded }});
  if (
    base64Encoded === false &&
    body.includes('\\"model\\": \\"instant\\"') &&
    body.includes('\\"reasoning_effort\\": \\"none\\"')
  ) {{
    responseHintsObserved = true;
  }}
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
const decoded = `data: {{\"model\": \"instant\", \"reasoning_effort\": \"none\"}}\n` +
  `data: {{\"type\": \"stream_handoff\", \"conversation_id\": \"${{cid}}\", \"turn_exchange_id\": \"${{turn}}\"}}\n`;
const encoded = Buffer.from(decoded, "utf8").toString("base64");
const result = extractSafeStreamMetadata(encoded, true);
console.log(JSON.stringify({{
  priorCalls,
  responseHintsObserved,
  decoded,
  result,
  context: _pr92ActiveRichInputContext,
  diagnostics: _pr92Schema28LastIdentityParseDiagnostics
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


def test_schema_28_decodes_base64_before_prior_metadata_observer_side_effects():
    result = _run_base64_observer_case()
    expected_cid = "11111111-2222-3333-4444-555555555555"
    expected_turn = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    assert len(result["priorCalls"]) == 1
    prior = result["priorCalls"][0]
    assert prior["base64Encoded"] is False
    assert prior["body"] == result["decoded"]
    assert result["responseHintsObserved"] is True

    assert result["result"] == {
        "conversationId": expected_cid,
        "turnExchangeId": expected_turn,
    }
    assert result["context"]["schema19CausalConversationId"] == expected_cid
    assert result["context"]["schema19CausalTurnExchangeId"] == expected_turn
    assert result["result"]["conversationId"] != "WRONG_PRIOR_ID"
    assert result["diagnostics"]["base64Encoded"] is True
    assert result["diagnostics"]["bodyDecoded"] is True


def test_schema_28_prior_observer_receives_decoded_text_before_request_bound_parse():
    text = SCHEMA28.read_text(encoding="utf-8")
    start = text.index("extractSafeStreamMetadata = function")
    end = text.index("async function _pr92Schema28ReadDiagnosticTab", start)
    block = text[start:end]

    decode = "const observerBody = _pr92Schema28DecodeResponseBody(body, base64Encoded);"
    observe = "_pr92Schema28PriorExtractSafeStreamMetadata(observerBody, false);"
    parse = "_pr92Schema28ExtractRequestBoundStreamMetadata(body, base64Encoded)"
    assert decode in block
    assert observe in block
    assert parse in block
    assert block.index(decode) < block.index(observe) < block.index(parse)
    assert "_pr92Schema28PriorExtractSafeStreamMetadata(body, base64Encoded);" in block
