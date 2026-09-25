from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker.js"
SCHEMA12 = EXT / "service_worker_rich_input_schema12_repair_pr9_2.js"
OWNER = EXT / "service_worker_submit_readiness.js"
WRITE = EXT / "service_worker_runtime_write.js"
UI_COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"
TEXT_HARDENING = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_submit_readiness_has_one_public_owner() -> None:
    base = _source(BASE)
    schema12 = _source(SCHEMA12)
    owner = _source(OWNER)

    assert "async function _cwaBaseWaitForSendButtonPoint(" in base
    assert "async function waitForSendButtonPoint(" not in base

    assert "async function _pr92Schema12DeadlineBoundedSendReadiness(" in schema12
    assert "_pr92Schema12PriorWaitForSendButtonPoint" not in schema12
    assert "waitForSendButtonPoint =" not in schema12

    assert owner.count("async function waitForSendButtonPoint(") == 1
    assert "waitForSendButtonPoint =" not in owner


def test_schema12_readiness_delegates_to_immutable_base() -> None:
    schema12 = _source(SCHEMA12)
    start = schema12.index("async function _pr92Schema12DeadlineBoundedSendReadiness")
    end = schema12.index("function _pr92Schema12AugmentSupportResult", start)
    block = schema12[start:end]

    assert block.count("_cwaBaseWaitForSendButtonPoint(debuggee, timeoutMs)") == 2
    assert "const context = _pr92ActiveRichInputContext;" in block
    assert '"SCHEMA12_SEND_READINESS_WAIT"' in block
    assert "_pr92Schema7RunUntil(" in block


def test_write_domain_installs_owner_after_schema_helpers_before_context_owner() -> (
    None
):
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_submit_readiness.js");'
    context = 'importScripts("service_worker_turn_context.js");'

    assert write.index(schemas) < write.index(owner) < write.index(context)


def test_ui_compatibility_keeps_separate_ordinary_text_helper() -> None:
    compat = _source(UI_COMPAT)
    hardening = _source(TEXT_HARDENING)

    assert "async function _pr117WaitForSendButtonPoint(" in compat
    assert "waitForSendButtonPoint =" not in compat
    assert 'typeof _pr117WaitForSendButtonPoint === "function"' in hardening
    assert "return _pr117WaitForSendButtonPoint(debuggee, timeoutMs);" in hardening
    assert "return waitForSendButtonPoint(debuggee, timeoutMs);" in hardening


def test_public_owner_delegates_once_without_argument_drift() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
const DEFAULT_SUBMIT_READY_TIMEOUT_MS = 1500;
async function _pr92Schema12DeadlineBoundedSendReadiness(debuggee, timeoutMs) {{
  calls.push([debuggee, timeoutMs]);
  return {{ x: 4, y: 5 }};
}}

{owner}

(async () => {{
  const debuggee = {{ tabId: 7 }};
  const result = await waitForSendButtonPoint(debuggee, 321);
  console.log(JSON.stringify({{
    result,
    calls,
    sameDebuggee: calls[0][0] === debuggee
  }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["result"] == {"x": 4, "y": 5}
    assert result["calls"] == [[{"tabId": 7}, 321]]
    assert result["sameDebuggee"] is True
