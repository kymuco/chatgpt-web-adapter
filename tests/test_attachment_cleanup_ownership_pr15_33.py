from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WRITE = EXT / "service_worker_runtime_write.js"
OWNER = EXT / "service_worker_attachment_cleanup.js"

PUBLIC_TO_FINAL = {
    "_pr92PersistDirtyAttachmentFence": "_pr92Schema7PersistDirtyAttachmentFence",
    "_pr92TryClearDirtyAttachmentFence": "_pr92Schema7TryClearDirtyAttachmentFence",
    "_pr92ClearOfficialPageAttachments": "_pr92Schema8ClearFencedRuntimeTab",
}

HISTORICAL_HELPERS = {
    "service_worker_rich_input_pr9_2.js": (
        "_pr92BasePersistDirtyAttachmentFence",
        "_pr92BaseTryClearDirtyAttachmentFence",
        "_pr92BaseClearOfficialPageAttachments",
    ),
    "service_worker_rich_input_deadline_repair_pr9_2.js": (
        "_pr92DeadlineTryClearDirtyAttachmentFence",
        "_pr92DeadlineClearOfficialPageAttachments",
    ),
    "service_worker_rich_input_schema7_core_pr9_2.js": (
        "_pr92Schema7PersistDirtyAttachmentFence",
        "_pr92Schema7TryClearDirtyAttachmentFence",
        "_pr92Schema7ClearFencedRuntimeTab",
    ),
    "service_worker_rich_input_schema8_repair_pr9_2.js": (
        "_pr92Schema8ClearFencedRuntimeTab",
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


def test_attachment_cleanup_has_one_public_owner_and_no_runtime_reassignments() -> None:
    owner = OWNER.read_text(encoding="utf-8")

    for public in PUBLIC_TO_FINAL:
        assert owner.count(f"async function {public}(") == 1
        assert f"{public} =" not in owner

    for name, helpers in HISTORICAL_HELPERS.items():
        source = _source(name)
        for helper in helpers:
            assert f"function {helper}(" in source, (name, helper)
        for public in PUBLIC_TO_FINAL:
            assert re.search(rf"async function {re.escape(public)}\\(", source) is None
            assert re.search(rf"^\\s*{re.escape(public)}\\s*=", source, re.MULTILINE) is None

    deadline = _source("service_worker_rich_input_deadline_repair_pr9_2.js")
    schema7 = _source("service_worker_rich_input_schema7_core_pr9_2.js")
    assert "PriorTryClearDirtyAttachmentFence" not in deadline
    assert "PriorPersistDirtyAttachmentFence" not in schema7
    assert "PriorTryClearDirtyAttachmentFence" not in schema7
    assert "PriorClearOfficialPageAttachments" not in schema7


def test_write_domain_assembles_cleanup_owner_after_schemas_before_staging() -> None:
    write = WRITE.read_text(encoding="utf-8")
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    evidence = 'importScripts("service_worker_attachment_evidence.js");'
    owner = 'importScripts("service_worker_attachment_cleanup.js");'
    staging = 'importScripts("service_worker_attachment_staging.js");'
    lifecycle = 'importScripts("service_worker_rich_input_lifecycle.js");'

    for item in (schemas, evidence, owner, staging, lifecycle):
        assert item in write
    assert (
        write.index(schemas)
        < write.index(evidence)
        < write.index(owner)
        < write.index(staging)
        < write.index(lifecycle)
    )


def test_public_cleanup_owner_graduates_final_effective_generations() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    for public, final in PUBLIC_TO_FINAL.items():
        assert public in owner
        assert final in owner

    assert "_pr92Schema7PersistDirtyAttachmentFence(tabId)" in owner
    assert "_pr92Schema7TryClearDirtyAttachmentFence()" in owner
    assert "_pr92Schema8ClearFencedRuntimeTab(tabId, timeoutMs)" in owner


def test_explicit_cleanup_owner_delegates_once_without_argument_drift() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const calls = [];
async function _pr92Schema7PersistDirtyAttachmentFence(tabId) {{
  calls.push(["persist", tabId]);
  return "persisted";
}}
async function _pr92Schema7TryClearDirtyAttachmentFence() {{
  calls.push(["clear-fence"]);
  return "cleared";
}}
async function _pr92Schema8ClearFencedRuntimeTab(tabId, timeoutMs) {{
  calls.push(["cleanup", tabId, timeoutMs]);
  return "cleaned";
}}

{owner}

(async () => {{
  const persisted = await _pr92PersistDirtyAttachmentFence(41);
  const cleared = await _pr92TryClearDirtyAttachmentFence();
  const cleaned = await _pr92ClearOfficialPageAttachments(42, 900);
  console.log(JSON.stringify({{ calls, persisted, cleared, cleaned }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["calls"] == [
        ["persist", 41],
        ["clear-fence"],
        ["cleanup", 42, 900],
    ]
    assert result["persisted"] == "persisted"
    assert result["cleared"] == "cleared"
    assert result["cleaned"] == "cleaned"


def test_existing_attachment_consumers_resolve_public_owner_at_call_time() -> None:
    base = _source("service_worker_rich_input_pr9_2.js")

    assert "await _pr92PersistDirtyAttachmentFence(tabId);" in base
    assert "await _pr92ClearOfficialPageAttachments(" in base
    assert "await _pr92TryClearDirtyAttachmentFence()" in base
