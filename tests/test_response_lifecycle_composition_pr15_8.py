from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

LAYERS = (
    "service_worker_normalized_activity_stream_pr8_12.js",
    "service_worker_early_product_completion_repair_pr8_11_1.js",
    "service_worker_early_product_completion_pr8_11_1.js",
    "service_worker_post_answer_tail_timing_pr8_11.js",
    "service_worker_revision_safe_text_delivery_pr8_9.js",
    "service_worker_safe_browser_response_stream_pr8_9.js",
)
OWNER = "service_worker_response_lifecycle.js"


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_response_layers_no_longer_own_native_turn() -> None:
    for name in LAYERS:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_lower_level_stream_and_page_hooks_remain_in_original_modules() -> None:
    required = {
        "service_worker_safe_browser_response_stream_pr8_9.js": (
            "async function _executeOfficialPageTurnWithSafeBrowserStream",
        ),
        "service_worker_revision_safe_text_delivery_pr8_9.js": (
            "_pr89BrowserStreamRecordAssistant =",
        ),
        "service_worker_post_answer_tail_timing_pr8_11.js": (
            "_pr89BrowserStreamRecordAssistant =",
            "async function _executeOfficialPageTurnWithPostAnswerTailTiming",
        ),
        "service_worker_early_product_completion_pr8_11_1.js": (
            "_pr89BrowserStreamProcessSseEvent =",
            "_pr89BrowserStreamRecordAssistant =",
            "async function _pr8111ExecuteOfficialPageTurn",
        ),
        "service_worker_early_product_completion_repair_pr8_11_1.js": (
            "_pr89BrowserStreamProcessSseEvent =",
            "_pr89BrowserStreamRecordAssistant =",
            "async function _pr8111RepairExecuteOfficialPageTurn",
        ),
        "service_worker_normalized_activity_stream_pr8_12.js": (
            "_pr89BrowserStreamProcessSseEvent =",
        ),
    }
    for name, tokens in required.items():
        source = _source(name)
        for token in tokens:
            assert token in source, (name, token)


def test_response_lifecycle_is_pure_layer_at_same_assembly_boundary() -> None:
    assembly = _source("service_worker_observability.js")
    owner = _source(OWNER)

    activity = 'importScripts("service_worker_normalized_activity_stream_pr8_12.js");'
    owner_import = f'importScripts("{OWNER}");'
    connector = 'importScripts("service_worker_connector_lifecycle_pr10_0.js");'

    assert activity in assembly and owner_import in assembly and connector in assembly
    assert (
        assembly.index(activity)
        < assembly.index(owner_import)
        < assembly.index(connector)
    )
    assert "executeNativeTurn =" not in owner
    assert "_cwaResponseLifecyclePriorExecuteNativeTurn" not in owner
    assert (
        "async function _executeNativeTurnWithResponseLifecycle(message, next)" in owner
    )


def test_response_lifecycle_preserves_historical_outer_to_inner_order() -> None:
    owner = _source(OWNER)
    markers = (
        '["normalized-activity-stream", _pr812ExecuteNativeTurn]',
        '["early-product-completion-repair", _pr8111RepairExecuteNativeTurn]',
        '["early-product-completion", _pr8111ExecuteNativeTurn]',
        '["post-answer-tail-timing", _executeNativeTurnWithPostAnswerTailTiming]',
        '["revision-safe-text-delivery", _executeNativeTurnWithRevisionSafeTextDelivery]',
        '["safe-browser-response-stream", _executeNativeTurnWithSafeBrowserStream]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_composition_preserves_nested_enter_exit_and_message_handoff() -> None:
    owner = _source(OWNER)
    script = f"""
const events = [];

const priorExecuteNativeTurn = async (message) => {{
  events.push("prior");
  return {{ chain: message.chain }};
}};

function layer(name) {{
  return async (message, next) => {{
    events.push("enter:" + name);
    const result = await next({{
      ...message,
      chain: [...(message.chain || []), name]
    }});
    events.push("exit:" + name);
    return result;
  }};
}}

const _pr812ExecuteNativeTurn = layer("normalized");
const _pr8111RepairExecuteNativeTurn = layer("repair");
const _pr8111ExecuteNativeTurn = layer("early");
const _executeNativeTurnWithPostAnswerTailTiming = layer("tail");
const _executeNativeTurnWithRevisionSafeTextDelivery = layer("delivery");
const _executeNativeTurnWithSafeBrowserStream = layer("stream");

{owner}

(async () => {{
  const result = await _executeNativeTurnWithResponseLifecycle(
    {{ chain: [] }},
    priorExecuteNativeTurn
  );
  console.log(JSON.stringify({{ events, chain: result.chain }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:normalized",
        "enter:repair",
        "enter:early",
        "enter:tail",
        "enter:delivery",
        "enter:stream",
        "prior",
        "exit:stream",
        "exit:delivery",
        "exit:tail",
        "exit:early",
        "exit:repair",
        "exit:normalized",
    ]
    assert result["chain"] == [
        "normalized",
        "repair",
        "early",
        "tail",
        "delivery",
        "stream",
    ]
