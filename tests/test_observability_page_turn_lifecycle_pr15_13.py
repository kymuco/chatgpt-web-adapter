from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OWNER = "service_worker_observability_page_turn_lifecycle.js"

LAYERS = (
    "service_worker_early_product_completion_repair_pr8_11_1.js",
    "service_worker_early_product_completion_pr8_11_1.js",
    "service_worker_post_answer_tail_timing_pr8_11.js",
    "service_worker_safe_browser_response_stream_pr8_9.js",
    "service_worker_instant_mode_pr8_8.js",
    "service_worker_phase_timing_pr8_8.js",
)
BASE = "service_worker_recovery.js"


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


def test_observability_page_turn_layers_do_not_own_global_dispatch() -> None:
    for name in (*LAYERS, BASE):
        source = _source(name)
        assert "executeOfficialPageTurn =" not in source, name

    assert (
        "async function _executeOfficialPageTurnWithEarlyTerminalBoundary("
        in _source(BASE)
    )


def test_observability_page_turn_owner_is_loaded_at_historical_outer_boundary() -> None:
    assembly = _source("service_worker_observability.js")
    owner = _source(OWNER)

    repair = (
        'importScripts("service_worker_early_product_completion_repair_pr8_11_1.js");'
    )
    owner_import = f'importScripts("{OWNER}");'
    normalized = 'importScripts("service_worker_normalized_activity_stream_pr8_12.js");'

    assert repair in assembly and owner_import in assembly and normalized in assembly
    assert (
        assembly.index(repair)
        < assembly.index(owner_import)
        < assembly.index(normalized)
    )
    assert "executeOfficialPageTurn =" not in owner
    assert (
        "async function _executeOfficialPageTurnWithObservabilityLifecycle(args)"
        in owner
    )


def test_observability_page_turn_order_matches_historical_nesting() -> None:
    owner = _source(OWNER)
    markers = (
        '["early-completion-repair", _pr8111RepairExecuteOfficialPageTurn]',
        '["early-completion", _pr8111ExecuteOfficialPageTurn]',
        '["post-answer-tail-timing", _executeOfficialPageTurnWithPostAnswerTailTiming]',
        '["safe-browser-stream", _executeOfficialPageTurnWithSafeBrowserStream]',
        '["instant-observation", _executeOfficialPageTurnWithInstantObservation]',
        '["phase-timing", _executeOfficialPageTurnWithPhaseTiming]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "_executeOfficialPageTurnWithEarlyTerminalBoundary(args)" in owner


def test_explicit_page_turn_composition_preserves_nested_order_and_handoff() -> None:
    owner = _source(OWNER)
    script = f"""
const events = [];
function layer(name) {{
  return async (args, next) => {{
    events.push("enter:" + name);
    const result = await next({{
      ...args,
      chain: [...(args.chain || []), name]
    }});
    events.push("exit:" + name);
    return result;
  }};
}}

const _pr8111RepairExecuteOfficialPageTurn = layer("repair");
const _pr8111ExecuteOfficialPageTurn = layer("early");
const _executeOfficialPageTurnWithPostAnswerTailTiming = layer("tail");
const _executeOfficialPageTurnWithSafeBrowserStream = layer("stream");
const _executeOfficialPageTurnWithInstantObservation = layer("instant");
const _executeOfficialPageTurnWithPhaseTiming = layer("phase");

async function _executeOfficialPageTurnWithEarlyTerminalBoundary(args) {{
  events.push("base");
  return {{ chain: args.chain }};
}}

{owner}

(async () => {{
  const result = await _executeOfficialPageTurnWithObservabilityLifecycle({{ chain: [] }});
  console.log(JSON.stringify({{ events, chain: result.chain }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:repair",
        "enter:early",
        "enter:tail",
        "enter:stream",
        "enter:instant",
        "enter:phase",
        "base",
        "exit:phase",
        "exit:instant",
        "exit:stream",
        "exit:tail",
        "exit:early",
        "exit:repair",
    ]
    assert result["chain"] == [
        "repair",
        "early",
        "tail",
        "stream",
        "instant",
        "phase",
    ]
