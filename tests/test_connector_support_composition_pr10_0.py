from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
ENTRYPOINT = EXT / "service_worker_temporary_chat_route_reopen_probe.js"
SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"
MANIFEST = EXT / "manifest.json"


def test_manifest_entrypoint_stays_historically_stable() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["version"] == "0.1.13"
    assert (
        manifest["background"]["service_worker"]
        == "service_worker_temporary_chat_route_reopen_probe.js"
    )


def test_connector_support_remains_outermost_turn_wrapper() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    schema7 = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    support = 'importScripts("service_worker_connector_support_pr10_0.js");'

    assert schema7 in source and support in source
    assert source.index(schema7) < source.index(support)
    assert source.rstrip().endswith(support)

    support_source = SUPPORT.read_text(encoding="utf-8")
    liveness = 'importScripts("service_worker_ui_liveness.js");'
    assert support_source.rstrip().endswith(liveness)
    assert support_source.index("executeNativeTurn = async function _pr100") < (
        support_source.index(liveness)
    )


def test_outer_support_probes_are_direct_no_write_and_other_turns_delegate() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    connector_flag = 'message?.characterizeConnectorObservationSupport === true'
    surface_flag = 'message?.characterizeRequiredActionSurface === true'
    delegation = "return _pr100SupportPriorExecuteNativeTurn(message);"
    contract = "connectorObservationSupported: true"

    assert "const _pr100SupportPriorExecuteNativeTurn = executeNativeTurn;" in source
    assert connector_flag in source
    assert surface_flag in source
    assert contract in source
    assert source.count(delegation) == 1
    assert source.rfind(delegation) > source.index(surface_flag)
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
