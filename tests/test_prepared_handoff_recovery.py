from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter as adapter
import pytest

from chatgpt_web_adapter.prepared_text_send import send_existing_text_prepared
from chatgpt_web_adapter.types import ChatConversation


class HandoffClient:
    _parse_event = staticmethod(adapter.ChatGPTWebClient._parse_event)
    _capture_message_diagnostics = staticmethod(
        adapter.ChatGPTWebClient._capture_message_diagnostics
    )

    def __init__(self) -> None:
        self.sequence: list[str] = []
        self.timeout = 1
        self.auth = SimpleNamespace(turnstile_token=None)
        self.prefetched_requirements = None
        self.prefetched_proof_header = None
        self.prefetched_ts = 0.0

    @staticmethod
    def _conversation_to_dict(conversation):
        if isinstance(conversation, ChatConversation):
            return conversation.to_dict()
        return dict(conversation)

    @staticmethod
    def _normalize_reasoning_effort(reasoning_effort):
        return reasoning_effort

    @staticmethod
    def _resolve_model(model, reasoning_effort):
        return model

    @staticmethod
    def _create_messages(prompt, system, *, image_requests=None, system_hints=None):
        return [
            {
                "id": "user-message-1",
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": [prompt]},
            }
        ]

    @staticmethod
    def _build_headers(extra):
        return {key: value for key, value in extra.items() if value is not None}

    @staticmethod
    def _emit_event(callback, event_type, **payload):
        if callback is not None:
            callback({"type": event_type, **payload})

    def _json_request(self, method, url, payload, headers):
        self.sequence.append("prepare")
        return 200, {"status": "ok", "conduit_token": "secret-conduit"}

    def _get_ready_requirements(self):
        self.sequence.append("requirements")
        return {"token": "chat-token", "turnstile": {"required": False}}, "proof-token"

    def _stream_backend_payload(self, payload, headers, *, on_token=None, on_event=None):
        self.sequence.append("stream")
        parser_state = {
            "recipient": "all",
            "conversation_id": "conv-1",
            "message_id": "assistant-partial",
            "parent_message_id": "assistant-partial",
            "finish_reason": "stop",
        }
        self._parse_event(
            {
                "type": "stream_handoff",
                "conversation_id": "conv-1",
                "options": [
                    {"type": "subscribe_ws_topic", "topic_id": "sensitive-topic-id"}
                ],
            },
            parser_state,
        )
        if on_token is not None:
            on_token("prefix")
        self._emit_event(on_event, "assistant_token", token="prefix")
        return "conv-1", "assistant-partial", "prefix"

    def _poll_conversation_after_prepare(
        self,
        conversation_id,
        *,
        previous_message_id,
        timeout,
        interval,
        on_token=None,
        on_event=None,
        reason,
        allow_global_fallback,
    ):
        self.sequence.append("poll")
        assert conversation_id == "conv-1"
        assert previous_message_id == "parent-1"
        assert on_token is None
        assert reason == "prepared_text_send_handoff_recovery"
        assert allow_global_fallback is False
        return (
            {
                "id": "assistant-final",
                "metadata": {
                    "model_slug": "gpt-5-6-thinking",
                    "thinking_effort": "standard",
                    "finish_details": {"type": "stop"},
                },
            },
            "prefix suffix",
            {},
        )


def _conversation() -> ChatConversation:
    return ChatConversation(
        conversation_id="conv-1",
        message_id="parent-1",
        user_id="user-1",
    )


def test_partial_stream_handoff_forces_recovery_and_emits_only_suffix() -> None:
    client = HandoffClient()
    tokens: list[str] = []
    events: list[dict] = []

    response = send_existing_text_prepared(
        client,
        "hello",
        model="gpt-5-6-thinking",
        conversation=_conversation(),
        reasoning_effort="standard",
        on_token=tokens.append,
        on_event=events.append,
    )

    assert client.sequence == ["prepare", "requirements", "stream", "poll"]
    assert response.text == "prefix suffix"
    assert response.conversation.message_id == "assistant-final"
    assert tokens == ["prefix", " suffix"]
    assert not any(event.get("type") == "assistant_token" for event in events)
    completed = [
        event
        for event in events
        if event.get("type") == "prepared_conversation_write_completed"
    ]
    assert completed[-1]["handoff_recovery_used"] is True
    assert "sensitive-topic-id" not in repr(events)


def test_partial_stream_handoff_never_returns_prefix_after_recovery_timeout() -> None:
    class TimeoutClient(HandoffClient):
        def _poll_conversation_after_prepare(self, *args, **kwargs):
            self.sequence.append("poll")
            return None, "", None

    client = TimeoutClient()
    tokens: list[str] = []

    with pytest.raises(adapter.RequestError) as captured:
        send_existing_text_prepared(
            client,
            "hello",
            model="gpt-5-6-thinking",
            conversation=_conversation(),
            on_token=tokens.append,
        )

    assert captured.value.request_stage == "prepared_stream_handoff_recovery"
    assert "completed assistant message" in str(captured.value)
    assert client.sequence == ["prepare", "requirements", "stream", "poll"]
    assert tokens == ["prefix"]
