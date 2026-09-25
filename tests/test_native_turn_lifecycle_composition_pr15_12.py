from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RUNTIME = EXT / "service_worker_runtime.js"
OWNER = EXT / "service_worker_native_turn_lifecycle.js"

DOMAIN_LAYERS = (
    "service_worker_ordinary_text_identity_authority.js",
    "service_worker_rich_input_lifecycle.js",
    "service_worker_runtime_tab_reconciliation.js",
    "service_worker_temporary_lifecycle.js",
    "service_worker_response_lifecycle.js",
    "service_worker_selection_lifecycle.js",
    "service_worker_recovery.js",
)


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


def test_active_domain_layers_do_not_mutate_native_turn() -> None:
    for name in DOMAIN_LAYERS:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "= executeNativeTurn;" not in source, name


def test_runtime_loads_single_native_turn_owner_last() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    imports = [
        line.strip()
        for line in runtime.splitlines()
        if line.strip().startswith("importScripts(")
    ]
    assert imports[-1] == 'importScripts("service_worker_native_turn_lifecycle.js");'

    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("async function executeNativeTurn(") == 1
    assert "executeNativeTurn =" not in owner
    assert "= executeNativeTurn;" not in owner
    assert "_cwaNativeTurnBaseExecute" not in owner
    assert "_cwaBaseExecuteNativeTurn(message)" in owner


def test_root_composition_preserves_historical_outer_to_inner_order() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    markers = (
        '["ordinary-text-identity", _cwaOrdinaryIdentityExecuteNativeTurn]',
        '["rich-input", _executeNativeTurnWithRichInputLifecycle]',
        '["browser-authority-lease", _executeNativeTurnWithBrowserAuthorityLease]',
        '["temporary", _executeNativeTurnWithTemporaryLifecycle]',
        '["response", _executeNativeTurnWithResponseLifecycle]',
        '["selection", _executeNativeTurnWithSelectionLifecycle]',
        '["stale-ui-recovery", _executeNativeTurnWithStaleUiRecovery]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_single_owner_preserves_nested_order_and_message_handoff() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const events = [];

async function _cwaBaseExecuteNativeTurn(message) {{
  events.push("base");
  return {{ chain: message.chain }};
}}

function layer(name) {{
  return async (message, next) => {{
    events.push("enter:" + name);
    const result = await next({{
      ...message,
      chain: [...(message.chain || []), name]
    }});
    events.push("exit:" + name);
    return result;
  }};
}}

const _cwaOrdinaryIdentityExecuteNativeTurn = layer("ordinary");
const _executeNativeTurnWithRichInputLifecycle = layer("rich");
const _executeNativeTurnWithBrowserAuthorityLease = layer("authority");
const _executeNativeTurnWithTemporaryLifecycle = layer("temporary");
const _executeNativeTurnWithResponseLifecycle = layer("response");
const _executeNativeTurnWithSelectionLifecycle = layer("selection");
const _executeNativeTurnWithStaleUiRecovery = layer("recovery");

{owner}

(async () => {{
  const result = await executeNativeTurn({{ chain: [] }});
  console.log(JSON.stringify({{ events, chain: result.chain }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:ordinary",
        "enter:rich",
        "enter:authority",
        "enter:temporary",
        "enter:response",
        "enter:selection",
        "enter:recovery",
        "base",
        "exit:recovery",
        "exit:selection",
        "exit:response",
        "exit:temporary",
        "exit:authority",
        "exit:rich",
        "exit:ordinary",
    ]
    assert result["chain"] == [
        "ordinary",
        "rich",
        "authority",
        "temporary",
        "response",
        "selection",
        "recovery",
    ]
