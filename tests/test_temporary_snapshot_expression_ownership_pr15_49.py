from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker_temporary_chat.js"
STATE = EXT / "service_worker_temporary_chat_state_semantics.js"
OWNER = EXT / "service_worker_temporary_snapshot_expression.js"
RUNTIME = EXT / "service_worker_runtime.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_temporary_snapshot_expression_has_one_public_owner() -> None:
    base = _source(BASE)
    state = _source(STATE)
    owner = _source(OWNER)

    assert "function _pr87BaseTemporaryControlSnapshotExpression()" in base
    assert "function _pr87TemporaryControlSnapshotExpression()" not in base
    assert 'importScripts("service_worker_temporary_snapshot_expression.js");' in base

    assert (
        "function _pr87TemporaryControlSnapshotExpressionWithAriaActionState()" in state
    )
    assert "_pr87TemporaryControlSnapshotExpression =" not in state

    assert owner.count("function _pr87TemporaryControlSnapshotExpression()") == 1
    assert "_pr87TemporaryControlSnapshotExpression =" not in owner


def test_owner_prefers_aria_action_helper_and_preserves_base_fallback() -> None:
    owner = _source(OWNER)

    assert (
        'typeof _pr87TemporaryControlSnapshotExpressionWithAriaActionState === "function"'
        in owner
    )
    assert (
        "return _pr87TemporaryControlSnapshotExpressionWithAriaActionState();" in owner
    )
    assert "return _pr87BaseTemporaryControlSnapshotExpression();" in owner


def test_snapshot_owner_remains_detached_from_production_runtime() -> None:
    runtime = _source(RUNTIME)

    assert "service_worker_temporary_snapshot_expression.js" not in runtime
    assert "service_worker_temporary_chat.js" not in runtime
    assert "service_worker_temporary_chat_state_semantics.js" not in runtime


def test_owner_selects_base_then_loaded_state_helper_without_rebinding() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = """
const vm = require("vm");
const context = {
  calls: [],
  _pr87BaseTemporaryControlSnapshotExpression() {
    context.calls.push("base");
    return "BASE";
  }
};
vm.createContext(context);
vm.runInContext(__OWNER_SOURCE__, context);

const before = vm.runInContext(
  "_pr87TemporaryControlSnapshotExpression()",
  context
);
vm.runInContext(
  "function _pr87TemporaryControlSnapshotExpressionWithAriaActionState() {" +
  " calls.push('state'); return 'STATE'; }",
  context
);
const after = vm.runInContext(
  "_pr87TemporaryControlSnapshotExpression()",
  context
);

console.log(JSON.stringify({ before, after, calls: context.calls }));
""".replace("__OWNER_SOURCE__", json.dumps(owner))
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "before": "BASE",
        "after": "STATE",
        "calls": ["base", "state"],
    }
