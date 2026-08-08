from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.conversation_send import send_to_conversation
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.prepared_text_send import send_existing_text_prepared
from chatgpt_web_adapter.types import AttachedConversation, ChatConversation, ChatResponse


class PreparedClient:
    def __init__(self) -> None:
        self.sequence: list[str] = []
        self.events: list[dict] = []
        self.prepare_status = 200
        self.prepare_data = {"status": "ok", "conduit_token": "secret-conduit"}
        self.requirements_error: RequestError | None = None
        self.stream_result = ("conv-1", "assistant-1", "ok")
        self.stream_payload = None
        self.stream_headers = None
        self.prepare_payload = None
        self.timeout = 1
        self.auth = SimpleNamespace(turnstile_token=None)
        self.prefetched_requirements = {"old": True}
        self.prefetched_proof_header = "old-proof"
        self.prefetched_ts = 1.0

    @staticmethod
    def _conversation_to_dict(conversation):
        if isinstance(conversation, ChatConversation):
            return conversation.to_dict()
        return dict(conversation) if isinstance(conversation, dict) else None

    @staticmethod
    def _normalize_reasoning_effort(reasoning_effort):
        return reasoning_effort

    @staticmethod
    def _resolve_model(model, reasoning_effort):
        return model

    @staticmethod
    def _create_messages(prompt, system, *, image_requests=None, system_hints=None):
        assert system is None
        assert image_requests is None
        return [
            {
                "id": "user-message-1",
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": [prompt]},
                "metadata": {"system_hints": system_hints or []},
            }
        ]

    def _emit_event(self, callback, event_type, **payload):
        event = {"type": event_type, **payload}
        self.events.append(event)
        if callback is not None:
            callback(event)

    @staticmethod
    def _build_headers(extra):
        return {key: value for key, value in extra.items() if value is not None}

    def _json_request(self, method, url, payload, headers):
        assert method == "POST"
        assert url.endswith("/backend-api/f/conversation/prepare")
        assert headers["x-conduit-token"] == "no-token"
        self.sequence.append("prepare")
        self.prepare_payload = payload
        return self.prepare_status, self.prepare_data

    def _get_ready_requirements(self):
        self.sequence.append("requirements")
        if self.requirements_error is not None:
            raise self.requirements_error
        return {"token": "chat-token", "turnstile": {"required": False}}, "proof-token"

    def _stream_backend_payload(self, payload, headers, *, on_token=None, on_event=None):
        self.sequence.append("stream")
        self.stream_payload = payload
        self.stream_headers = headers
        if on_token is not None and self.stream_result[2]:
            on_token(self.stream_result[2])
        return self.stream_result

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
        assert allow_global_fallback is False
        if on_token is not None:
            on_token("recovered")
        return (
            {
                "id": "assistant-polled",
                "metadata": {
                    "model_slug": "gpt-5-6-thinking",
                    "thinking_effort": "standard",
                    "finish_details": {"type": "stop"},
                },
            },
            "recovered",
            {},
        )

    @staticmethod
    def _capture_message_diagnostics(message, state):
        metadata = message.get("metadata") if isinstance(message, dict) else None
        if isinstance(metadata, dict):
            state["observed_model"] = metadata.get("model_slug")
            state["observed_reasoning_effort"] = metadata.get("thinking_effort")


def _conversation() -> ChatConversation:
    return ChatConversation(
        conversation_id="conv-1",
        message_id="parent-1",
        user_id="user-1",
    )


def test_prepared_text_send_orders_prepare_requirements_then_final_write() -> None:
    client = PreparedClient()
    response = send_existing_text_prepared(
        client,
        "hello",
        model="gpt-5-6-thinking",
        conversation=_conversation(),
        reasoning_effort="standard",
    )

    assert client.sequence == ["prepare", "requirements", "stream"]
    assert client.prepare_payload["partial_query"]["id"] == "user-message-1"
    assert client.stream_payload["messages"][0]["id"] == "user-message-1"
    assert client.stream_payload["client_prepare_state"] == "success"
    assert client.stream_payload["conversation_id"] == "conv-1"
    assert client.stream_headers["x-conduit-token"] == "secret-conduit"
    assert client.stream_headers["x-oai-turn-trace-id"]
    assert client.stream_headers["x-openai-target-path"] == "/backend-api/f/conversation"
    assert client.stream_headers["x-openai-target-route"] == "/backend-api/f/conversation"
    assert client.stream_headers["openai-sentinel-chat-requirements-token"] == "chat-token"
    assert response.text == "ok"
    assert response.request.sent_model == "gpt-5-6-thinking"
    assert response.request.sent_reasoning_effort == "standard"
    assert client.prefetched_requirements is None
    assert client.prefetched_proof_header is None
    assert client.prefetched_ts == 0.0


