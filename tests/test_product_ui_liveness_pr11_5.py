from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.product_transport import (
    BROWSERLESS_REQUEST_PRODUCT_TRANSPORT,
    BROWSER_OWNED_PRODUCT_TRANSPORT,
)


class _Provider:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.requests: list[dict] = []

    def _rpc(self, payload: dict, *, timeout: float, on_event=None) -> dict:
        self.requests.append({"payload": dict(payload), "timeout": timeout})
        response = dict(self.response)
        response["request_id"] = payload["request_id"]
        return response


def _runtime(*, transport: str, provider=None):
    runtime = object.__new__(adapter.ChatGPTProductRuntime)
    runtime.transport = transport
    runtime.write_transport = SimpleNamespace(
        provider=provider,
        governance=lambda: {},
    )
    return runtime


def _response(**updates) -> dict:
    payload = {
        "protocol": 1,
        "type": "ui_liveness_result",
        "ok": True,
        "state": "READY_FOR_INPUT",
        "reasonCode": "COMPOSER_READY",
        "observedAtMs": 1_700_000_000_000,
        "bridgeAvailable": True,
        "extensionConnected": True,
        "runtimeTabPresent": True,
        "composerVisible": True,
        "generationControlVisible": False,
        "composerBusy": False,
        "rawDomExported": False,
        "navigationPerformed": False,
        "runtimeTabCreated": False,
        "writePerformed": False,
        "canonicalReadPerformed": False,
        "canonicalFinalityProven": False,
        "grantsWriteAuthority": False,
        "grantsRetryAuthority": False,
    }
    payload.update(updates)
    return payload


def test_liveness_value_types_are_primary_root_exports() -> None:
    primary = adapter.PublicSurfaceTier.PRIMARY_PRODUCTION

    assert adapter.public_surface_tier("BrowserUILivenessState") is primary
    assert adapter.public_surface_tier("BrowserUILivenessObservation") is primary
    assert "BrowserUILivenessState" in adapter.__all__
    assert "BrowserUILivenessObservation" in adapter.__all__


def test_generating_requires_positive_generation_control_evidence() -> None:
    with pytest.raises(ValueError, match="positive generation-control evidence"):
        adapter.BrowserUILivenessObservation(
            transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
            state=adapter.BrowserUILivenessState.GENERATING,
            reason_code="COMPOSER_BUSY",
            observed_at_ms=1,
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=True,
            composer_visible=True,
            generation_control_visible=False,
            composer_busy=True,
        )


def test_browserless_liveness_is_explicitly_unavailable() -> None:
    runtime = _runtime(transport=BROWSERLESS_REQUEST_PRODUCT_TRANSPORT)

    observed = runtime.observe_ui_liveness()

    assert observed.state is adapter.BrowserUILivenessState.UNAVAILABLE
    assert observed.reason_code == "TRANSPORT_OBSERVATION_UNSUPPORTED"
    assert observed.canonical_finality_proven is False
    assert observed.grants_write_authority is False
    assert observed.grants_retry_authority is False


def test_ready_observation_uses_read_only_rpc_without_authority_fields() -> None:
    provider = _Provider(_response())
    runtime = _runtime(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        provider=provider,
    )

    observed = runtime.observe_ui_liveness(timeout=2.0)

    assert observed.state is adapter.BrowserUILivenessState.READY_FOR_INPUT
    assert observed.reason_code == "COMPOSER_READY"
    assert observed.composer_visible is True
    assert observed.generation_control_visible is False
    assert observed.composer_busy is False
    request = provider.requests[0]["payload"]
    assert request["type"] == "ui_liveness"
    assert request["timeoutMs"] == 2000
    for forbidden in (
        "text",
        "conversationId",
        "attachmentPaths",
        "browserAuthorityLeaseId",
    ):
        assert forbidden not in request


def test_generating_observation_requires_stop_control_evidence() -> None:
    provider = _Provider(
        _response(
            state="GENERATING",
            reasonCode="GENERATION_CONTROL_VISIBLE",
            composerVisible=True,
            generationControlVisible=True,
            composerBusy=False,
        )
    )
    runtime = _runtime(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        provider=provider,
    )

    observed = runtime.observe_ui_liveness()

    assert observed.state is adapter.BrowserUILivenessState.GENERATING
    assert observed.generation_control_visible is True
    assert observed.canonical_finality_proven is False


def test_authority_claim_from_observation_is_rejected_to_unknown() -> None:
    provider = _Provider(_response(grantsWriteAuthority=True))
    runtime = _runtime(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        provider=provider,
    )

    observed = runtime.observe_ui_liveness()

    assert observed.state is adapter.BrowserUILivenessState.UNKNOWN
    assert observed.reason_code == "OBSERVATION_CONTRACT_VIOLATION"
    assert observed.grants_write_authority is False
    assert observed.grants_retry_authority is False
    assert observed.canonical_finality_proven is False


def test_governance_declares_liveness_observation_only() -> None:
    runtime = _runtime(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        provider=_Provider(_response()),
    )

    governance = runtime.governance()

    assert governance["browser_ui_liveness_observation_supported"] is True
    assert governance["browser_ui_liveness_is_authority"] is False
    assert governance["browser_ui_liveness_is_canonical_finality"] is False
    assert governance["browser_ui_liveness_grants_write_authority"] is False
    assert governance["browser_ui_liveness_grants_retry_authority"] is False
    assert governance["browser_ui_liveness_raw_dom_exported"] is False
    assert governance["browser_ui_liveness_navigation_performed"] is False
    assert governance["browser_ui_liveness_runtime_tab_created"] is False
    assert governance["browser_ui_liveness_acquires_browser_authority_lane"] is False
