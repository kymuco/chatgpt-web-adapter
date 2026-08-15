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
        "probeContext": "fresh_root_history_presence",
        "conversationId": "conversation-1",
        "historyLinkPresent": True,
        "historyVisibleLinkPresent": True,
        "conversationLinkCount": 12,
        "historySurfaceReady": True,
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "probeTabClosed": True,
        "elapsedMs": 1200,
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

    assert result.probe_context == "fresh_root_history_presence"
    assert result.conversation_id == "conversation-1"
    assert result.history_link_present is True
    assert result.history_visible_link_present is True
    assert result.conversation_link_count == 12
    assert result.history_surface_ready is True
    assert result.foreground_activation_observed is False
    assert result.probe_tab_closed is True


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


def test_history_probe_preserves_absence_as_observation_not_error() -> None:
    provider = _FakeProvider(
        _success_response(
            historyLinkPresent=False,
            historyVisibleLinkPresent=False,
            conversationLinkCount=9,
        )
    )
    result = probe_temporary_chat_history_presence(
        "conversation-1",
        provider=provider,
    )
    assert result.history_surface_ready is True
    assert result.history_link_present is False
    assert result.history_visible_link_present is False


def test_history_probe_fails_closed_on_bridge_error() -> None:
    provider = _FakeProvider(
        {"ok": False, "error": "TEMPORARY_CHAT_HISTORY_PROBE_TAB_CREATE_FAILED"}
    )
    with pytest.raises(RequestError, match="TAB_CREATE_FAILED"):
        probe_temporary_chat_history_presence(
            "conversation-1",
            provider=provider,
        )
