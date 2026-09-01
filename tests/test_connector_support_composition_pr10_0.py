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


def test_connector_support_wrapper_loads_after_complete_rich_input_stack() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    schema7 = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    support = 'importScripts("service_worker_connector_support_pr10_0.js");'

    assert schema7 in source and support in source
    assert source.index(schema7) < source.index(support)
    assert source.rstrip().endswith(support)


def test_outer_support_probe_is_direct_no_write_and_non_probe_delegates() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    flag = 'message?.characterizeConnectorObservationSupport !== true'
    delegation = "return _pr100SupportPriorExecuteNativeTurn(message);"
    contract = "connectorObservationSupported: true"

    assert "const _pr100SupportPriorExecuteNativeTurn = executeNativeTurn;" in source
    assert flag in source and delegation in source and contract in source
    assert source.index(flag) < source.index(delegation) < source.index(contract)
    assert "message?.text != null" in source
    assert "message?.conversationId != null" in source
    assert "message?.attachmentPaths != null" in source
    assert "message?.browserAuthorityLeaseId != null" in source
    assert "PR10_0_CONNECTOR_SUPPORT_PROBE_MUST_BE_NO_WRITE" in source
    assert "writePerformed: false" in source
    assert "automaticWriteRetry: false" in source
    assert "fallbackTransport: null" in source

    for forbidden in (
        "executeOfficialPageTurn",
        "submitOfficialPageTurn",
        "DOM.setFileInputFiles",
        "Input.dispatchKeyEvent",
        "Input.insertText",
        "approve",
    ):
        assert forbidden not in source
