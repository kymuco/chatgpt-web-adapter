from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
SCHEMA17 = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"
SCHEMA20 = EXT / "service_worker_rich_input_schema20_repair_pr9_2.js"
SCHEMA29 = EXT / "service_worker_rich_input_schema29_repair_pr9_2.js"
OWNER = EXT / "service_worker_conversation_write_predicate.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_conversation_write_predicate_has_one_public_owner() -> None:
    core = _source(CORE)
    schema20 = _source(SCHEMA20)
    owner = _source(OWNER)

    assert "function _cwaBaseIsConversationWrite(" in core
    assert "function isConversationWrite(" not in core

    assert "function _pr92Schema20SubmitBoundConversationWrite(" in schema20
    assert "isConversationWrite =" not in schema20
    assert "_pr92Schema20PriorIsConversationWrite" not in schema20

    assert owner.count("function isConversationWrite(") == 1
    assert "isConversationWrite =" not in owner


def test_schema20_gate_uses_explicit_base_classifier() -> None:
    schema20 = _source(SCHEMA20)
    start = schema20.index("function _pr92Schema20SubmitBoundConversationWrite")
    end = schema20.index("function _pr92Schema20ObserveArmMarker", start)
    block = schema20[start:end]

    assert "_cwaBaseIsConversationWrite(url, method)" in block
    assert "context.schema20ProtectedSubmitArmed === true" in block


def test_schema29_post_arm_recorder_uses_structural_base_not_public_gate() -> None:
    schema29 = _source(SCHEMA29)
    start = schema29.index("function _pr92Schema29RecordPostArmConversationRequest")
    end = schema29.index("async function _pr92Schema29AwaitPostDataLookups", start)
    block = schema29[start:end]

    assert "_cwaBaseIsConversationWrite(" in block
    assert "isConversationWrite(" not in block
    assert "_pr92Schema20SubmitBoundConversationWrite(" not in block


def test_schema17_keeps_dynamic_public_authority_resolution() -> None:
    schema17 = _source(SCHEMA17)
    assert 'isConversationWrite(request?.url || "", request?.method || "")' in schema17


def test_write_domain_installs_predicate_owner_after_rich_schema_loader() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    submit = 'importScripts("service_worker_protected_submit_expression.js");'
    owner = 'importScripts("service_worker_conversation_write_predicate.js");'
    evidence = 'importScripts("service_worker_attachment_evidence.js");'

    assert write.index(schemas) < write.index(submit) < write.index(owner)
    assert write.index(owner) < write.index(evidence)


def test_public_owner_delegates_once_with_unchanged_arguments() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
function _pr92Schema20SubmitBoundConversationWrite(url, method) {{
  calls.push([url, method]);
  return true;
}}
{owner}
const result = isConversationWrite(
  "https://chatgpt.com/backend-api/conversation",
  "POST"
);
console.log(JSON.stringify({{
  result,
  calls
}}));
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": True,
        "calls": [["https://chatgpt.com/backend-api/conversation", "POST"]],
    }
