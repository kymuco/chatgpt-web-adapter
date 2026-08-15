from __future__ import annotations

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_manual_ground_truth_probe import (
    probe_manual_temporary_ground_truth,
)


class _FakeProvider:
    connect_timeout = 0.5

    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def _rpc(self, payload, *, timeout):
        self.request = dict(payload)
        self.timeout = timeout
        response = dict(self.response)
        response.setdefault("protocol", 1)
        response.setdefault("type", "turn_result")
        response.setdefault("request_id", payload["request_id"])
        return response


def _success_response(**overrides):
    payload = {
        "ok": True,
        "probeContext": "manual_temporary_ground_truth_turn",
        "manualTemporaryConfirmed": True,
        "sourceTabId": 42,
        "sourceTabLeftOpen": True,
        "conversationWriteCount": 1,
        "conversationId": "temporary-conversation-1",
        "turnExchangeId": "turn-1",
        "responseStatus": 200,
        "responseMimeType": "text/event-stream",
        "finalUrlKind": "conversation",
        "urlConversationIdPresent": True,
        "submitStrategy": "send_button_click",
        "submitAckMs": 123,
        "completionReadyWaitMs": 456,
        "uiModeMarkerObservedAfterTurn": True,
        "postTurnUiModeSignals": ["semantic:document-title-temporary"],
        "elapsedMs": 1200,
    }
    payload.update(overrides)
    return payload


def test_manual_ground_truth_requires_explicit_human_confirmation() -> None:
    with pytest.raises(ValueError, match="manual_temporary_confirmed"):
        probe_manual_temporary_ground_truth(
            provider=_FakeProvider(_success_response()),
            manual_temporary_confirmed=False,
        )


def test_manual_ground_truth_serializes_isolated_flags_and_parses_result() -> None:
    provider = _FakeProvider(_success_response())

    result = probe_manual_temporary_ground_truth(
        "Reply exactly: smoke",
        provider=provider,
        manual_temporary_confirmed=True,
        timeout=12,
    )

    assert provider.request["type"] == "turn"
    assert provider.request["conversationId"] is None
    assert provider.request["probeTemporaryMode"] is False
    assert provider.request["characterizeTemporaryTurn"] is False
    assert provider.request["probeTemporaryHistoryPresence"] is False
    assert provider.request["characterizeManualTemporaryGroundTruth"] is True
    assert provider.request["manualTemporaryConfirmed"] is True
    assert provider.request["timeoutMs"] == 12_000
    assert provider.timeout == pytest.approx(12.5)

    assert result.probe_context == "manual_temporary_ground_truth_turn"
    assert result.manual_temporary_confirmed is True
    assert result.source_tab_id == 42
    assert result.source_tab_left_open is True
    assert result.conversation_write_count == 1
    assert result.conversation_id == "temporary-conversation-1"
    assert result.turn_exchange_id == "turn-1"
    assert result.response_status == 200
    assert result.response_mime_type == "text/event-stream"
    assert result.ui_mode_marker_observed_after_turn is True
    assert result.post_turn_ui_mode_signals == ("semantic:document-title-temporary",)


def test_manual_ground_truth_does_not_require_or_construct_canonical_runtime(monkeypatch) -> None:
    provider = _FakeProvider(_success_response())

    # This module deliberately has no canonical runtime dependency. If that
    # boundary regresses, this import-level assertion will fail visibly.
    import chatgpt_web_adapter.temporary_chat_manual_ground_truth_probe as module

    assert not hasattr(module, "assemble_product_runtime")
    result = probe_manual_temporary_ground_truth(
        provider=provider,
        manual_temporary_confirmed=True,
        timeout=5,
    )
    assert result.source_tab_left_open is True


def test_manual_ground_truth_fails_closed_on_bridge_error() -> None:
    provider = _FakeProvider(
        {"ok": False, "error": "TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_REQUIRES_FRESH_NEW_CHAT"}
    )

    with pytest.raises(RequestError, match="REQUIRES_FRESH_NEW_CHAT"):
        probe_manual_temporary_ground_truth(
            provider=provider,
            manual_temporary_confirmed=True,
            timeout=5,
        )
