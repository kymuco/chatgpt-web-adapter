from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker_rich_input_pr9_2.js"
SCHEMA16 = EXT / "service_worker_rich_input_schema16_repair_pr9_2.js"
OWNER = EXT / "service_worker_attachment_fence_read.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dirty_fence_read_has_one_public_owner_and_no_runtime_reassignment() -> None:
    base = _source(BASE)
    schema16 = _source(SCHEMA16)
    owner = _source(OWNER)

    assert "async function _pr92BaseReadDirtyAttachmentFence(" in base
    assert "async function _pr92ReadDirtyAttachmentFence(" not in base

    assert (
        "async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline(" in schema16
    )
    assert "_pr92ReadDirtyAttachmentFence =" not in schema16

    assert owner.count("async function _pr92ReadDirtyAttachmentFence(") == 1
    assert "_pr92ReadDirtyAttachmentFence =" not in owner


def test_schema16_non_active_path_delegates_to_immutable_base() -> None:
    schema16 = _source(SCHEMA16)
    start = schema16.index(
        "async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline"
    )
    end = schema16.index(
        "async function _pr92Schema16ResolveRuntimeTabWithinRichDeadline", start
    )
    block = schema16[start:end]

    assert "const context = _pr92ActiveTurnContext;" in block
    assert "if (context === null)" in block
    assert "return _pr92BaseReadDirtyAttachmentFence();" in block


def test_schema16_active_path_mutates_state_only_after_deadline_bounded_read() -> None:
    schema16 = _source(SCHEMA16)
    start = schema16.index(
        "async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline"
    )
    end = schema16.index(
        "async function _pr92Schema16ResolveRuntimeTabWithinRichDeadline", start
    )
    block = schema16[start:end]

    race = block.index("const stored = await _pr92Schema7RunUntil(")
    decode = block.index("const record = stored?.[PR92_DIRTY_ATTACHMENT_STORAGE_KEY];")
    mutation = block.index("_pr92DirtyAttachmentTabId = tabId;")

    assert race < decode < mutation
    assert '"SCHEMA16_STALE_ATTACHMENT_FENCE_READ"' in block
    assert "() => chrome.storage.local.get(PR92_DIRTY_ATTACHMENT_STORAGE_KEY)" in block


def test_write_domain_installs_fence_read_owner_after_schemas_before_cleanup() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    readiness = 'importScripts("service_worker_attachment_readiness.js");'
    owner = 'importScripts("service_worker_attachment_fence_read.js");'
    cleanup = 'importScripts("service_worker_attachment_cleanup.js");'

    assert write.index(schemas) < write.index(readiness)
    assert write.index(readiness) < write.index(owner) < write.index(cleanup)


def test_public_owner_delegates_once_without_argument_or_result_drift() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
async function _pr92Schema16ReadDirtyAttachmentFenceWithinDeadline() {{
  calls.push("schema16");
  return 42;
}}

{owner}

(async () => {{
  const result = await _pr92ReadDirtyAttachmentFence();
  console.log(JSON.stringify({{ result, calls }}));
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

    assert result == {"result": 42, "calls": ["schema16"]}
