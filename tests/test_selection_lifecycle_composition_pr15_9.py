from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

LAYERS = (
    "service_worker_model_profile_selection_pr8_10.js",
    "service_worker_instant_selection_repair_pr8_8.js",
    "service_worker_instant_mode_pr8_8.js",
    "service_worker_phase_timing_pr8_8.js",
)
OWNER = "service_worker_selection_lifecycle.js"


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


def test_selection_layers_no_longer_own_native_turn() -> None:
    for name in LAYERS:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_lower_level_selection_and_timing_hooks_remain_local() -> None:
    required = {
        "service_worker_phase_timing_pr8_8.js": (
            "ensureRuntimeTab =",
            "executeOfficialPageTurn =",
        ),
        "service_worker_instant_mode_pr8_8.js": (
            "locateAndFocusComposer =",
            "extractSafeStreamMetadata =",
            "executeOfficialPageTurn =",
        ),
        "service_worker_instant_selection_repair_pr8_8.js": (
            "locateAndFocusComposer =",
        ),
        "service_worker_model_profile_selection_pr8_10.js": (
            "locateAndFocusComposer =",
        ),
    }
    for name, tokens in required.items():
        source = _source(name)
        for token in tokens:
            assert token in source, (name, token)


def test_selection_lifecycle_has_one_owner_at_historical_outer_boundary() -> None:
    assembly = _source("service_worker_observability.js")
    owner = _source(OWNER)

    model = 'importScripts("service_worker_model_profile_selection_pr8_10.js");'
    owner_import = f'importScripts("{OWNER}");'
    response = 'importScripts("service_worker_safe_browser_response_stream_pr8_9.js");'

    assert model in assembly and owner_import in assembly and response in assembly
    assert (
        assembly.index(model)
        < assembly.index(owner_import)
        < assembly.index(response)
    )
    assert owner.count("executeNativeTurn =") == 1
    assert (
        "const _cwaSelectionLifecyclePriorExecuteNativeTurn = executeNativeTurn;"
        in owner
    )


def test_selection_lifecycle_preserves_historical_outer_to_inner_order() -> None:
    owner = _source(OWNER)
    markers = (
        '["model-profile-selection", _executeNativeTurnWithModelProfile]',
        '["instant-selection-repair", _executeNativeTurnWithInstantSelectionRepair]',
        '["instant-mode-observation", _executeNativeTurnWithInstantModeObservation]',
        '["phase-timing", _executeNativeTurnWithPhaseTiming]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_selection_composition_preserves_nested_order_and_handoff() -> None:
    owner = _source(OWNER)
    script = f"""
const events = [];

let executeNativeTurn = async (message) => {{
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

const _executeNativeTurnWithModelProfile = layer("model");
const _executeNativeTurnWithInstantSelectionRepair = layer("selection");
const _executeNativeTurnWithInstantModeObservation = layer("instant");
const _executeNativeTurnWithPhaseTiming = layer("phase");

{owner}

(async () => {{
  const result = await executeNativeTurn({{ chain: [] }});
  console.log(JSON.stringify({{ events, chain: result.chain }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:model",
        "enter:selection",
        "enter:instant",
        "enter:phase",
        "prior",
        "exit:phase",
        "exit:instant",
        "exit:selection",
        "exit:model",
    ]
    assert result["chain"] == ["model", "selection", "instant", "phase"]
