"""Contract regressions for the experimental HTTP client, without live writes.

Keep private protocol, browser-backed paths and Qwen out of this suite.
"""

from __future__ import annotations

from contextlib import nullcontext
from threading import RLock
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.types import ChatConversation, ChatResponse


@pytest.fixture
def harness(monkeypatch):
    client = object.__new__(BrowserlessHTTPClient)
    client._browserless_lock = RLock()
    client._browserless_sending = False
    client.last_timing = {}
    bundles = []
    calls = []
    client.set_sentinel_bundle_provider = bundles.append
    monkeypatch.setattr(
        "chatgpt_web_adapter.browserless_http.bootstrap_web_session",
        lambda _: True,
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.browserless_http.suppress_web_session_debug_trace",
        nullcontext,
    )

    def underlying(_self, prompt, **kwargs):
        calls.append((prompt, kwargs))
        if callback := kwargs.get("on_event"):
            callback({"type": "stream_started"})
        if callback := kwargs.get("on_token"):
            callback("Hel")
            callback("lo")
        return ChatResponse(
            text="Hello",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="assistant-1",
                parent_message_id="assistant-1",
            ),
        )

    monkeypatch.setattr(ChatGPTWebClient, "send", underlying)
    return client, calls, bundles


def test_direct_new_chat_streams_and_retains_conversation_identity(harness):
    client, calls, bundles = harness
    tokens = []
    events = []

    response = client.send(
        "Hi",
        on_token=tokens.append,
        on_event=events.append,
    )

    assert response.text == "Hello"
    assert response.conversation.conversation_id == "conversation-1"
    assert response.conversation.message_id == "assistant-1"
    assert tokens == ["Hel", "lo"]
    assert events == [{"type": "stream_started"}]
    assert len(calls) == 1
    assert calls[0][1]["model"] == "gpt-6-instant"
    assert calls[0][1]["temporary"] is False
    assert bundles[-1] is None
    assert client._browserless_sending is False
    assert client.last_timing["ttft_seconds"] is not None
    assert client.last_timing["stream_ttft_seconds"] is not None
    assert client.last_timing["total_seconds"] >= 0


def test_continuation_temporary_and_media_forwarded_without_browser_fallback(harness, monkeypatch):
    client, calls, _ = harness
    requested_files = ["notes-a.md", "notes-b.md"]
    attached = SimpleNamespace(conversation=ChatConversation(
        conversation_id="existing", message_id="assistant-last"
    ))
    monkeypatch.setattr(client, "attach_conversation", lambda identity: attached)

    client.send(
        "Continue",
        conversation="existing",
        temporary=False,
        media=requested_files,
    )
    _, kwargs = calls[0]
    assert kwargs["conversation"] is attached.conversation
    assert kwargs["media"] is requested_files

    client.send("Ephemeral", temporary=True)
    assert calls[1][1]["temporary"] is True
    assert calls[1][1]["conversation"] is None


def test_failed_direct_send_does_not_replay_or_leave_client_busy(harness, monkeypatch):
    client, calls, bundles = harness

    def lost_response(_self, prompt, **kwargs):
        calls.append((prompt, kwargs))
        raise RequestError("connection lost after possible write")

    monkeypatch.setattr(ChatGPTWebClient, "send", lost_response)

    with pytest.raises(RequestError, match="connection lost"):
        client.send("Only once")
    assert len(calls) == 1
    assert client._browserless_sending is False
    assert bundles[-1] is None


def test_reentrant_send_is_rejected_before_network(harness):
    client, calls, _ = harness
    client._browserless_sending = True

    with pytest.raises(RuntimeError, match="reentrant send"):
        client.send("Must not dispatch")
    assert calls == []


def test_invalid_request_fails_before_network(harness):
    client, calls, _ = harness

    with pytest.raises(ValueError, match="nonempty"):
        client.send("   ")
    with pytest.raises(ValueError, match="model"):
        client.send("Valid prompt", model=" ")
    with pytest.raises(ValueError, match="conversation_origin"):
        client.send("Valid prompt", conversation_origin="unknown")
    assert calls == []
