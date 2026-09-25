from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
RECOVERY = EXT / "service_worker_recovery.js"
RICH = EXT / "service_worker_rich_input_pr9_2.js"
OWNER = EXT / "service_worker_recovery_deadline.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_recovery_deadline_hooks_have_one_public_owner() -> None:
    core = _source(CORE)
    recovery = _source(RECOVERY)
    rich = _source(RICH)
    owner = _source(OWNER)

    assert "async function _cwaBaseWaitForTabComplete(" in core
    assert "async function waitForTabComplete(" not in core

    assert "async function _pr811BaseReloadRuntimeTabAndWait(" in recovery
    assert "async function _pr811BaseMaybeRecoverStaleRuntimeUi(" in recovery
    assert "async function _pr811ReloadRuntimeTabAndWait(" not in recovery
    assert "async function _pr811MaybeRecoverStaleRuntimeUi(" not in recovery

    assert "async function _pr92WaitForTabCompleteWithinTurn(" in rich
    assert "async function _pr92ReloadRuntimeTabWithinTurn(" in rich
    assert "async function _pr92RecoverThenStage(" in rich
    assert "waitForTabComplete =" not in rich
    assert "_pr811ReloadRuntimeTabAndWait =" not in rich
    assert "_pr811MaybeRecoverStaleRuntimeUi =" not in rich
    assert "_pr92PriorWaitForTabComplete" not in rich
    assert "_pr92PriorReloadRuntimeTabAndWait" not in rich
    assert "_pr92PriorMaybeRecoverStaleRuntimeUi" not in rich

    assert owner.count("async function waitForTabComplete(") == 1
    assert owner.count("async function _pr811ReloadRuntimeTabAndWait(") == 1
    assert owner.count("async function _pr811MaybeRecoverStaleRuntimeUi(") == 1


def test_rich_helpers_delegate_to_immutable_bases() -> None:
    rich = _source(RICH)

    wait_start = rich.index("async function _pr92WaitForTabCompleteWithinTurn")
    page_turn_start = rich.index(
        "async function _pr92ExecuteOfficialPageTurnWithinTurn", wait_start
    )
    wait_block = rich[wait_start:page_turn_start]
    assert wait_block.count("_cwaBaseWaitForTabComplete(") == 2

    reload_start = rich.index("async function _pr92ReloadRuntimeTabWithinTurn")
    dirty_start = rich.index("async function _pr92ReadDirtyAttachmentFence", reload_start)
    reload_block = rich[reload_start:dirty_start]
    assert "_pr811BaseReloadRuntimeTabAndWait(" in reload_block

    recover_start = rich.index("async function _pr92RecoverThenStage")
    support_start = rich.index("function _pr92RichInputBaseSupportResult", recover_start)
    recover_block = rich[recover_start:support_start]
    assert "_pr811BaseMaybeRecoverStaleRuntimeUi(message)" in recover_block


def test_base_recovery_reenters_public_reload_owner() -> None:
    recovery = _source(RECOVERY)
    start = recovery.index("async function _pr811BaseMaybeRecoverStaleRuntimeUi")
    end = recovery.index(
        "async function _executeOfficialPageTurnWithEarlyTerminalBoundary", start
    )
    block = recovery[start:end]

    assert "_pr811ReloadRuntimeTabAndWait(tab.id, conversationId)" in block
    assert "_pr811BaseReloadRuntimeTabAndWait(tab.id, conversationId)" not in block


def test_support_gate_checks_base_helpers_without_prior_aliases() -> None:
    rich = _source(RICH)
    start = rich.index("const PR92_TOTAL_DEADLINE_HOOKS_AVAILABLE")
    end = rich.index("let _pr92ActiveTurnContext", start)
    block = rich[start:end]

    assert 'typeof _pr811BaseMaybeRecoverStaleRuntimeUi === "function"' in block
    assert 'typeof _pr811BaseReloadRuntimeTabAndWait === "function"' in block
    assert 'typeof _cwaBaseWaitForTabComplete === "function"' in block
    assert "Prior" not in block


def test_write_domain_installs_owner_after_rich_base_overlay() -> None:
    write = _source(WRITE)
    retained = 'importScripts("service_worker_retained_conversation_tabs.js");'
    rich = 'importScripts("service_worker_rich_input_pr9_2.js");'
    owner = 'importScripts("service_worker_recovery_deadline.js");'
    deadline = 'importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");'

    assert write.index(retained) < write.index(rich) < write.index(owner)
    assert write.index(owner) < write.index(deadline)


def test_public_owner_delegates_once_to_each_explicit_helper() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];

async function _pr92WaitForTabCompleteWithinTurn(tabId, timeoutMs) {{
  calls.push(["wait", tabId, timeoutMs]);
  return {{ id: tabId }};
}}
async function _pr92ReloadRuntimeTabWithinTurn(tabId, conversationId) {{
  calls.push(["reload", tabId, conversationId]);
  return 17;
}}
async function _pr92RecoverThenStage(message) {{
  calls.push(["recover", message]);
  return {{ runtimeReloaded: false }};
}}

{owner}

const message = {{ text: "hello" }};
Promise.all([
  waitForTabComplete(7, 1234),
  _pr811ReloadRuntimeTabAndWait(8, "cid"),
  _pr811MaybeRecoverStaleRuntimeUi(message)
]).then((result) => {{
  console.log(JSON.stringify({{
    result,
    calls,
    sameMessage: calls[2][1] === message
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
        "result": [{"id": 7}, 17, {"runtimeReloaded": False}],
        "calls": [
            ["wait", 7, 1234],
            ["reload", 8, "cid"],
            ["recover", {"text": "hello"}],
        ],
        "sameMessage": True,
    }
