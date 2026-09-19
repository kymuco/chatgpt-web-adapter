from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker.js"
ROUTE = EXTENSION / "service_worker_retained_route_identity_pr8_8.js"
PICKER = EXTENSION / "service_worker_retained_picker_forensics_pr8_8.js"
FAILURE = EXTENSION / "service_worker_instant_failure_forensics_pr8_8.js"
POPUP = EXTENSION / "service_worker_instant_popup_subtree_forensics_pr8_8.js"
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
    assert "return executeNativeTurn(message);" in source
    assert "const result = await dispatchNativeTurn(message);" in source


def test_retained_route_and_picker_diagnostics_do_not_wrap_native_turn() -> None:
    route = ROUTE.read_text(encoding="utf-8")
    picker = PICKER.read_text(encoding="utf-8")

    assert "executeNativeTurn = async function" not in route
    assert "_pr88RoutePriorExecuteNativeTurn" not in route
    assert "registerNativeTurnDiagnosticHandler(" in route
    assert '"retained-route-identity"' in route

    assert "executeNativeTurn = async function" not in picker
    assert "_pr88ForensicsPriorExecuteNativeTurn" not in picker
    assert "registerNativeTurnDiagnosticHandler(" in picker
    assert '"retained-picker-forensics"' in picker
    assert "characterizeRetainedRouteIdentitySupport" in picker
    assert "characterizeRetainedRouteIdentity" in picker


def test_instant_failure_diagnostics_have_one_explicit_owner() -> None:
    failure = FAILURE.read_text(encoding="utf-8")
    popup = POPUP.read_text(encoding="utf-8")

    assert "executeNativeTurn = async function" not in failure
    assert "_pr88FailurePriorExecuteNativeTurn" not in failure
    assert "async function _pr88FailureSupport(message)" in failure
    assert "_pr88FailurePriorLocateAndFocusComposer" in failure

    assert "executeNativeTurn = async function" not in popup
    assert "_pr88PopupPriorExecuteNativeTurn" not in popup
    assert "registerNativeTurnDiagnosticHandler(" in popup
    assert '"instant-failure-forensics"' in popup
    assert "await _pr88FailureSupport(message)" in popup
    assert "await _pr88FailureRecord(message)" in popup
    assert "_pr88PopupPriorLocateAndFocusComposer" in popup


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
