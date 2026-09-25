from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker_rich_input_schema7_core_pr9_2.js"
SCHEMA20 = EXT / "service_worker_rich_input_schema20_repair_pr9_2.js"
SCHEMA21 = EXT / "service_worker_rich_input_schema21_repair_pr9_2.js"
OWNER = EXT / "service_worker_protected_submit_expression.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_protected_submit_expression_has_one_public_owner() -> None:
    base = _source(BASE)
    schema20 = _source(SCHEMA20)
    schema21 = _source(SCHEMA21)
    owner = _source(OWNER)

    assert "function _pr92Schema7BaseAtomicAttachmentSubmitExpression(" in base
    assert "function _pr92Schema7AtomicAttachmentSubmitExpression(" not in base

    assert "function _pr92Schema20PageSideArmProtectedSubmit(" in schema20
    assert "_pr92Schema7AtomicAttachmentSubmitExpression =" not in schema20
    assert "_pr92Schema20PriorAtomicAttachmentSubmitExpression" not in schema20

    assert "function _pr92Schema21ValidatedClickBoundaryArm(" in schema21
    assert "_pr92Schema7AtomicAttachmentSubmitExpression =" not in schema21
    assert "_pr92Schema20PriorAtomicAttachmentSubmitExpression" not in schema21

    assert owner.count(
        "function _pr92Schema7AtomicAttachmentSubmitExpression("
    ) == 1
    assert "_pr92Schema7AtomicAttachmentSubmitExpression =" not in owner


def test_schema21_explicitly_bypasses_schema20_early_marker_helper() -> None:
    schema21 = _source(SCHEMA21)
    start = schema21.index("function _pr92Schema21ValidatedClickBoundaryArm")
    end = schema21.index("function _pr92Schema21AugmentSupportResult", start)
    block = schema21[start:end]

    assert "_pr92Schema7BaseAtomicAttachmentSubmitExpression(" in block
    assert "_pr92Schema20PageSideArmProtectedSubmit(" not in block
    assert "PR92_SCHEMA21_CLICK_NEEDLE" in block


def test_write_domain_installs_owner_immediately_after_rich_schema_loader() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_protected_submit_expression.js");'
    evidence = 'importScripts("service_worker_attachment_evidence.js");'

    assert write.index(schemas) < write.index(owner) < write.index(evidence)


def test_owner_delegates_once_with_unchanged_arguments() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
function _pr92Schema21ValidatedClickBoundaryArm(selector, deadlineEpochMs, expectedNames) {{
  calls.push([selector, deadlineEpochMs, expectedNames]);
  return "expression";
}}
{owner}
const names = ["a.png", "b.txt"];
const result = _pr92Schema7AtomicAttachmentSubmitExpression(
  "#send",
  12345,
  names
);
console.log(JSON.stringify({{
  result,
  count: calls.length,
  selector: calls[0][0],
  deadline: calls[0][1],
  sameNames: calls[0][2] === names
}}));
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": "expression",
        "count": 1,
        "selector": "#send",
        "deadline": 12345,
        "sameNames": True,
    }


def test_schema7_runtime_consumer_keeps_dynamic_public_resolution() -> None:
    base = _source(BASE)
    assert (
        "const expression = _pr92Schema7AtomicAttachmentSubmitExpression("
        in base
    )
