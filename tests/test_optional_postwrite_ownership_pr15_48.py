from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

SCHEMA17 = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"
SCHEMA18 = EXT / "service_worker_rich_input_schema18_repair_pr9_2.js"
SCHEMA19 = EXT / "service_worker_rich_input_schema19_repair_pr9_2.js"
OWNER = EXT / "service_worker_optional_postwrite.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_optional_postwrite_has_one_public_owner_and_no_runtime_reassignment() -> None:
    schema17 = _source(SCHEMA17)
    schema18 = _source(SCHEMA18)
    schema19 = _source(SCHEMA19)
    owner = _source(OWNER)

    assert "async function _pr92Schema17BaseOptionalPostWrite(" in schema17
    assert "async function _pr92Schema17OptionalPostWrite(" not in schema17

    assert (
        "async function _pr92Schema18OptionalPostWriteWithIdentityReserve("
        in schema18
    )
    assert "_pr92Schema17OptionalPostWrite =" not in schema18

    assert "async function _pr92Schema19OptionalPostWrite(" in schema19
    assert "_pr92Schema17OptionalPostWrite =" not in schema19
    assert "_pr92Schema19PriorOptionalPostWrite" not in schema19

    assert owner.count("async function _pr92Schema17OptionalPostWrite(") == 1
    assert "_pr92Schema17OptionalPostWrite =" not in owner


def test_schema19_fallback_delegates_explicitly_to_schema18_policy() -> None:
    schema19 = _source(SCHEMA19)
    start = schema19.index("async function _pr92Schema19OptionalPostWrite")
    end = schema19.index(
        "async function _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity",
        start,
    )
    block = schema19[start:end]

    assert 'stage === "SCHEMA17_POSTWRITE_RESPONSE_BODY"' in block
    assert "context?.schema19RequestedConversationId == null" in block
    assert "_pr92Schema18OptionalPostWriteWithIdentityReserve(" in block
    assert "_pr92Schema19PriorOptionalPostWrite" not in block


def test_new_chat_causal_response_body_keeps_schema19_budget_authority() -> None:
    schema19 = _source(SCHEMA19)
    start = schema19.index("async function _pr92Schema19OptionalPostWrite")
    end = schema19.index(
        "async function _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity",
        start,
    )
    block = schema19[start:end]

    assert "PR92_SCHEMA19_CAUSAL_RESPONSE_BODY_CAP_MS" in block
    assert "remaining - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS" in block
    assert "context.deadlineAt - PR92_SCHEMA19_RPC_RETURN_RESERVE_MS" in block
    assert "_pr92Schema7RunUntil(localDeadlineAt, stage, operation)" in block


def test_schema17_consumers_continue_to_call_public_owner() -> None:
    schema17 = _source(SCHEMA17)

    assert schema17.count("_pr92Schema17OptionalPostWrite(") == 3
    assert '"SCHEMA17_POSTWRITE_RESPONSE_BODY"' in schema17
    assert '"SCHEMA17_POSTWRITE_FINAL_TAB"' in schema17
    assert '"SCHEMA17_POSTWRITE_COMPOSER_READINESS"' in schema17


def test_write_domain_installs_owner_after_schema_helpers_before_consumers() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_optional_postwrite.js");'
    submit = 'importScripts("service_worker_submit_readiness.js");'

    assert write.index(schemas) < write.index(owner) < write.index(submit)


def test_public_owner_delegates_once_without_argument_drift() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
const PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS = 1000;
async function _pr92Schema19OptionalPostWrite(context, stage, operation, capMs) {{
  calls.push([context, stage, capMs]);
  return operation();
}}

{owner}

(async () => {{
  const context = {{ deadlineAt: 123 }};
  const operation = () => ({{ ok: true }});
  const result = await _pr92Schema17OptionalPostWrite(
    context,
    "POSTWRITE",
    operation,
    777
  );
  console.log(JSON.stringify({{
    result,
    calls,
    sameContext: calls[0][0] === context
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

    assert result["result"] == {"ok": True}
    assert result["calls"] == [[{"deadlineAt": 123}, "POSTWRITE", 777]]
    assert result["sameContext"] is True
