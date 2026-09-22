from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"


def test_native_turn_diagnostic_dispatch_has_single_owner_semantics() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "const nativeTurnDiagnosticHandlers = new Map();" in source
    assert (
        "function registerNativeTurnDiagnosticHandler(name, matches, handle)" in source
    )
    assert "if (nativeTurnDiagnosticHandlers.has(key))" in source
    assert "CHATGPT_NATIVE_TURN_DIAGNOSTIC_HANDLER_DUPLICATE" in source
    assert "if (matching.length > 1)" in source
    assert "CHATGPT_NATIVE_TURN_DIAGNOSTIC_HANDLER_AMBIGUOUS" in source


def test_native_turn_diagnostic_dispatch_falls_through_to_single_runtime_owner() -> (
    None
):
    source = WORKER.read_text(encoding="utf-8")

    assert "async function dispatchNativeTurn(message)" in source
    assert "return matching[0][1].handle(message);" in source
    assert "return _executeNativeTurnWithObservers(message);" in source
    assert "const result = await dispatchNativeTurn(message);" in source


def test_retained_route_and_picker_diagnostics_are_retired() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    assert "service_worker_retained_route_identity_pr8_8.js" not in source
    assert "service_worker_retained_picker_forensics_pr8_8.js" not in source
    assert not (
        EXTENSION / "service_worker_retained_route_identity_pr8_8.js"
    ).exists()
    assert not (
        EXTENSION / "service_worker_retained_picker_forensics_pr8_8.js"
    ).exists()


def test_retired_failure_forensics_are_not_in_production_dispatch() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    for name in (
        "service_worker_instant_failure_forensics_pr8_8.js",
        "service_worker_instant_popup_subtree_forensics_pr8_8.js",
        "service_worker_picker_trigger_identity_pr8_8.js",
        "service_worker_picker_trigger_poll_timeline_pr8_8.js",
        "service_worker_picker_trigger_persistence_pr8_8.js",
    ):
        assert name not in source
        assert not (EXTENSION / name).exists()


def test_native_turn_observer_pipeline_has_one_core_runtime_call() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "const nativeTurnObservers = new Map();" in source
    assert "function registerNativeTurnObserver(name, observer)" in source
    assert "CHATGPT_NATIVE_TURN_OBSERVER_DUPLICATE" in source
    assert "async function _executeNativeTurnWithObservers(message)" in source
    assert source.count("let result = await executeNativeTurn(message);") == 1
    assert "await observer.before(message)" in source
    assert "await observer.afterSuccess(message, result, context)" in source
    assert "await observer.finish(message, context)" in source


def test_provisioning_observability_is_registered_not_wrapped() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    assert "executeNativeTurn = async function" not in source
    assert "_pr824aOriginalExecuteNativeTurn" not in source
    assert 'registerNativeTurnObserver("provisioning-observability"' in source
    assert "runtimeTabPreexisting" in source
    assert "runtimeTabCreatedForTurn" in source
    assert "foregroundActivationObserved" in source
