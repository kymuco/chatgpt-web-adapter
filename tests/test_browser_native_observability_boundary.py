from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SRC = ROOT / "src" / "chatgpt_web_adapter"


def test_manifest_routes_through_observability_wrapper() -> None:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.4"
    assert manifest["background"]["service_worker"] == "service_worker_observability.js"


def test_observability_worker_is_metadata_only() -> None:
    source = (EXT / "service_worker_observability.js").read_text(encoding="utf-8")
    assert 'importScripts("service_worker_recovery.js")' in source
    assert "chrome.tabs.onActivated" in source
    assert "runtimeTabCreatedForTurn" in source
    for forbidden in (
        "Input.dispatchKeyEvent",
        "Input.dispatchMouseEvent",
        "Network.getResponseBody",
        "chat-requirements",
        "turnstile",
        "proof_token",
        "document.cookie",
    ):
        assert forbidden not in source


def test_safe_metadata_is_preserved_through_provider_and_client_event() -> None:
    provider = (SRC / "browser_native_provider.py").read_text(encoding="utf-8")
    client = (SRC / "browser_native_client.py").read_text(encoding="utf-8")
    for name in (
        "runtime_tab_preexisting",
        "runtime_tab_created_for_turn",
        "tab_active_after",
        "tab_activated_during_turn",
        "foreground_activation_observed",
    ):
        assert name in provider
        assert name in client


def test_core_transport_workers_are_not_reimplemented_by_observability_layer() -> None:
    source = (EXT / "service_worker_observability.js").read_text(encoding="utf-8")
    assert "submitOfficialPageTurn" not in source
    assert "locateAndFocusComposer" not in source
    assert "clearComposer" not in source
    assert "executeOfficialPageTurn" not in source
