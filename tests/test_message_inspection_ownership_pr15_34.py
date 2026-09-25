from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
READ = EXT / "service_worker_runtime_read.js"
OWNER = EXT / "service_worker_message_inspection.js"

BASE = EXT / "service_worker_response_activity.js"
PRODUCT = EXT / "service_worker_product_observation.js"
SOURCES = EXT / "service_worker_product_source_citations_pr9_3.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_message_inspection_has_one_public_owner() -> None:
    owner = _source(OWNER)
    base = _source(BASE)
    product = _source(PRODUCT)
    sources = _source(SOURCES)

    assert owner.count("function _pr812InspectMessage(") == 1
    assert "_pr812InspectMessage =" not in owner

    assert "function _pr812BaseInspectMessage(" in base
    assert "function _pr812InspectMessage(" not in base

    assert "function _pr10ProductObservationInspectMessage(" in product
    assert "_pr812InspectMessage =" not in product
    assert "_pr10ProductObservationUpstreamInspectMessage" not in product

    assert "function _pr93InspectMessage(" in sources
    assert "_pr812InspectMessage =" not in sources
    assert "_pr93PriorInspectMessage" not in sources


def test_public_owner_preserves_historical_side_effect_order() -> None:
    owner = _source(OWNER)
    base = owner.index("_pr812BaseInspectMessage(context, state, message)")
    product = owner.index(
        "_pr10ProductObservationInspectMessage(context, state, message)"
    )
    sources = owner.index("_pr93InspectMessage(context, state, message)")
    assert base < product < sources


def test_read_domain_installs_owner_after_source_helper_before_canonical_read() -> None:
    read = _source(READ)
    sources = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    owner = 'importScripts("service_worker_message_inspection.js");'
    canonical = 'importScripts("service_worker_canonical_read_v2.js");'

    assert read.index(sources) < read.index(owner) < read.index(canonical)


def test_explicit_owner_delegates_once_with_unchanged_arguments() -> None:
    owner = _source(OWNER)
    script = f"""
const calls = [];
function _pr812BaseInspectMessage(context, state, message) {{
  calls.push(["base", context, state, message]);
}}
function _pr10ProductObservationInspectMessage(context, state, message) {{
  calls.push(["product", context, state, message]);
}}
function _pr93InspectMessage(context, state, message) {{
  calls.push(["sources", context, state, message]);
}}

{owner}

const context = {{ id: "ctx" }};
const state = {{ id: "state" }};
const message = {{ id: "message" }};
_pr812InspectMessage(context, state, message);
console.log(JSON.stringify({{
  names: calls.map((item) => item[0]),
  sameContext: calls.every((item) => item[1] === context),
  sameState: calls.every((item) => item[2] === state),
  sameMessage: calls.every((item) => item[3] === message)
}}));
"""
    result = _run_node(script)
    assert result == {
        "names": ["base", "product", "sources"],
        "sameContext": True,
        "sameState": True,
        "sameMessage": True,
    }


def test_response_activity_consumers_keep_dynamic_public_resolution() -> None:
    base = _source(BASE)
    assert "_pr812InspectMessage(context, state, state.currentPatchMessage)" in base
    assert "_pr812InspectMessage(context, state, message)" in base
