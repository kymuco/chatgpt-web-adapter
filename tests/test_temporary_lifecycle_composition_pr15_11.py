from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

LAYERS = (
    "service_worker_temporary_startup_readiness_pr8_13_2.js",
    "service_worker_temporary_product.js",
)
OWNER = "service_worker_temporary_lifecycle.js"


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


def test_temporary_layers_no_longer_own_native_turn() -> None:
    for name in LAYERS:
        source = _source(name)
        assert "executeNativeTurn =" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_temporary_lower_level_authority_hooks_remain_local() -> None:
    production = _source("service_worker_temporary_product.js")
    fresh = production
    readiness = _source("service_worker_temporary_startup_readiness_pr8_13_2.js")

    assert "Fetch.requestPaused" in production
    assert "_pr813EndTemporaryLifecycle" in production
    assert "_pr813ExecuteTemporaryTurn(message, next)" in production
    assert "PR813_FRESH_TEMPORARY_IDENTITY_SENTINEL" in fresh
    assert "function _pr813ConversationId(value)" in fresh
    assert "_pr8132WaitForFreshTemporaryReadiness" in readiness
    assert "_pr8132PriorSubmitOfficialPageTurn" in readiness


def test_temporary_lifecycle_is_pure_layer_at_historical_outer_boundary() -> None:
    assembly = _source("service_worker_observability.js")
    owner = _source(OWNER)

    readiness = (
        'importScripts("service_worker_temporary_startup_readiness_pr8_13_2.js");'
    )
    owner_import = f'importScripts("{OWNER}");'
    product_surface = 'importScripts("service_worker_product_surface_pr11_0.js");'

    assert (
        readiness in assembly
        and owner_import in assembly
        and product_surface in assembly
    )
    assert (
        assembly.index(readiness)
        < assembly.index(owner_import)
        < assembly.index(product_surface)
    )
    assert "executeNativeTurn =" not in owner
    assert "_cwaTemporaryLifecyclePriorExecuteNativeTurn" not in owner
    assert (
        "async function _executeNativeTurnWithTemporaryLifecycle(message, next)"
        in owner
    )


def test_temporary_lifecycle_preserves_historical_outer_to_inner_order() -> None:
    owner = _source(OWNER)
    markers = (
        '["startup-readiness", _pr8132ExecuteNativeTurnWithStartupDiagnostics]',
        '["fresh-identity-flush", _pr813ExecuteNativeTurnWithFreshIdentityFlush]',
        '["temporary-production", _pr813ExecuteNativeTurn]',
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_explicit_temporary_composition_preserves_nested_order_and_handoff() -> None:
    owner = _source(OWNER)
    script = f"""
const events = [];

const priorExecuteNativeTurn = async (message) => {{
  events.push("prior");
  return {{ chain: message.chain }};
}};

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

const _pr8132ExecuteNativeTurnWithStartupDiagnostics = layer("startup");
const _pr813ExecuteNativeTurnWithFreshIdentityFlush = layer("fresh");
const _pr813ExecuteNativeTurn = layer("production");

{owner}

(async () => {{
  const result = await _executeNativeTurnWithTemporaryLifecycle(
    {{ chain: [] }},
    priorExecuteNativeTurn
  );
  console.log(JSON.stringify({{ events, chain: result.chain }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == [
        "enter:startup",
        "enter:fresh",
        "enter:production",
        "prior",
        "exit:production",
        "exit:fresh",
        "exit:startup",
    ]
    assert result["chain"] == ["startup", "fresh", "production"]
