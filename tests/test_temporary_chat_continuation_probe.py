from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_continuation_probe import (
    DEFAULT_CONTINUATION_TEXT,
    probe_temporary_controlled_continuation,
)


class _FakeProvider:
    connect_timeout = 0.1

    def __init__(self, route_responses: list[dict], write_result: SimpleNamespace):
        self.route_responses = list(route_responses)
        self.write_result = write_result
        self.rpc_calls: list[tuple[dict, float]] = []
        self.send_calls: list[tuple[str, object, float | None]] = []

    def _rpc(self, payload: dict, *, timeout: float) -> dict:
        self.rpc_calls.append((payload, timeout))
        response = dict(self.route_responses.pop(0))
        response.setdefault("protocol", 1)
        response.setdefault("request_id", payload["request_id"])
        return response

    def send_text(self, text: str, *, conversation=None, timeout=None):
        self.send_calls.append((text, conversation, timeout))
        return self.write_result


def _route_response(turn_count: int, **overrides) -> dict:
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
        "maxVisibleTurnCount": turn_count,
        "finalVisibleTurnCount": turn_count,
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


def _write_result(**overrides) -> SimpleNamespace:
    payload = {
        "conversation_id": "ephemeral-1",
        "turn_exchange_id": "turn-2",
        "response_status": 200,
        "response_mime_type": "text/event-stream",
        "final_url": "https://chatgpt.com/c/ephemeral-1",
        "tab_was_active": False,
        "tab_active_after": False,
        "tab_activated_during_turn": False,
        "foreground_activation_observed": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_continuation_requires_source_closed_confirmation() -> None:
    with pytest.raises(ValueError, match="source_temporary_tab_confirmed_closed"):
        probe_temporary_controlled_continuation(
            "ephemeral-1",
            source_temporary_tab_confirmed_closed=False,
            acknowledge_single_continuation_write=True,
            provider=_FakeProvider([], _write_result()),
        )


def test_continuation_requires_explicit_single_write_acknowledgement() -> None:
    with pytest.raises(ValueError, match="acknowledge_single_continuation_write"):
        probe_temporary_controlled_continuation(
            "ephemeral-1",
            source_temporary_tab_confirmed_closed=True,
            acknowledge_single_continuation_write=False,
            provider=_FakeProvider([], _write_result()),
        )


def test_continuation_rejects_product_url_as_backend_id() -> None:
    with pytest.raises(ValueError, match="raw backend id"):
        probe_temporary_controlled_continuation(
            "https://chatgpt.com/c/ephemeral-1",
            source_temporary_tab_confirmed_closed=True,
            acknowledge_single_continuation_write=True,
            provider=_FakeProvider([], _write_result()),
        )


def test_continuation_composes_pre_write_post_without_canonical_or_history() -> None:
    provider = _FakeProvider(
        [_route_response(2), _route_response(4)],
        _write_result(),
    )

    result = probe_temporary_controlled_continuation(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        acknowledge_single_continuation_write=True,
        provider=provider,
        route_probe_timeout=45,
        write_timeout=180,
    )

    assert len(provider.rpc_calls) == 2
    assert all(call[0]["probeTemporaryRouteReopen"] is True for call in provider.rpc_calls)
    assert len(provider.send_calls) == 1
    text, conversation, timeout = provider.send_calls[0]
    assert text == DEFAULT_CONTINUATION_TEXT
    assert conversation == "ephemeral-1"
    assert timeout == 180

    assert result.pre_stable_recovered is True
    assert result.pre_final_visible_turn_count == 2
    assert result.write_invocation_count == 1
    assert result.provider_result_conversation_id_matches_target is True
    assert result.provider_result_conversation_id_provenance == "worker_resolved_or_requested_fallback"
    assert result.write_response_status == 200
    assert result.write_final_url_kind == "exact_target"
    assert result.write_final_url_conversation_id_matches_target is True
    assert result.post_stable_recovered is True
    assert result.post_final_visible_turn_count == 4
    assert result.persisted_turn_count_growth == 2
    assert result.target_route_turn_growth_proven is True
    assert result.continuation_evidence_status == "CONTINUATION_PROVEN"
    assert result.canonical_http_read_performed is False
    assert result.conversation_attach_performed is False
    assert result.history_probe_performed is False
    assert result.message_text_exported is False


def test_continuation_fails_closed_before_write_when_pre_recovery_is_not_stable() -> None:
    provider = _FakeProvider(
        [
            _route_response(
                0,
                stableRecovered=False,
                recoveryEvidenceStatus="REDIRECTED_TO_ROOT",
                finalUrlKind="root",
                finalUrlConversationIdMatchesTarget=False,
            )
        ],
        _write_result(),
    )

    with pytest.raises(RequestError, match="PRE_ROUTE_NOT_STABLY_RECOVERED"):
        probe_temporary_controlled_continuation(
            "ephemeral-1",
            source_temporary_tab_confirmed_closed=True,
            acknowledge_single_continuation_write=True,
            provider=provider,
        )

    assert provider.send_calls == []


def test_continuation_does_not_promote_when_post_route_growth_is_missing() -> None:
    provider = _FakeProvider(
        [_route_response(2), _route_response(2)],
        _write_result(),
    )

    result = probe_temporary_controlled_continuation(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        acknowledge_single_continuation_write=True,
        provider=provider,
    )

    assert result.persisted_turn_count_growth == 0
    assert result.target_route_turn_growth_proven is False
    assert result.continuation_evidence_status == "CONTINUATION_NOT_PROVEN"


def test_continuation_does_not_promote_when_write_final_route_changes() -> None:
    provider = _FakeProvider(
        [_route_response(2), _route_response(4)],
        _write_result(final_url="https://chatgpt.com/"),
    )

    result = probe_temporary_controlled_continuation(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        acknowledge_single_continuation_write=True,
        provider=provider,
    )

    assert result.write_final_url_kind == "root"
    assert result.write_final_url_conversation_id_matches_target is False
    assert result.target_route_turn_growth_proven is False
    assert result.continuation_evidence_status == "CONTINUATION_NOT_PROVEN"
