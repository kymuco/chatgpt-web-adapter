from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_connector_support_pr10_0.js"
)
PROBE = ROOT / "tools" / "pr10_0_required_action_surface_probe.py"


def test_required_action_surface_probe_is_read_only_dom_characterization() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    assert "characterizeRequiredActionSurface" in source
    assert "Runtime.evaluate" in source
    assert "storedRuntimeTabId()" in source
    assert "chrome.debugger.attach" in source
    assert "chrome.debugger.detach" in source
    assert "chrome.debugger.getTargets" in source

    assert "Input.dispatch" not in source
    assert ".click(" not in source
    assert "chrome.tabs.create" not in source
    assert "chrome.tabs.update" not in source
    assert "chrome.tabs.remove" not in source


def test_required_action_surface_probe_never_exports_raw_dom_text() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    assert "rawDomExported: false" in source
    assert "clickPerformed: false" in source
    assert "writePerformed: false" in source
    assert "approvalAuthorityGranted: false" in source
    assert "connectorName: provider" in source
    assert "actionType: 'connector_authorization_required'" in source

    # DOM strings are used only inside the page-side classifier; the outer worker
    # result re-materializes a fixed whitelist rather than forwarding the value.
    outer_result = source[source.index("snapshot = {") :]
    assert "innerText" not in outer_result
    assert "textContent" not in outer_result


def test_required_action_surface_requires_connect_and_dismiss_affordance() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    assert "isConnect(label(connectControl))" in source
    assert "isDismiss(label(element))" in source
    assert "if (!dismissPresent) continue;" in source
    assert "['gmail', ['gmail']]" in source
    assert "stableActionIdPresent: false" in source


def test_required_action_surface_rpc_rejects_write_bearing_fields() -> None:
    source = SUPPORT.read_text(encoding="utf-8")

    assert "_pr100SupportRejectWriteBearingMessage" in source
    assert "message?.text != null" in source
    assert "message?.conversationId != null" in source
    assert "message?.attachmentPaths != null" in source
    assert "message?.browserAuthorityLeaseId != null" in source
    assert "PR10_0_REQUIRED_ACTION_SURFACE_PROBE_MUST_BE_NO_WRITE" in source


def test_required_action_surface_cli_has_no_product_write_path() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert 'SCHEMA = "CWA_PR10_0_REQUIRED_ACTION_SURFACE_PROBE_V2"' in source
    assert '"product_write_budget": 0' in source
    assert '"write_attempted": False' in source
    assert '"click_attempted": False' in source
    assert "characterizeRequiredActionSurface" in source
    assert "ChatGPTWebClient" not in source
    assert "assemble_product_runtime" not in source
    assert "send_text" not in source
    assert "send_text_observed" not in source


def test_required_action_surface_cli_materializes_only_uncorrelated_point_evidence() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert "PRODUCT_REQUIRED_ACTION_SURFACE_OBSERVED" in source
    assert "ProductConnectorLifecycleCollector" in source
    assert '"point_observation_materialized": point_observation_materialized' in source
    assert '"lifecycle_correlation_claimed": False' in source
    assert '"action_id" not in typed_observation' in source
    assert "stable_action_id_present" in source
