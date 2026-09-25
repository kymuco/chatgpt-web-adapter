from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CORE = EXT / "service_worker.js"
PRODUCT = EXT / "service_worker_product_surface_pr11_0.js"
OWNER = EXT / "service_worker_native_bridge_connection.js"
OBSERVABILITY = EXT / "service_worker_observability.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_native_bridge_connection_has_one_public_owner() -> None:
    core = _source(CORE)
    product = _source(PRODUCT)
    owner = _source(OWNER)

    assert "function _cwaBaseConnectNativeBridge(" in core
    assert "function connectNativeBridge(" not in core

    assert "function _cwaConnectNativeBridgeWithProductState(" in product
    assert "connectNativeBridge =" not in product
    assert "_cwaProductPriorConnectNativeBridge" not in product

    assert owner.count("function connectNativeBridge(") == 1
    assert "connectNativeBridge =" not in owner


def test_initial_bootstrap_uses_base_but_future_callbacks_use_public_owner() -> None:
    core = _source(CORE)

    schedule_start = core.index("function scheduleReconnect()")
    connect_start = core.index("function _cwaBaseConnectNativeBridge()", schedule_start)
    schedule_block = core[schedule_start:connect_start]
    assert "connectNativeBridge();" in schedule_block
    assert "_cwaBaseConnectNativeBridge();" not in schedule_block

    tail = core[core.index("chrome.runtime.onInstalled.addListener") :]
    assert "chrome.runtime.onInstalled.addListener(() => connectNativeBridge());" in tail
    assert "chrome.runtime.onStartup.addListener(() => connectNativeBridge());" in tail
    assert tail.rstrip().endswith("_cwaBaseConnectNativeBridge();")


def test_product_wrapper_delegates_to_base_and_attaches_new_port_state() -> None:
    product = _source(PRODUCT)
    start = product.index("function _cwaConnectNativeBridgeWithProductState")
    end = product.index("async function _cwaOnNativeMessageWithProductState", start)
    block = product[start:end]

    assert "const previousPort = nativePort;" in block
    assert "const result = _cwaBaseConnectNativeBridge();" in block
    assert "nativePort !== null && nativePort !== previousPort" in block
    assert "_cwaAttachNativePortProductState(nativePort);" in block
    assert "_cwaUpdateActionState();" in block


def test_owner_is_installed_immediately_after_product_surface() -> None:
    observability = _source(OBSERVABILITY)
    product = 'importScripts("service_worker_product_surface_pr11_0.js");'
    owner = 'importScripts("service_worker_native_bridge_connection.js");'

    assert observability.index(product) < observability.index(owner)
    assert observability.index(owner) == (
        observability.index(product) + len(product) + 1
    )


def test_public_owner_delegates_once() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension ownership fixtures")

    owner = _source(OWNER)
    script = f"""
let calls = 0;
function _cwaConnectNativeBridgeWithProductState() {{
  calls += 1;
  return {{ connected: true }};
}}
{owner}
const result = connectNativeBridge();
console.log(JSON.stringify({{ result, calls }}));
"""
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "result": {"connected": True},
        "calls": 1,
    }
