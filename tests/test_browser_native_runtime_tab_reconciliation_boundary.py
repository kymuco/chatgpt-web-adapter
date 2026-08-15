from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_manifest_routes_through_runtime_tab_reconciliation_wrapper() -> None:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.5"
    assert manifest["background"]["service_worker"] == "service_worker_runtime_tab_reconciliation.js"


def test_reconciliation_wrapper_extends_observability_without_reimplementing_transport() -> None:
    source = (EXT / "service_worker_runtime_tab_reconciliation.js").read_text(encoding="utf-8")
    assert 'importScripts("service_worker_observability.js")' in source
    assert "storedRuntimeTabId = async function" in source
    assert "chrome.tabs.get" in source
    assert "chrome.storage.local.remove(RUNTIME_TAB_KEY)" in source
    assert 'type: "runtime_state"' in source
    assert "runtimeTabId: null" in source
    assert "chrome.tabs.onUpdated" in source
    assert "chrome.tabs.onReplaced" in source
    assert "storeRuntimeTabId(addedTabId)" in source
    assert "_pr824a3PublishValidatedRuntimeState" in source

    for forbidden in (
        "Input.dispatchKeyEvent",
        "Input.dispatchMouseEvent",
        "Network.getResponseBody",
        "submitOfficialPageTurn",
        "executeOfficialPageTurn",
        "chat-requirements",
        "turnstile",
        "proof_token",
        "document.cookie",
    ):
        assert forbidden not in source


def test_reconciliation_does_not_claim_hidden_or_browserless_write() -> None:
    source = (EXT / "service_worker_runtime_tab_reconciliation.js").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "chrome.tabs.create" not in source
    assert "chrome.windows" not in source
    assert "hidden tab" not in lowered
    assert "browserless write" not in lowered
