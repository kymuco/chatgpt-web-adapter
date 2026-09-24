from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RUNTIME = EXT / "service_worker_runtime.js"
OWNER = EXT / "service_worker_runtime_tab_resolution.js"

LAYERS = {
    "service_worker.js": "_cwaBaseEnsureRuntimeTab",
    "service_worker_phase_timing_pr8_8.js": "_pr88ResolveRuntimeTabWithPhaseTiming",
    "service_worker_temporary_product.js": "_pr813ResolveRuntimeTab",
    "service_worker_retained_conversation_tabs.js": "_pr148ResolveRuntimeTab",
    "service_worker_rich_input_schema16_repair_pr9_2.js": (
        "_pr92Schema16ResolveRuntimeTabWithinRichDeadline"
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


def test_runtime_tab_resolution_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("async function ensureRuntimeTab(") == 1
    assert "ensureRuntimeTab =" not in owner

    for name, helper in LAYERS.items():
        source = _source(name)
        assert helper in source, (name, helper)
        assert "ensureRuntimeTab =" not in source, name
        assert "PriorEnsureRuntimeTab" not in source, name

    assert "async function ensureRuntimeTab(" not in _source("service_worker.js")


def test_runtime_assembles_owner_after_all_resolution_helpers() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    reconciliation = 'importScripts("service_worker_runtime_tab_reconciliation.js");'
    write = 'importScripts("service_worker_runtime_write.js");'
    owner = 'importScripts("service_worker_runtime_tab_resolution.js");'
    read = 'importScripts("service_worker_runtime_read.js");'

    assert reconciliation in runtime
    assert write in runtime
    assert owner in runtime
    assert read in runtime
    assert runtime.index(reconciliation) < runtime.index(write) < runtime.index(owner)
    assert runtime.index(owner) < runtime.index(read)


def test_runtime_tab_resolution_preserves_historical_outer_to_inner_order() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    markers = (
        "_pr92Schema16ResolveRuntimeTabWithinRichDeadline",
        "_pr148ResolveRuntimeTab",
        "_pr813ResolveRuntimeTab",
        "_pr88ResolveRuntimeTabWithPhaseTiming",
        "_cwaBaseEnsureRuntimeTab",
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_runtime_tab_composition_preserves_nested_handoff() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const events = [];

function layer(name) {{
  return async (conversationId, next) => {{
    events.push("enter:" + name + ":" + conversationId);
    const result = await next(conversationId + ":" + name);
    events.push("exit:" + name);
    return result;
  }};
}}

const _pr92Schema16ResolveRuntimeTabWithinRichDeadline = layer("schema16");
const _pr148ResolveRuntimeTab = layer("retained");
const _pr813ResolveRuntimeTab = layer("temporary");
const _pr88ResolveRuntimeTabWithPhaseTiming = layer("phase");
const _cwaBaseEnsureRuntimeTab = async (conversationId) => {{
  events.push("base:" + conversationId);
  return {{ conversationId }};
}};

{owner}

(async () => {{
  const result = await ensureRuntimeTab("conversation");
  console.log(JSON.stringify({{ events, result }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:schema16:conversation",
        "enter:retained:conversation:schema16",
        "enter:temporary:conversation:schema16:retained",
        "enter:phase:conversation:schema16:retained:temporary",
        "base:conversation:schema16:retained:temporary:phase",
        "exit:phase",
        "exit:temporary",
        "exit:retained",
        "exit:schema16",
    ]
    assert result["result"]["conversationId"] == (
        "conversation:schema16:retained:temporary:phase"
    )
