from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
HOTFIX = EXT / "service_worker_hotfix.js"
ORDINARY = EXT / "service_worker_ordinary_text_identity_authority.js"
OWNER = EXT / "service_worker_send_command.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_send_command_has_one_public_owner() -> None:
    core = _source(CORE)
    hotfix = _source(HOTFIX)
    ordinary = _source(ORDINARY)
    owner = _source(OWNER)

    assert "async function _cwaBaseSendCommand(" in core
    assert "async function sendCommand(" not in core

    assert "async function _cwaHotfixSendCommand(" in hotfix
    assert "sendCommand =" not in hotfix
    assert "_originalCoreSendCommand" not in hotfix

    assert "function _cwaOrdinaryIdentitySendCommand(" in ordinary
    assert "sendCommand =" not in ordinary
    assert "_cwaOrdinaryIdentityPriorSendCommand" not in ordinary

    assert owner.count("function sendCommand(") == 1
    assert "sendCommand =" not in owner


def test_hotfix_delegates_to_immutable_base_transport() -> None:
    hotfix = _source(HOTFIX)
    start = hotfix.index("async function _cwaHotfixSendCommand")
    block = hotfix[start:]

    assert "_cwaBaseSendCommand(debuggee, method, params)" in block
    assert "_cwaBaseSendCommand(debuggee, method, {" in block
    assert "_runSubmitFallbackLadder(debuggee)" in block
    assert "_cwaHotfixSendCommand(" not in block.split("\n", 1)[1]


def test_ordinary_identity_observes_commit_before_hotfix_delegation() -> None:
    ordinary = _source(ORDINARY)
    start = ordinary.index("function _cwaOrdinaryIdentitySendCommand")
    end = ordinary.index(
        "async function _cwaOrdinaryIdentityExecuteOfficialPageTurn",
        start,
    )
    block = ordinary[start:end]

    boundary = block.index("_cwaOrdinaryIdentityCommitBoundary(method, params)")
    armed = block.index("context.submitArmed = true")
    delegate = block.index("_cwaHotfixSendCommand(debuggee, method, params)")

    assert boundary < armed < delegate


def test_write_domain_installs_send_command_owner_last() -> None:
    write = _source(WRITE)
    authority = 'importScripts("service_worker_ordinary_text_identity_authority.js");'
    owner = 'importScripts("service_worker_send_command.js");'

    assert write.index(authority) < write.index(owner)
    assert write.rstrip().endswith(owner)


def test_public_owner_delegates_once_with_unchanged_arguments() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
function _cwaOrdinaryIdentitySendCommand(debuggee, method, params) {{
  calls.push([debuggee, method, params]);
  return Promise.resolve({{ ok: true }});
}}
{owner}
const debuggee = {{ tabId: 9 }};
const params = {{ expression: "1+1" }};
sendCommand(debuggee, "Runtime.evaluate", params).then((result) => {{
  console.log(JSON.stringify({{
    result,
    count: calls.length,
    sameDebuggee: calls[0][0] === debuggee,
    method: calls[0][1],
    sameParams: calls[0][2] === params
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
        "result": {"ok": True},
        "count": 1,
        "sameDebuggee": True,
        "method": "Runtime.evaluate",
        "sameParams": True,
    }
