from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
DEADLINE = EXT / "service_worker_rich_input_deadline_repair_pr9_2.js"
CLOSURE = EXT / "service_worker_rich_input_closure_repair_pr9_2.js"
OWNER = EXT / "service_worker_raw_submit_primitives.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_raw_submit_primitives_have_one_public_owner() -> None:
    core = _source(CORE)
    deadline = _source(DEADLINE)
    closure = _source(CLOSURE)
    owner = _source(OWNER)

    assert "async function _cwaBaseClickSendButton(" in core
    assert "async function _cwaBaseSubmitWithEnter(" in core
    assert "async function clickSendButton(" not in core
    assert "async function submitWithEnter(" not in core

    assert "async function _pr92ClickSendButtonWithinDeadline(" in deadline
    assert "async function _pr92SubmitWithEnterWithinDeadline(" in deadline
    assert "clickSendButton =" not in deadline
    assert "submitWithEnter =" not in deadline
    assert "_pr92DeadlineRepairPriorClickSendButton" not in deadline
    assert "_pr92DeadlineRepairPriorSubmitWithEnter" not in deadline

    assert "async function _pr92ClosureRejectRawMouseSubmit(" in closure
    assert "async function _pr92ClosureRejectRawEnterSubmit(" in closure
    assert "clickSendButton =" not in closure
    assert "submitWithEnter =" not in closure
    assert "_pr92ClosurePriorClickSendButton" not in closure
    assert "_pr92ClosurePriorSubmitWithEnter" not in closure

    assert owner.count("async function clickSendButton(") == 1
    assert owner.count("async function submitWithEnter(") == 1


def test_deadline_text_only_fallback_is_explicit_base_delegation() -> None:
    deadline = _source(DEADLINE)

    click_start = deadline.index("async function _pr92ClickSendButtonWithinDeadline")
    click_end = deadline.index(
        "async function _pr92SubmitWithEnterWithinDeadline", click_start
    )
    click_block = deadline[click_start:click_end]
    assert "return _cwaBaseClickSendButton(debuggee, point);" in click_block

    enter_start = click_end
    enter_end = deadline.index(
        "async function _pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry",
        enter_start,
    )
    enter_block = deadline[enter_start:enter_end]
    assert "return _cwaBaseSubmitWithEnter(debuggee);" in enter_block


def test_closure_rejects_rich_raw_submit_before_deadline_delegation() -> None:
    closure = _source(CLOSURE)

    mouse_start = closure.index("async function _pr92ClosureRejectRawMouseSubmit")
    enter_start = closure.index(
        "async function _pr92ClosureRejectRawEnterSubmit", mouse_start
    )
    mouse_block = closure[mouse_start:enter_start]
    assert "PR9_2_RICH_INPUT_RAW_MOUSE_SUBMIT_FORBIDDEN" in mouse_block
    assert "_pr92ClickSendButtonWithinDeadline(debuggee, point)" in mouse_block
    assert mouse_block.index(
        "PR9_2_RICH_INPUT_RAW_MOUSE_SUBMIT_FORBIDDEN"
    ) < mouse_block.index("_pr92ClickSendButtonWithinDeadline")

    enter_end = closure.index(
        "async function _pr92ClosurePageDeadlineGuardedSubmit",
        enter_start,
    )
    enter_block = closure[enter_start:enter_end]
    assert "PR9_2_RICH_INPUT_RAW_ENTER_SUBMIT_FORBIDDEN" in enter_block
    assert "_pr92SubmitWithEnterWithinDeadline(debuggee)" in enter_block
    assert enter_block.index(
        "PR9_2_RICH_INPUT_RAW_ENTER_SUBMIT_FORBIDDEN"
    ) < enter_block.index("_pr92SubmitWithEnterWithinDeadline")


def test_base_submit_path_keeps_dynamic_public_primitive_resolution() -> None:
    core = _source(CORE)
    start = core.index("async function _cwaBaseSubmitOfficialPageTurn")
    end = core.index("async function executeOfficialPageTurn", start)
    block = core[start:end]

    assert "await clickSendButton(debuggee, point);" in block
    assert "await submitWithEnter(debuggee);" in block
    assert "_cwaBaseClickSendButton(debuggee, point)" not in block
    assert "_cwaBaseSubmitWithEnter(debuggee)" not in block


def test_write_domain_installs_raw_submit_owner_after_closure() -> None:
    write = _source(WRITE)
    deadline = 'importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");'
    closure = 'importScripts("service_worker_rich_input_closure_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_raw_submit_primitives.js");'
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'

    assert write.index(deadline) < write.index(closure) < write.index(owner)
    assert write.index(owner) < write.index(schemas)


def test_public_owner_delegates_once_with_unchanged_arguments() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
async function _pr92ClosureRejectRawMouseSubmit(debuggee, point) {{
  calls.push(["mouse", debuggee, point]);
  return "mouse";
}}
async function _pr92ClosureRejectRawEnterSubmit(debuggee) {{
  calls.push(["enter", debuggee]);
  return "enter";
}}
{owner}
const debuggee = {{ tabId: 7 }};
const point = {{ x: 1, y: 2 }};
Promise.all([
  clickSendButton(debuggee, point),
  submitWithEnter(debuggee)
]).then((result) => {{
  console.log(JSON.stringify({{
    result,
    count: calls.length,
    sameMouseDebuggee: calls[0][1] === debuggee,
    samePoint: calls[0][2] === point,
    sameEnterDebuggee: calls[1][1] === debuggee
  }}));
}});
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": ["mouse", "enter"],
        "count": 2,
        "sameMouseDebuggee": True,
        "samePoint": True,
        "sameEnterDebuggee": True,
    }