def test_prepared_text_send_events_never_expose_conduit_token_value() -> None:
    client = PreparedClient()
    send_existing_text_prepared(
        client,
        "secret prompt",
        model="gpt-5-6-thinking",
        conversation=_conversation(),
    )
    rendered = repr(client.events)
    assert "secret-conduit" not in rendered
    assert "secret prompt" not in rendered
    assert any(event["type"] == "conversation_prepare_succeeded" for event in client.events)


def test_prepare_rejection_stops_before_requirements_and_final_write() -> None:
    client = PreparedClient()
    client.prepare_status = 403
    client.prepare_data = {"detail": "rejected"}

    with pytest.raises(RequestError, match="conversation prepare status=403") as captured:
        send_existing_text_prepared(
            client,
            "hello",
            model="gpt-5-6-thinking",
            conversation=_conversation(),
        )

    assert captured.value.request_stage == "conversation_prepare"
    assert client.sequence == ["prepare"]
    assert client.stream_payload is None


def test_missing_conduit_token_stops_before_requirements_and_final_write() -> None:
    client = PreparedClient()
    client.prepare_data = {"status": "ok"}

    with pytest.raises(RequestError, match="missing conduit_token"):
        send_existing_text_prepared(
            client,
            "hello",
            model="gpt-5-6-thinking",
            conversation=_conversation(),
        )

    assert client.sequence == ["prepare"]
    assert client.stream_payload is None


def test_turnstile_gate_after_prepare_stops_before_final_write() -> None:
    client = PreparedClient()
    client.requirements_error = RequestError(
        "TURNSTILE_REQUIRED",
        request_stage="turnstile_gate",
    )

    with pytest.raises(RequestError) as captured:
        send_existing_text_prepared(
            client,
            "hello",
            model="gpt-5-6-thinking",
            conversation=_conversation(),
        )

    assert captured.value.request_stage == "turnstile_gate"
    assert client.sequence == ["prepare", "requirements"]
    assert client.stream_payload is None


def test_prepared_text_send_polls_when_stream_handoff_has_no_text() -> None:
    client = PreparedClient()
    client.stream_result = ("conv-1", None, "")
    tokens: list[str] = []

    response = send_existing_text_prepared(
        client,
        "hello",
        model="gpt-5-6-thinking",
        conversation=_conversation(),
        reasoning_effort="standard",
        on_token=tokens.append,
    )

    assert client.sequence == ["prepare", "requirements", "stream", "poll"]
    assert response.text == "recovered"
    assert response.conversation.message_id == "assistant-polled"
    assert response.request.observed_model == "gpt-5-6-thinking"
    assert response.request.observed_reasoning_effort == "standard"
    assert tokens == ["recovered"]


def test_send_to_conversation_routes_text_to_prepared_path(monkeypatch) -> None:
    attached = AttachedConversation(
        conversation=_conversation(),
        detected_model="gpt-5-6-thinking",
        detected_reasoning_effort="standard",
    )

    class Client:
        def attach_conversation(self, value):
            return attached

        def send(self, *args, **kwargs):
            raise AssertionError("legacy send must not handle ordinary existing text")

    calls = []

    def fake_prepared(self, prompt, **kwargs):
        calls.append((prompt, kwargs))
        return ChatResponse(text="prepared")

    monkeypatch.setattr(
        "chatgpt_web_adapter.conversation_send.send_existing_text_prepared",
        fake_prepared,
    )
    response = send_to_conversation(Client(), "conv-1", "hello")
    assert response.text == "prepared"
    assert calls[0][1]["model"] == "gpt-5-6-thinking"
    assert calls[0][1]["reasoning_effort"] == "standard"
    assert calls[0][1]["conversation"].conversation_id == "conv-1"


def test_send_to_conversation_keeps_media_on_legacy_send(monkeypatch) -> None:
    attached = AttachedConversation(
        conversation=_conversation(),
        detected_model="gpt-5-6-thinking",
        detected_reasoning_effort="standard",
    )

    class Client:
        def attach_conversation(self, value):
            return attached

        def send(self, prompt, **kwargs):
            assert kwargs["media"] == [b"image-bytes"]
            return ChatResponse(text="legacy-media")

    def forbidden_prepared(*args, **kwargs):
        raise AssertionError("media must not enter prepared text path")

    monkeypatch.setattr(
        "chatgpt_web_adapter.conversation_send.send_existing_text_prepared",
        forbidden_prepared,
    )
    response = send_to_conversation(
        Client(),
        "conv-1",
        "hello",
        media=[b"image-bytes"],
    )
    assert response.text == "legacy-media"
