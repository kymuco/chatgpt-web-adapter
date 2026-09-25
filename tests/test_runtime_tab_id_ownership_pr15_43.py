from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
RECONCILIATION = EXT / "service_worker_runtime_tab_reconciliation.js"
OWNER = EXT / "service_worker_runtime_tab_id.js"
RUNTIME = EXT / "service_worker_runtime.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_tab_id_has_one_public_owner() -> None:
    core = _source(CORE)
    reconciliation = _source(RECONCILIATION)
    owner = _source(OWNER)

    assert "async function _cwaBaseStoredRuntimeTabId()" in core
    assert "async function storedRuntimeTabId()" not in core

    assert (
        "async function _pr824a3StoredRuntimeTabIdWithLiveValidation()"
        in reconciliation
    )
    assert "storedRuntimeTabId =" not in reconciliation
    assert "_pr824a3RawStoredRuntimeTabId" not in reconciliation

    assert owner.count("async function storedRuntimeTabId()") == 1
    assert "storedRuntimeTabId =" not in owner


def test_reconciliation_uses_immutable_base_reader_for_raw_state() -> None:
    reconciliation = _source(RECONCILIATION)

    assert reconciliation.count("_cwaBaseStoredRuntimeTabId()") >= 3
    assert "_pr824a3RawStoredRuntimeTabId" not in reconciliation


def test_initial_native_hello_preserves_raw_persisted_id_read() -> None:
    core = _source(CORE)
    start = core.index("function _cwaBaseConnectNativeBridge()")
    end = core.index("chrome.runtime.onInstalled.addListener", start)
    block = core[start:end]

    assert "_cwaBaseStoredRuntimeTabId().then((runtimeTabId) => {" in block
    assert "storedRuntimeTabId().then((runtimeTabId) => {" not in block


def test_runtime_tab_consumers_still_resolve_public_validated_owner() -> None:
    core = _source(CORE)

    ensure_start = core.index("async function _cwaBaseEnsureRuntimeTab")
    ensure_end = core.index("chrome.tabs.onRemoved.addListener", ensure_start)
    ensure_block = core[ensure_start:ensure_end]
    assert "const storedId = await storedRuntimeTabId();" in ensure_block
    assert "_cwaBaseStoredRuntimeTabId()" not in ensure_block

    removed_start = ensure_end
    removed_end = core.index("async function queryComposerReadiness", removed_start)
    removed_block = core[removed_start:removed_end]
    assert "const storedId = await storedRuntimeTabId();" in removed_block
    assert "_cwaBaseStoredRuntimeTabId()" not in removed_block


def test_runtime_installs_tab_id_owner_immediately_after_reconciliation() -> None:
    runtime = _source(RUNTIME)
    reconciliation = 'importScripts("service_worker_runtime_tab_reconciliation.js");'
    owner = 'importScripts("service_worker_runtime_tab_id.js");'
    write = 'importScripts("service_worker_runtime_write.js");'

    assert runtime.index(reconciliation) < runtime.index(owner) < runtime.index(write)


def test_public_owner_delegates_once() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
let calls = 0;
async function _pr824a3StoredRuntimeTabIdWithLiveValidation() {{
  calls += 1;
  return 17;
}}
{owner}
storedRuntimeTabId().then((value) => {{
  console.log(JSON.stringify({{ value, calls }}));
}});
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {"value": 17, "calls": 1}
