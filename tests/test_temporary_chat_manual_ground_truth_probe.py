from __future__ import annotations

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_manual_ground_truth_probe import (
    DEFAULT_EXPECTED_ASSISTANT_TEXT,
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
        "sameSourceTab": True,
        "initialUrlKind": "new_chat_root",
        "initialUrlTemporaryMarker": True,
        "initialUrlTemporaryQueryTrue": True,
        "initialUrlConversationIdPresent": False,
        "conversationWriteCount": 1,
        "conversationId": "temporary-conversation-1",
        "turnExchangeId": "turn-1",
        "responseStatus": 200,
        "responseMimeType": "text/event-stream",
        "finalUrlKind": "new_chat_root",
        "finalUrlTemporaryMarker": True,
        "finalUrlTemporaryQueryTrue": True,
        "urlConversationIdPresent": False,
        "submitStrategy": "send_button_click",
        "submitAckMs": 123,
        "completionReadyWaitMs": 456,
        "conversationTurnCountBefore": 0,
        "conversationTurnCountAfter": 2,
        "turnCountGrowth": 2,
        "matchingUserMessageCount": 1,
        "assistantMessageCandidateCount": 1,
        "matchingExpectedAssistantMessageCount": 1,
        "userMessageVisibleAfterTurn": True,
        "assistantMessageVisibleAfterTurn": True,
        "assistantExactExpectedReplyVisible": True,
        "visibleTurnGroundTruthProven": True,
        "turnSurfaceEvidenceStatus": "PROVEN",
        "turnSurfaceSelectorKind": "conversation-testid",
        "uiModeMarkerObservedAfterTurn": True,
        "postTurnUiModeSignals": ["semantic:url-temporary"],
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
        expected_assistant_text="smoke",
        timeout=12,
    )

    assert provider.request["type"] == "turn"
    assert provider.request["conversationId"] is None
    assert provider.request["expectedAssistantText"] == "smoke"
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
    assert result.same_source_tab is True
    assert result.initial_url_kind == "new_chat_root"
    assert result.initial_url_temporary_marker is True
    assert result.initial_url_temporary_query_true is True
    assert result.initial_url_conversation_id_present is False
    assert result.conversation_write_count == 1
    assert result.conversation_id == "temporary-conversation-1"
    assert result.turn_exchange_id == "turn-1"
    assert result.response_status == 200
    assert result.response_mime_type == "text/event-stream"
    assert result.final_url_kind == "new_chat_root"
    assert result.final_url_temporary_marker is True
    assert result.final_url_temporary_query_true is True
    assert result.url_conversation_id_present is False
    assert result.conversation_turn_count_before == 0
    assert result.conversation_turn_count_after == 2
    assert result.turn_count_growth == 2
    assert result.user_message_visible_after_turn is True
    assert result.assistant_message_visible_after_turn is True
    assert result.assistant_exact_expected_reply_visible is True
    assert result.visible_turn_ground_truth_proven is True
    assert result.turn_surface_evidence_status == "PROVEN"
    assert result.turn_surface_selector_kind == "conversation-testid"
    assert result.ui_mode_marker_observed_after_turn is True
    assert result.post_turn_ui_mode_signals == ("semantic:url-temporary",)


def test_manual_ground_truth_defaults_expected_assistant_text_for_smoke() -> None:
    provider = _FakeProvider(_success_response())
    probe_manual_temporary_ground_truth(
        provider=provider,
        manual_temporary_confirmed=True,
    )
    assert provider.request["expectedAssistantText"] == DEFAULT_EXPECTED_ASSISTANT_TEXT


def test_manual_ground_truth_preserves_network_success_without_visible_turn_as_inconclusive() -> None:
    provider = _FakeProvider(
        _success_response(
            conversationTurnCountAfter=0,
            turnCountGrowth=0,
            matchingUserMessageCount=0,
            assistantMessageCandidateCount=0,
            matchingExpectedAssistantMessageCount=0,
            userMessageVisibleAfterTurn=False,
            assistantMessageVisibleAfterTurn=False,
            assistantExactExpectedReplyVisible=False,
            visibleTurnGroundTruthProven=False,
            turnSurfaceEvidenceStatus="INCONCLUSIVE",
        )
    )

    result = probe_manual_temporary_ground_truth(
        provider=provider,
        manual_temporary_confirmed=True,
    )

    assert result.response_status == 200
    assert result.conversation_id == "temporary-conversation-1"
    assert result.visible_turn_ground_truth_proven is False
    assert result.turn_surface_evidence_status == "INCONCLUSIVE"


def test_manual_ground_truth_does_not_require_or_construct_canonical_runtime(monkeypatch) -> None:
    provider = _FakeProvider(_success_response())

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
        {"ok": False, "error": "TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_REQUIRES_TEMPORARY_URL"}
    )

    with pytest.raises(RequestError, match="REQUIRES_TEMPORARY_URL"):
        probe_manual_temporary_ground_truth(
            provider=provider,
            manual_temporary_confirmed=True,
            timeout=5,
        )
