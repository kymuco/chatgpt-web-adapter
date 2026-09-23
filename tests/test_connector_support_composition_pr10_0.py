from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BOOTSTRAP = EXT / "service_worker_temporary_chat_route_reopen_probe.js"
WRITE = EXT / "service_worker_runtime_write.js"
OBSERVATION = EXT / "service_worker_runtime_observation.js"
SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"
LIFECYCLE = EXT / "service_worker_product_observation.js"
MANIFEST = EXT / "manifest.json"
WORKER = EXT / "service_worker.js"


def test_manifest_entrypoint_stays_historically_stable() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["version"] == "0.1.13"
    assert (
        manifest["background"]["service_worker"]
        == "service_worker_temporary_chat_route_reopen_probe.js"
    )
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'importScripts("service_worker_runtime.js");' in bootstrap


def test_connector_support_registers_explicit_diagnostic_handler() -> None:
    write = WRITE.read_text(encoding="utf-8")
    observation = OBSERVATION.read_text(encoding="utf-8")
    support_source = SUPPORT.read_text(encoding="utf-8")
    lifecycle_source = LIFECYCLE.read_text(encoding="utf-8")
    worker_source = WORKER.read_text(encoding="utf-8")

    schema7 = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    support = 'importScripts("service_worker_connector_support_pr10_0.js");'
    liveness = 'importScripts("service_worker_ui_liveness.js");'

    assert schema7 in write
    assert observation.index(support) < observation.index(liveness)
    assert "executeNativeTurn = async function" not in support_source
    assert "executeNativeTurn = async function" not in lifecycle_source
    assert "_pr100SupportPriorExecuteNativeTurn" not in support_source
    assert "_pr100PriorExecuteNativeTurn" not in lifecycle_source
    assert "registerNativeTurnDiagnosticHandler(" in support_source
    assert '"connector-support"' in support_source
    assert "registerNativeTurnDiagnosticHandler" in worker_source
    assert "dispatchNativeTurn(message)" in worker_source


def test_connector_support_diagnostics_are_no_write_and_do_not_wrap_runtime() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    connector_flag = "message?.characterizeConnectorObservationSupport === true"
    surface_flag = "message?.characterizeRequiredActionSurface === true"
    contract = "connectorObservationSupported: true"

    assert connector_flag in source
    assert surface_flag in source
    assert contract in source
    assert "_pr100SupportDiagnosticMatches" in source
    assert "_pr100HandleSupportDiagnostic" in source
    assert "executeNativeTurn" not in source
    assert "message?.text != null" in source
    assert "message?.conversationId != null" in source
    assert "message?.attachmentPaths != null" in source
    assert "message?.browserAuthorityLeaseId != null" in source
    assert "PR10_0_CONNECTOR_SUPPORT_PROBE_MUST_BE_NO_WRITE" in source
    assert "PR10_0_REQUIRED_ACTION_SURFACE_PROBE_MUST_BE_NO_WRITE" in source
    assert "writePerformed: false" in source
    assert "automaticWriteRetry: false" in source
    assert "fallbackTransport: null" in source

    for forbidden in (
        "executeOfficialPageTurn",
        "submitOfficialPageTurn",
        "DOM.setFileInputFiles",
        "Input.dispatchKeyEvent",
        "Input.insertText",
        "approve_pending_action",
        "send_and_auto_approve",
        "wait_and_approve",
    ):
        assert forbidden not in source
