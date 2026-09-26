from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RUNTIME = EXT / "service_worker_runtime.js"
OWNER = EXT / "service_worker_native_message_router.js"

LAYERS = {
    "service_worker.js": "_cwaBaseOnNativeMessage",
    "service_worker_product_surface_pr11_0.js": "_cwaOnNativeMessageWithProductState",
    "service_worker_runtime_tab_reconciliation.js": (
        "_pr88OnNativeMessageWithBrowserAuthorityLease"
    ),
    "service_worker_google_translate_capability.js": (
        "_cwaOnNativeMessageWithGoogleTranslate"
    ),
    "service_worker_canonical_read_v2.js": "_cwaOnNativeMessageWithCanonicalRead",
    "service_worker_ui_liveness.js": "_cwaOnNativeMessageWithUiLiveness",
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


def test_native_message_router_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("async function onNativeMessage(") == 1
    assert "onNativeMessage =" not in owner

    for name, helper in LAYERS.items():
        source = _source(name)
        assert helper in source, (name, helper)
        assert "onNativeMessage =" not in source, name
        assert "PriorOnNativeMessage" not in source, name

    assert "async function onNativeMessage(" not in _source("service_worker.js")


def test_runtime_assembles_native_message_owner_after_all_route_helpers() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    read = 'importScripts("service_worker_runtime_read.js");'
    observation = 'importScripts("service_worker_runtime_observation.js");'
    owner = 'importScripts("service_worker_native_message_router.js");'
    page_turn = 'importScripts("service_worker_official_page_turn_lifecycle.js");'

    assert read in runtime
    assert observation in runtime
    assert owner in runtime
    assert page_turn in runtime
    assert runtime.index(read) < runtime.index(observation) < runtime.index(owner)
    assert runtime.index(owner) < runtime.index(page_turn)


def test_native_message_router_preserves_historical_outer_to_inner_order() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    markers = (
        "_cwaOnNativeMessageWithUiLiveness",
        "_cwaOnNativeMessageWithCanonicalRead",
        "_pr88OnNativeMessageWithBrowserAuthorityLease",
        "_cwaOnNativeMessageWithGoogleTranslate",
        "_cwaOnNativeMessageWithProductState",
        "_cwaBaseOnNativeMessage",
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_native_message_router_preserves_nested_handoff() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const events = [];

function layer(name) {{
  return async (message, port, next) => {{
    events.push("enter:" + name + ":" + message.type);
    const result = await next({{ ...message, type: message.type + ":" + name }}, port);
    events.push("exit:" + name);
    return result;
  }};
}}

const _cwaOnNativeMessageWithUiLiveness = layer("ui");
const _cwaOnNativeMessageWithCanonicalRead = layer("canonical");
const _pr88OnNativeMessageWithBrowserAuthorityLease = layer("release");
const _cwaOnNativeMessageWithGoogleTranslate = layer("capability");
const _cwaOnNativeMessageWithProductState = layer("product");
const _cwaBaseOnNativeMessage = async (message) => {{
  events.push("base:" + message.type);
  return {{ type: message.type }};
}};

{owner}

(async () => {{
  const result = await onNativeMessage({{ type: "turn" }}, {{}});
  console.log(JSON.stringify({{ events, result }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:ui:turn",
        "enter:canonical:turn:ui",
        "enter:release:turn:ui:canonical",
        "enter:capability:turn:ui:canonical:release",
        "enter:product:turn:ui:canonical:release:capability",
        "base:turn:ui:canonical:release:capability:product",
        "exit:product",
        "exit:capability",
        "exit:release",
        "exit:canonical",
        "exit:ui",
    ]
    assert (
        result["result"]["type"]
        == "turn:ui:canonical:release:capability:product"
    )
