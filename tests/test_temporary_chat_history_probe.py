from __future__ import annotations

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_history_probe import (
    probe_temporary_chat_history_presence,
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
        "probeContext": "fresh_root_history_settling",
        "conversationId": "conversation-1",
        "historyLinkPresent": True,
        "historyVisibleLinkPresent": True,
        "finalHistoryLinkPresent": True,
        "finalHistoryVisibleLinkPresent": True,
        "stableHistoryPresence": True,
        "transientHistoryPresence": False,
        "historyAbsenceProven": False,
        "historyEvidenceStatus": "STABLE_PRESENT",
        "disappearedAfterSeen": False,
        "firstSeenMs": 1200,
        "lastSeenMs": 9800,
        "seenSampleCount": 18,
        "absentSampleCount": 0,
        "settleWindowMs": 8000,
        "settleCompleted": True,
        "observationWindowMs": 10_000,
        "conversationLinkCount": 12,
        "visibleConversationLinkCount": 8,
        "historySurfaceReady": True,
        "historyReadinessSignals": [
            "document-complete",
            "main-present",
            "conversation-links-enumerated",
        ],
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "probeTabClosed": True,
        "elapsedMs": 10_000,
    }
    payload.update(overrides)
    return payload


def test_history_probe_uses_no_write_exact_identity_request() -> None:
    provider = _FakeProvider(_success_response())
    result = probe_temporary_chat_history_presence(
        "conversation-1",
        provider=provider,
        timeout=12,
    )

    assert provider.request["type"] == "turn"
    assert provider.request["conversationId"] == "conversation-1"
    assert provider.request["text"] is None
    assert provider.request["probeTemporaryMode"] is False
    assert provider.request["characterizeTemporaryTurn"] is False
    assert provider.request["probeTemporaryHistoryPresence"] is True
    assert provider.request["timeoutMs"] == 12_000
    assert provider.timeout == pytest.approx(12.5)

    assert result.probe_context == "fresh_root_history_settling"
    assert result.conversation_id == "conversation-1"
    assert result.history_link_present is True
    assert result.history_visible_link_present is True
    assert result.final_history_link_present is True
    assert result.final_history_visible_link_present is True
    assert result.stable_history_presence is True
    assert result.transient_history_presence is False
    assert result.history_absence_proven is False
    assert result.history_evidence_status == "STABLE_PRESENT"
    assert result.disappeared_after_seen is False
    assert result.first_seen_ms == 1200
    assert result.last_seen_ms == 9800
    assert result.seen_sample_count == 18
    assert result.absent_sample_count == 0
    assert result.settle_window_ms == 8000
    assert result.settle_completed is True
    assert result.observation_window_ms == 10_000
    assert result.conversation_link_count == 12
    assert result.visible_conversation_link_count == 8
    assert result.history_surface_ready is True
    assert "conversation-links-enumerated" in result.history_readiness_signals
    assert result.foreground_activation_observed is False
    assert result.probe_tab_closed is True


def test_history_probe_preserves_transient_presence_as_distinct_observation() -> None:
    provider = _FakeProvider(
        _success_response(
            finalHistoryLinkPresent=False,
            finalHistoryVisibleLinkPresent=False,
            stableHistoryPresence=False,
            transientHistoryPresence=True,
            historyEvidenceStatus="TRANSIENT_PRESENT",
            disappearedAfterSeen=True,
            firstSeenMs=900,
            lastSeenMs=2100,
            seenSampleCount=3,
            absentSampleCount=16,
            conversationLinkCount=11,
        )
    )

    result = probe_temporary_chat_history_presence(
        "conversation-1",
        provider=provider,
    )

    assert result.history_link_present is True
    assert result.final_history_link_present is False
    assert result.stable_history_presence is False
    assert result.transient_history_presence is True
    assert result.history_evidence_status == "TRANSIENT_PRESENT"
    assert result.disappeared_after_seen is True


def test_history_probe_rejects_url_instead_of_raw_conversation_id() -> None:
    with pytest.raises(ValueError, match="raw id"):
        probe_temporary_chat_history_presence(
            "https://chatgpt.com/c/conversation-1",
            provider=_FakeProvider(_success_response()),
        )


def test_history_probe_fails_closed_on_returned_identity_mismatch() -> None:
    provider = _FakeProvider(_success_response(conversationId="other"))
    with pytest.raises(RequestError, match="IDENTITY_MISMATCH"):
        probe_temporary_chat_history_presence(
            "conversation-1",
            provider=provider,
        )


def test_history_probe_promotes_absence_only_after_readiness_and_settling() -> None:
    provider = _FakeProvider(
        _success_response(
            historyLinkPresent=False,
            historyVisibleLinkPresent=False,
            finalHistoryLinkPresent=False,
            finalHistoryVisibleLinkPresent=False,
            stableHistoryPresence=False,
            transientHistoryPresence=False,
            historyAbsenceProven=True,
            historyEvidenceStatus="STABLE_ABSENT",
            disappearedAfterSeen=False,
            firstSeenMs=None,
            lastSeenMs=None,
            seenSampleCount=0,
            absentSampleCount=18,
            conversationLinkCount=9,
        )
    )
    result = probe_temporary_chat_history_presence(
        "conversation-1",
        provider=provider,
    )
    assert result.history_surface_ready is True
    assert result.settle_completed is True
    assert result.history_absence_proven is True
    assert result.history_evidence_status == "STABLE_ABSENT"
    assert result.history_link_present is False
    assert result.final_history_link_present is False


def test_history_probe_without_ready_surface_is_explicitly_inconclusive() -> None:
    provider = _FakeProvider(
        _success_response(
            historyLinkPresent=False,
            historyVisibleLinkPresent=False,
            finalHistoryLinkPresent=False,
            finalHistoryVisibleLinkPresent=False,
            stableHistoryPresence=False,
            transientHistoryPresence=False,
            historyAbsenceProven=False,
            historyEvidenceStatus="INCONCLUSIVE",
            firstSeenMs=None,
            lastSeenMs=None,
            seenSampleCount=0,
            absentSampleCount=1,
            settleCompleted=False,
            conversationLinkCount=0,
            visibleConversationLinkCount=0,
            historySurfaceReady=False,
            historyReadinessSignals=["document-complete", "main-present"],
        )
    )

    result = probe_temporary_chat_history_presence(
        "conversation-1",
        provider=provider,
    )

    assert result.history_surface_ready is False
    assert result.history_absence_proven is False
    assert result.history_evidence_status == "INCONCLUSIVE"
    assert result.absent_sample_count == 1


def test_history_probe_fails_closed_on_bridge_error() -> None:
    provider = _FakeProvider(
        {"ok": False, "error": "TEMPORARY_CHAT_HISTORY_PROBE_TAB_CREATE_FAILED"}
    )
    with pytest.raises(RequestError, match="TAB_CREATE_FAILED"):
        probe_temporary_chat_history_presence(
            "conversation-1",
            provider=provider,
        )
