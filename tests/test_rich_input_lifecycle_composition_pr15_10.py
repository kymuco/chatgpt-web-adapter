from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

LAYERS = (
    "service_worker_rich_input_schema29_repair_pr9_2.js",
    "service_worker_rich_input_schema28_repair_pr9_2.js",
    "service_worker_rich_input_schema18_repair_pr9_2.js",
    "service_worker_rich_input_schema14_repair_pr9_2.js",
    "service_worker_rich_input_closure_repair_pr9_2.js",
    "service_worker_rich_input_pr9_2.js",
)
OWNER = "service_worker_rich_input_lifecycle.js"


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


def test_mixed_rich_input_layers_no_longer_own_native_turn() -> None:
    for name in LAYERS:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_lower_level_rich_input_hooks_remain_in_original_modules() -> None:
    required = {
        "service_worker_rich_input_pr9_2.js": (
            "executeOfficialPageTurn =",
        ),
        "service_worker_rich_input_closure_repair_pr9_2.js": (
            "submitOfficialPageTurn =",
        ),
        "service_worker_rich_input_schema18_repair_pr9_2.js": (
            "executeOfficialPageTurn =",
        ),
        "service_worker_rich_input_schema28_repair_pr9_2.js": (
            "extractSafeStreamMetadata =",
        ),
        "service_worker_rich_input_schema29_repair_pr9_2.js": (
            "executeOfficialPageTurn =",
        ),
    }
    for name, tokens in required.items():
        source = _source(name)
        for token in tokens:
            assert token in source, (name, token)


def test_rich_input_lifecycle_has_one_owner_at_schema_loader_boundary() -> None:
    assembly = _source("service_worker_runtime_write.js")
    owner = _source(OWNER)

    loader = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner_import = f'importScripts("{OWNER}");'
    text_shape = 'importScripts("service_worker_request_text_shape_compat.js");'

    assert loader in assembly and owner_import in assembly and text_shape in assembly
    assert (
        assembly.index(loader)
        < assembly.index(owner_import)
        < assembly.index(text_shape)
    )
    assert owner.count("executeNativeTurn =") == 1
    assert (
        "const _cwaRichInputLifecyclePriorExecuteNativeTurn = executeNativeTurn;"
        in owner
    )


def test_rich_input_lifecycle_preserves_historical_outer_to_inner_order() -> None:
    owner = _source(OWNER)
    markers = (
        '["schema29", _executeNativeTurnWithPr92Schema29Repair]',
        '["schema28", _executeNativeTurnWithPr92Schema28Repair]',
        '["schema18", _executeNativeTurnWithPr92Schema18Repair]',
        '["schema14", _executeNativeTurnWithPr92Schema14CompositionGuard]',
        '["closure", _executeNativeTurnWithPr92ClosureRepair]',
        '["base-rich-input", _executeNativeTurnWithPr92RichInput]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_rich_input_composition_preserves_nested_order_and_handoff() -> None:
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

const _executeNativeTurnWithPr92Schema29Repair = layer("schema29");
const _executeNativeTurnWithPr92Schema28Repair = layer("schema28");
const _executeNativeTurnWithPr92Schema18Repair = layer("schema18");
const _executeNativeTurnWithPr92Schema14CompositionGuard = layer("schema14");
const _executeNativeTurnWithPr92ClosureRepair = layer("closure");
const _executeNativeTurnWithPr92RichInput = layer("base");

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
        "enter:schema29",
        "enter:schema28",
        "enter:schema18",
        "enter:schema14",
        "enter:closure",
        "enter:base",
        "prior",
        "exit:base",
        "exit:closure",
        "exit:schema14",
        "exit:schema18",
        "exit:schema28",
        "exit:schema29",
    ]
    assert result["chain"] == [
        "schema29",
        "schema28",
        "schema18",
        "schema14",
        "closure",
        "base",
    ]
