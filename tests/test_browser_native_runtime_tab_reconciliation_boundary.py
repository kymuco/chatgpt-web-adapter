from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _transitive_worker_imports(worker_name: str) -> list[str]:
    pending = [worker_name]
    seen: set[str] = set()
    ordered: list[str] = []
    while pending:
        name = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
        source = (EXT / name).read_text(encoding="utf-8")
        pending.extend(
            match
            for match in re.findall(r'importScripts\("([^"]+)"\)', source)
            if match not in seen
        )
    return ordered


def test_manifest_routes_through_runtime_tab_reconciliation_wrapper() -> None:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    worker_name = manifest["background"]["service_worker"]
    chain = _transitive_worker_imports(worker_name)

    assert worker_name.endswith(".js")
    assert "service_worker_runtime_tab_reconciliation.js" in chain
    assert "service_worker_observability.js" in chain
    assert chain.index("service_worker_runtime_tab_reconciliation.js") < chain.index(
        "service_worker_observability.js"
    )


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
