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
    assert client.last_timing["pre_stream_seconds"] >= client.last_timing["bootstrap_seconds"]
    assert client.last_timing["attach_seconds"] is None
    assert client.last_timing["total_seconds"] >= 0


def test_dispatch_identity_exposes_only_minimal_fields(harness, monkeypatch):
    client, _, _ = harness
    identities = []
    events = []

    def underlying(_self, prompt, **kwargs):
        callback = kwargs["on_event"]
        callback({"type": "request_payload_prepared", "payload": {
            "conversation_id": "chat", "parent_message_id": "old",
            "messages": [{"id": "new", "author": {"role": "user"},
                          "content": {"parts": ["private prompt"]}}],
        }})
        callback({"type": "stream_started"})
        return ChatResponse(text="ok")

    monkeypatch.setattr(ChatGPTWebClient, "send", underlying)
    client.send("private prompt", on_dispatch_identity=identities.append, on_event=events.append)
    assert identities == [{"conversation_id": "chat", "parent_message_id": "old",
                           "user_message_id": "new", "temporary": False}]
    assert "private prompt" not in repr(identities)
    assert len(events) == 2


def test_dispatch_identity_failure_stops_before_stream(harness, monkeypatch):
    client, _, _ = harness
    stages = []

    def underlying(_self, prompt, **kwargs):
        callback = kwargs["on_event"]
        callback({"type": "request_payload_prepared", "payload": {
            "messages": [{"id": "new", "author": {"role": "user"}}],
        }})
        stages.append("stream")
        return ChatResponse(text="ok")

    def fail(_identity):
        raise OSError("synthetic persistence failure")

    monkeypatch.setattr(ChatGPTWebClient, "send", underlying)
    with pytest.raises(OSError, match="persistence"):
        client.send("synthetic", on_dispatch_identity=fail)
    assert stages == []


def test_dispatch_identity_missing_fails_before_stream(harness):
    client, _, _ = harness
    with pytest.raises(RequestError, match="dispatch identity"):
        client.send("synthetic", on_dispatch_identity=lambda identity: None)


@pytest.mark.parametrize("messages", [[], [{"author": {"role": "user"}}],
    [{"id": "a", "author": {"role": "user"}},
     {"id": "b", "author": {"role": "user"}}]])
def test_dispatch_identity_rejects_missing_or_multiple_users(harness, monkeypatch, messages):
    client, _, _ = harness
    def underlying(_self, prompt, **kwargs):
        kwargs["on_event"]({"type": "request_payload_prepared", "payload": {"messages": messages}})
        raise AssertionError("should stop before POST")
    monkeypatch.setattr(ChatGPTWebClient, "send", underlying)
    with pytest.raises(RequestError, match="dispatch identity"):
        client.send("synthetic", on_dispatch_identity=lambda identity: None)


def test_continuation_temporary_and_media_forwarded_without_browser_fallback(
    harness, monkeypatch
):
    client, calls, _ = harness
    requested_files = ["notes-a.md", "notes-b.md"]
    attached = SimpleNamespace(
        conversation=ChatConversation(
            conversation_id="existing", message_id="assistant-last"
        )
    )
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
    assert client.last_timing["attach_seconds"] >= 0

    client.send("Ephemeral", temporary=True)
    assert calls[1][1]["temporary"] is True
    assert calls[1][1]["conversation"] is None


def test_attach_failure_retains_phase_timing_and_never_dispatches(harness, monkeypatch):
    client, calls, _ = harness

    def fail(_identity):
        raise RequestError("GET timed out")

    monkeypatch.setattr(client, "attach_conversation", fail)
    with pytest.raises(RequestError, match="GET timed out"):
        client.send("Continue", conversation="existing")
    assert client.last_timing["bootstrap_seconds"] >= 0
    assert client.last_timing["attach_seconds"] >= 0
    assert client.last_timing["pre_stream_seconds"] is None
    assert calls == []


def test_bootstrap_failure_retains_phase_timing_and_never_dispatches(harness, monkeypatch):
    client, calls, _ = harness
    monkeypatch.setattr(
        "chatgpt_web_adapter.browserless_http.bootstrap_web_session", lambda _: False
    )
    with pytest.raises(RequestError, match="bootstrap"):
        client.send("Continue", conversation="existing")
    assert client.last_timing["bootstrap_seconds"] >= 0
    assert client.last_timing["attach_seconds"] is None
    assert client.last_timing["pre_stream_seconds"] is None
    assert calls == []


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


def test_deep_research_opt_in_forwards_exact_product_hint(harness):
    client, calls, _ = harness
    client.send("Research a topic", deep_research=True)
    assert len(calls) == 1
    assert calls[0][1]["_system_hints"] == ["plugin:connector_openai_deep_research"]
    client.send("Ordinary text")
    assert "_system_hints" not in calls[1][1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temporary": True},
        {"conversation": "existing"},
        {"media": ["notes.md"]},
        {"conversation_origin": "flora"},
    ],
)
def test_deep_research_unsupported_combinations_fail_before_network(harness, kwargs):
    client, calls, _ = harness
    with pytest.raises(ValueError, match="deep_research"):
        client.send("Research a topic", deep_research=True, **kwargs)
    assert calls == []
