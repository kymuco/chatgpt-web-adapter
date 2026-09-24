from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RUNTIME = EXT / "service_worker_runtime.js"
OWNER = EXT / "service_worker_submit_authority.js"

LAYERS = {
    "service_worker.js": "_cwaBaseSubmitOfficialPageTurn",
    "service_worker_temporary_product.js": "_pr813SubmitOfficialPageTurn",
    "service_worker_rich_input_deadline_repair_pr9_2.js": (
        "_pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry"
    ),
    "service_worker_rich_input_closure_repair_pr9_2.js": (
        "_pr92ClosurePageDeadlineGuardedSubmit"
    ),
    "service_worker_rich_input_schema7_core_pr9_2.js": (
        "_pr92Schema7AtomicAttachmentSubmit"
    ),
    "service_worker_text_submit_commit_hardening_pr11_3.js": (
        "_pr113SubmitOfficialTextWithoutPostCommitRetry"
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


def test_submit_authority_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("async function submitOfficialPageTurn(") == 1
    assert "submitOfficialPageTurn =" not in owner

    for name, helper in LAYERS.items():
        source = _source(name)
        assert helper in source, (name, helper)
        assert "submitOfficialPageTurn =" not in source, name
        assert "PriorSubmitOfficialPageTurn" not in source, name

    assert "async function submitOfficialPageTurn(" not in _source("service_worker.js")


def test_runtime_assembles_submit_owner_after_all_submit_helpers() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    reconciliation = 'importScripts("service_worker_runtime_tab_reconciliation.js");'
    write = 'importScripts("service_worker_runtime_write.js");'
    owner = 'importScripts("service_worker_submit_authority.js");'
    metadata = 'importScripts("service_worker_stream_metadata.js");'

    assert reconciliation in runtime
    assert write in runtime
    assert owner in runtime
    assert metadata in runtime
    assert runtime.index(reconciliation) < runtime.index(write) < runtime.index(owner)
    assert runtime.index(owner) < runtime.index(metadata)


def test_submit_authority_preserves_historical_outer_to_inner_order() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    markers = (
        "_pr113SubmitOfficialTextWithoutPostCommitRetry",
        "_pr92Schema7AtomicAttachmentSubmit",
        "_pr92ClosurePageDeadlineGuardedSubmit",
        "_pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry",
        "_pr813SubmitOfficialPageTurn",
        "_cwaBaseSubmitOfficialPageTurn",
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_submit_composition_preserves_nested_handoff() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const events = [];

function layer(name) {{
  return async (debuggee, timeoutMs, next) => {{
    events.push("enter:" + name + ":" + debuggee.tabId + ":" + timeoutMs);
    const result = await next(
      {{ tabId: debuggee.tabId + 1 }},
      timeoutMs - 1
    );
    events.push("exit:" + name);
    return result;
  }};
}}

const _pr113SubmitOfficialTextWithoutPostCommitRetry = layer("text");
const _pr92Schema7AtomicAttachmentSubmit = layer("schema7");
const _pr92ClosurePageDeadlineGuardedSubmit = layer("closure");
const _pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry = layer("deadline");
const _pr813SubmitOfficialPageTurn = layer("temporary");
const _cwaBaseSubmitOfficialPageTurn = async (debuggee, timeoutMs) => {{
  events.push("base:" + debuggee.tabId + ":" + timeoutMs);
  return {{ strategy: "base", selector: null }};
}};

{owner}

(async () => {{
  const result = await submitOfficialPageTurn({{ tabId: 1 }}, 10);
  console.log(JSON.stringify({{ events, result }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:text:1:10",
        "enter:schema7:2:9",
        "enter:closure:3:8",
        "enter:deadline:4:7",
        "enter:temporary:5:6",
        "base:6:5",
        "exit:temporary",
        "exit:deadline",
        "exit:closure",
        "exit:schema7",
        "exit:text",
    ]
    assert result["result"] == {"strategy": "base", "selector": None}
