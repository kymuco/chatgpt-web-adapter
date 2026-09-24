from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RUNTIME = EXT / "service_worker_runtime.js"
OWNER = EXT / "service_worker_stream_metadata.js"

LAYERS = {
    "service_worker.js": "_cwaBaseExtractSafeStreamMetadata",
    "service_worker_instant_mode_pr8_8.js": (
        "_pr88ExtractSafeStreamMetadataWithInstantHints"
    ),
    "service_worker_rich_input_schema19_repair_pr9_2.js": (
        "_pr92Schema19ExtractRequestBoundStreamMetadata"
    ),
    "service_worker_rich_input_schema28_repair_pr9_2.js": (
        "_pr92Schema28ExtractSafeStreamMetadata"
    ),
    "service_worker_rich_input_schema29_repair_pr9_2.js": (
        "_pr92Schema29ExtractSafeStreamMetadata"
    ),
}


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


def test_stream_metadata_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("function extractSafeStreamMetadata(") == 1
    assert "extractSafeStreamMetadata =" not in owner

    for name, helper in LAYERS.items():
        source = _source(name)
        assert helper in source, (name, helper)
        assert "extractSafeStreamMetadata =" not in source, name
        assert "PriorExtractSafeStreamMetadata" not in source, name

    assert "function extractSafeStreamMetadata(" not in _source("service_worker.js")


def test_runtime_assembles_stream_metadata_owner_after_all_helpers() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    reconciliation = 'importScripts("service_worker_runtime_tab_reconciliation.js");'
    write = 'importScripts("service_worker_runtime_write.js");'
    owner = 'importScripts("service_worker_stream_metadata.js");'
    tab_resolution = 'importScripts("service_worker_runtime_tab_resolution.js");'

    assert reconciliation in runtime
    assert write in runtime
    assert owner in runtime
    assert tab_resolution in runtime
    assert runtime.index(reconciliation) < runtime.index(write) < runtime.index(owner)
    assert runtime.index(owner) < runtime.index(tab_resolution)


def test_stream_metadata_preserves_historical_outer_to_inner_order() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    markers = (
        "_pr92Schema29ExtractSafeStreamMetadata",
        "_pr92Schema28ExtractSafeStreamMetadata",
        "_pr92Schema19ExtractRequestBoundStreamMetadata",
        "_pr88ExtractSafeStreamMetadataWithInstantHints",
        "_cwaBaseExtractSafeStreamMetadata",
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_stream_metadata_composition_preserves_nested_handoff() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const events = [];

function layer(name) {{
  return (body, base64Encoded, next) => {{
    events.push("enter:" + name + ":" + body + ":" + base64Encoded);
    const result = next(body + ":" + name, false);
    events.push("exit:" + name);
    return result;
  }};
}}

const _pr92Schema29ExtractSafeStreamMetadata = layer("schema29");
const _pr92Schema28ExtractSafeStreamMetadata = layer("schema28");
const _pr92Schema19ExtractRequestBoundStreamMetadata = layer("schema19");
const _pr88ExtractSafeStreamMetadataWithInstantHints = layer("instant");
const _cwaBaseExtractSafeStreamMetadata = (body, base64Encoded) => {{
  events.push("base:" + body + ":" + base64Encoded);
  return {{ conversationId: body, turnExchangeId: null }};
}};

{owner}

const result = extractSafeStreamMetadata("body", true);
console.log(JSON.stringify({{ events, result }}));
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:schema29:body:true",
        "enter:schema28:body:schema29:false",
        "enter:schema19:body:schema29:schema28:false",
        "enter:instant:body:schema29:schema28:schema19:false",
        "base:body:schema29:schema28:schema19:instant:false",
        "exit:instant",
        "exit:schema19",
        "exit:schema28",
        "exit:schema29",
    ]
    assert result["result"]["conversationId"] == (
        "body:schema29:schema28:schema19:instant"
    )
