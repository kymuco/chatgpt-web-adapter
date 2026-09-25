from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

BASE = EXT / "service_worker_browser_response_stream.js"
EARLY = EXT / "service_worker_early_response_completion.js"
ACTIVITY = EXT / "service_worker_response_activity.js"
TEMPORARY = EXT / "service_worker_temporary_product.js"
OWNER = EXT / "service_worker_response_stream_hooks.js"
ASSEMBLY = EXT / "service_worker_observability.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_response_stream_hooks_have_one_final_public_owner() -> None:
    base = _source(BASE)
    early = _source(EARLY)
    activity = _source(ACTIVITY)
    temporary = _source(TEMPORARY)
    owner = _source(OWNER)

    assert "function _pr89BaseBrowserStreamVisibleAssistantText(" in base
    assert "async function _pr89BaseBrowserStreamProcessSseEvent(" in base
    assert "async function _pr89BaseBrowserStreamRecordAssistant(" in base

    for source in (base, early, activity, temporary):
        assert "_pr89BrowserStreamProcessSseEvent =" not in source
        assert "_pr89BrowserStreamVisibleAssistantText =" not in source
        assert "_pr89BrowserStreamRecordAssistant =" not in source

    assert owner.count("async function _pr89BrowserStreamProcessSseEvent(") == 1
    assert owner.count("function _pr89BrowserStreamVisibleAssistantText(") == 1
    assert owner.count("async function _pr89BrowserStreamRecordAssistant(") == 1


def test_explicit_stream_helper_chain_matches_historical_nesting() -> None:
    early = _source(EARLY)
    activity = _source(ACTIVITY)
    temporary = _source(TEMPORARY)
    owner = _source(OWNER)

    assert "_pr89BaseBrowserStreamRecordAssistant" in early
    assert "_pr89BaseBrowserStreamProcessSseEvent" in early

    assert "_pr811ProcessSseEventOwner" in activity
    assert "_pr89BaseBrowserStreamVisibleAssistantText" in activity
    assert "_pr811RecordAssistantOwner" in activity

    assert "return _pr812ProcessSseEventOwner(context, block);" in temporary

    assert (
        "return _pr813ProcessSseWithTemporarySessionIdentity(context, block);"
        in owner
    )
    assert "return _pr812VisibleAssistantTextOwner(message);" in owner
    assert "return _pr812RecordAssistantOwner(context, candidate);" in owner


def test_final_stream_owner_loads_after_temporary_product() -> None:
    assembly = _source(ASSEMBLY)
    temporary = 'importScripts("service_worker_temporary_product.js");'
    owner = 'importScripts("service_worker_response_stream_hooks.js");'
    lifecycle = 'importScripts("service_worker_temporary_lifecycle.js");'

    assert assembly.index(temporary) < assembly.index(owner) < assembly.index(lifecycle)


def test_public_stream_owner_delegates_without_argument_drift() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
const calls = [];
async function _pr813ProcessSseWithTemporarySessionIdentity(context, block) {{
  calls.push(["process", context, block]);
  return "processed";
}}
function _pr812VisibleAssistantTextOwner(message) {{
  calls.push(["visible", message]);
  return {{ text: "answer" }};
}}
async function _pr812RecordAssistantOwner(context, candidate) {{
  calls.push(["record", context, candidate]);
  return "recorded";
}}

{owner}

(async () => {{
  const context = {{ id: "ctx" }};
  const message = {{ id: "message" }};
  const candidate = {{ text: "answer" }};
  const processResult = await _pr89BrowserStreamProcessSseEvent(context, "block");
  const visibleResult = _pr89BrowserStreamVisibleAssistantText(message);
  const recordResult = await _pr89BrowserStreamRecordAssistant(context, candidate);
  console.log(JSON.stringify({{
    processResult,
    visibleResult,
    recordResult,
    calls
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

    assert result["processResult"] == "processed"
    assert result["visibleResult"] == {"text": "answer"}
    assert result["recordResult"] == "recorded"
    assert result["calls"] == [
        ["process", {"id": "ctx"}, "block"],
        ["visible", {"id": "message"}],
        ["record", {"id": "ctx"}, {"text": "answer"}],
    ]
