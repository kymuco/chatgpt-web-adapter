from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WRITE = EXT / "service_worker_runtime_write.js"
OWNER = EXT / "service_worker_attachment_evidence.js"

LAYERS = {
    "service_worker_rich_input_schema8_repair_pr9_2.js": (
        "_pr92Schema8AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema9_repair_pr9_2.js": (
        "_pr92Schema9AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema10_repair_pr9_2.js": (
        "_pr92Schema10AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema11_repair_pr9_2.js": (
        "_pr92Schema11AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema22_repair_pr9_2.js": (
        "_pr92Schema22AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema23_repair_pr9_2.js": (
        "_pr92Schema23AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema25_repair_pr9_2.js": (
        "_pr92Schema25AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema26_repair_pr9_2.js": (
        "_pr92Schema26AttachmentEvidenceExpression"
    ),
    "service_worker_rich_input_schema27_repair_pr9_2.js": (
        "_pr92Schema27AttachmentEvidenceExpression"
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


def test_attachment_evidence_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("function _pr92ClosureAttachmentEvidenceExpression(") == 1
    assert "_pr92ClosureAttachmentEvidenceExpression =" not in owner

    closure = _source("service_worker_rich_input_closure_repair_pr9_2.js")
    assert "function _pr92BaseAttachmentEvidenceExpression(" in closure
    assert "function _pr92ClosureAttachmentEvidenceExpression(" not in closure

    for name, helper in LAYERS.items():
        source = _source(name)
        assert f"function {helper}(" in source, (name, helper)
        assert "_pr92ClosureAttachmentEvidenceExpression =" not in source, name
        assert "PriorAttachmentEvidenceExpression" not in source, name

    for name in (
        "service_worker_rich_input_schema28_repair_pr9_2.js",
        "service_worker_rich_input_schema29_repair_pr9_2.js",
    ):
        source = _source(name)
        assert "_pr92ClosureAttachmentEvidenceExpression =" not in source, name


def test_write_domain_assembles_evidence_owner_after_schemas_before_staging() -> None:
    write = WRITE.read_text(encoding="utf-8")
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_attachment_evidence.js");'
    staging = 'importScripts("service_worker_attachment_staging.js");'
    lifecycle = 'importScripts("service_worker_rich_input_lifecycle.js");'

    assert schemas in write
    assert owner in write
    assert staging in write
    assert lifecycle in write
    assert write.index(schemas) < write.index(owner) < write.index(staging)
    assert write.index(staging) < write.index(lifecycle)


def test_public_evidence_owner_graduates_schema27_final_generation() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert "_pr92Schema27AttachmentEvidenceExpression(expectedNames)" in owner


def test_explicit_evidence_owner_delegates_once_without_argument_drift() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const calls = [];
function _pr92Schema27AttachmentEvidenceExpression(expectedNames) {{
  calls.push(expectedNames);
  return "schema27-evidence";
}}

{owner}

const expected = ["a.png", "b.txt"];
const result = _pr92ClosureAttachmentEvidenceExpression(expected);
console.log(JSON.stringify({{
  calls,
  result,
  sameExpected: calls[0] === expected
}}));
"""
    result = _run_node(script)
    assert result["result"] == "schema27-evidence"
    assert len(result["calls"]) == 1
    assert result["calls"][0] == ["a.png", "b.txt"]
    assert result["sameExpected"] is True


def test_existing_evidence_read_resolves_the_public_owner_at_call_time() -> None:
    closure = _source("service_worker_rich_input_closure_repair_pr9_2.js")
    assert "expression: _pr92ClosureAttachmentEvidenceExpression(expectedNames)" in closure
