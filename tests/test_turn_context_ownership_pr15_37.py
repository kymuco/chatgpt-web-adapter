from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker_rich_input_pr9_2.js"
SCHEMA19 = EXT / "service_worker_rich_input_schema19_repair_pr9_2.js"
SCHEMA20 = EXT / "service_worker_rich_input_schema20_repair_pr9_2.js"
SCHEMA26_DIAG = EXT / "service_worker_rich_input_schema26_staging_diagnostic_pr9_2.js"
SCHEMA27_DIAG = EXT / "service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js"
SCHEMA28 = EXT / "service_worker_rich_input_schema28_repair_pr9_2.js"
OWNER = EXT / "service_worker_turn_context.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_turn_context_has_one_public_owner() -> None:
    base = _source(BASE)
    schema19 = _source(SCHEMA19)
    schema20 = _source(SCHEMA20)
    owner = _source(OWNER)

    assert "function _pr92BaseCreateTurnContext(" in base
    assert "function _pr92CreateTurnContext(" not in base

    assert "function _pr92Schema19CreateTurnContext(" in schema19
    assert "_pr92CreateTurnContext =" not in schema19
    assert "_pr92Schema19PriorCreateTurnContext" not in schema19

    assert "function _pr92Schema20CreateTurnContext(" in schema20
    assert "_pr92CreateTurnContext =" not in schema20
    assert "_pr92Schema20PriorCreateTurnContext" not in schema20

    assert owner.count("function _pr92CreateTurnContext(") == 1
    assert "_pr92CreateTurnContext =" not in owner


def test_context_composition_is_base_then_schema19_then_schema20() -> None:
    schema19 = _source(SCHEMA19)
    schema20 = _source(SCHEMA20)
    owner = _source(OWNER)

    assert "const context = _pr92BaseCreateTurnContext(message);" in schema19
    assert "const context = _pr92Schema19CreateTurnContext(message);" in schema20
    assert "return _pr92Schema20CreateTurnContext(message);" in owner


def test_schema19_and_schema20_preserve_their_context_fields() -> None:
    schema19 = _source(SCHEMA19)
    schema20 = _source(SCHEMA20)

    for field in (
        "schema19RequestedConversationId",
        "schema19CausalConversationId",
        "schema19CausalTurnExchangeId",
    ):
        assert field in schema19

    for field in (
        "schema20ProtectedSubmitArmed",
        "schema20ProtectedSubmitArmedAt",
        "schema20ProtectedSubmitMarker",
        "schema20ProtectedSubmitMarkerObserved",
        "schema20PostArmConversationRequests",
    ):
        assert field in schema20


def test_diagnostics_consume_public_context_factory_without_owning_it() -> None:
    for path in (SCHEMA26_DIAG, SCHEMA27_DIAG, SCHEMA28):
        source = _source(path)
        assert "_pr92CreateTurnContext(message)" in source
        assert "_pr92CreateTurnContext =" not in source


def test_write_domain_installs_context_owner_immediately_after_schema_loader() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_turn_context.js");'
    submit = 'importScripts("service_worker_protected_submit_expression.js");'

    assert write.index(schemas) < write.index(owner) < write.index(submit)


def test_public_owner_delegates_once_with_unchanged_message() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
function _pr92Schema20CreateTurnContext(message) {{
  calls.push(message);
  return {{ marker: "final" }};
}}
{owner}
const message = {{ text: "hello" }};
const result = _pr92CreateTurnContext(message);
console.log(JSON.stringify({{
  result,
  count: calls.length,
  sameMessage: calls[0] === message
}}));
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": {"marker": "final"},
        "count": 1,
        "sameMessage": True,
    }
