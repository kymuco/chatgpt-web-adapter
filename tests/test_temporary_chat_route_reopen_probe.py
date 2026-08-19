from __future__ import annotations

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_route_reopen_probe import (
    probe_temporary_product_route_reopen,
)


class _FakeProvider:
    connect_timeout = 0.1

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[tuple[dict, float]] = []

    def _rpc(self, payload: dict, *, timeout: float) -> dict:
        self.calls.append((payload, timeout))
        response = dict(self.response)
        response.setdefault("protocol", 1)
        response.setdefault("request_id", payload["request_id"])
        return response


def _base_response(**overrides) -> dict:
    payload = {
        "ok": True,
        "probeContext": "temporary_product_route_reopen_after_source_close",
        "conversationId": "ephemeral-1",
        "sourceTemporaryTabConfirmedClosed": True,
        "productRouteOpenAttempted": True,
        "canonicalHttpReadPerformed": False,
        "conversationAttachPerformed": False,
        "writePerformed": False,
        "conversationWriteCount": 0,
        "observationWindowMs": 15000,
        "targetRouteObserved": True,
        "targetRouteFirstSeenMs": 20,
        "targetRouteLastSeenMs": 14900,
        "targetRouteSampleCount": 50,
        "rootRouteObserved": False,
        "rootRouteSampleCount": 0,
        "otherRouteSampleCount": 0,
        "redirectAwayFromTargetObserved": False,
        "finalUrlKind": "exact_target",
        "finalUrlConversationIdMatchesTarget": True,
        "visibleTurnSurfaceObserved": True,
        "maxVisibleTurnCount": 2,
        "finalVisibleTurnCount": 2,
        "turnSurfaceSelectorKind": "conversation-testid",
        "recoveredSampleCount": 40,
        "firstRecoveredMs": 500,
        "lastRecoveredMs": 14900,
        "stableRecovered": True,
        "transientRecovered": False,
        "recoveryEvidenceStatus": "STABLE_RECOVERED",
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "debuggerAttachedAfter": False,
        "probeTabClosed": True,
    }
    payload.update(overrides)
    return payload


def test_route_reopen_requires_source_closed_confirmation() -> None:
    with pytest.raises(ValueError, match="source_temporary_tab_confirmed_closed"):
        probe_temporary_product_route_reopen(
            "ephemeral-1",
            source_temporary_tab_confirmed_closed=False,
            provider=_FakeProvider(_base_response()),
        )


def test_route_reopen_rejects_product_url_as_backend_id() -> None:
    with pytest.raises(ValueError, match="raw backend id"):
        probe_temporary_product_route_reopen(
            "https://chatgpt.com/c/ephemeral-1",
            source_temporary_tab_confirmed_closed=True,
            provider=_FakeProvider(_base_response()),
        )


def test_route_reopen_sends_read_only_explicit_probe_and_parses_stable_recovery() -> None:
    provider = _FakeProvider(_base_response())
    result = probe_temporary_product_route_reopen(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        provider=provider,
        timeout=45,
    )

    assert len(provider.calls) == 1
    request, rpc_timeout = provider.calls[0]
    assert request["probeTemporaryRouteReopen"] is True
    assert request["sourceTemporaryTabConfirmedClosed"] is True
    assert request["conversationId"] == "ephemeral-1"
    assert request["text"] is None
    assert request["canonicalCompleted"] is False
    assert rpc_timeout > 45

    assert result.product_route_open_attempted is True
    assert result.canonical_http_read_performed is False
    assert result.conversation_attach_performed is False
    assert result.write_performed is False
    assert result.conversation_write_count == 0
    assert result.target_route_observed is True
    assert result.max_visible_turn_count == 2
    assert result.stable_recovered is True
    assert result.transient_recovered is False
    assert result.recovery_evidence_status == "STABLE_RECOVERED"
    assert result.probe_tab_closed is True


def test_route_reopen_preserves_transient_recovery_distinct_from_stable() -> None:
    provider = _FakeProvider(
        _base_response(
            rootRouteObserved=True,
            rootRouteSampleCount=30,
            redirectAwayFromTargetObserved=True,
            finalUrlKind="root",
            finalUrlConversationIdMatchesTarget=False,
            finalVisibleTurnCount=0,
            recoveredSampleCount=2,
            stableRecovered=False,
            transientRecovered=True,
            recoveryEvidenceStatus="TRANSIENT_RECOVERED",
        )
    )

    result = probe_temporary_product_route_reopen(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        provider=provider,
    )

    assert result.redirect_away_from_target_observed is True
    assert result.final_url_kind == "root"
    assert result.stable_recovered is False
    assert result.transient_recovered is True
    assert result.recovery_evidence_status == "TRANSIENT_RECOVERED"


def test_route_reopen_rejects_identity_mismatch() -> None:
    provider = _FakeProvider(_base_response(conversationId="different-id"))
    with pytest.raises(RequestError, match="IDENTITY_MISMATCH"):
        probe_temporary_product_route_reopen(
            "ephemeral-1",
            source_temporary_tab_confirmed_closed=True,
            provider=provider,
        )
