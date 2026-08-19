from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SRC = ROOT / "src" / "chatgpt_web_adapter"


def test_current_wrapper_routes_through_observability_layer() -> None:
    reconciliation = (EXT / "service_worker_runtime_tab_reconciliation.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_observability.js")' in reconciliation


def test_observability_worker_is_metadata_only() -> None:
    source = (EXT / "service_worker_observability.js").read_text(encoding="utf-8")
    phase_timing = (EXT / "service_worker_phase_timing_pr8_8.js").read_text(
        encoding="utf-8"
    )

    # PR8.8 inserts phase timing between observability and the older recovery
    # layer. Recovery therefore remains in the active import chain without
    # being re-owned or duplicated by observability itself.
    assert 'importScripts("service_worker_phase_timing_pr8_8.js")' in source
    assert 'importScripts("service_worker_recovery.js")' in phase_timing
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
