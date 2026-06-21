from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest

from webchat_adapter import (
    ChatGPTWebClient,
    ChatResponse,
    PayloadValidationError,
    RequestError,
)


def _client() -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client.auth = SimpleNamespace(turnstile_token="turnstile-token")
    return client


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": "next",
        "parent_message_id": "parent-1",
        "model": "gpt-4o-mini",
        "messages": [{"id": "msg-1"}],
    }
    payload.update(overrides)
    return payload


def _install_requirements(client: ChatGPTWebClient, *, turnstile_required: bool = False) -> list[dict[str, Any]]:
    header_inputs: list[dict[str, Any]] = []
    client._get_ready_requirements = lambda: (
        {"token": "requirements-token", "turnstile": {"required": turnstile_required}},
        "proof-token",
    )

    def build_headers(extra: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = dict(extra or {})
        header_inputs.append(headers)
        return headers

    client._build_headers = build_headers
    return header_inputs


def test_send_payload_method_is_available_on_client() -> None:
    assert hasattr(ChatGPTWebClient, "send_payload")


def test_send_payload_rejects_non_dict_payload_before_network() -> None:
    client = _client()
    client._get_ready_requirements = lambda: pytest.fail("requirements must not be fetched")

    with pytest.raises(PayloadValidationError, match="payload must be a dict"):
        client.send_payload("bad")


def test_send_payload_validates_before_requirements() -> None:
    client = _client()
    client._get_ready_requirements = lambda: pytest.fail("requirements must not be fetched")

    with pytest.raises(PayloadValidationError, match="model is required"):
        client.send_payload(
            {
                "action": "next",
                "parent_message_id": "parent-1",
                "messages": [{"id": "msg-1"}],
            }
        )


def test_send_payload_deep_copies_payload_before_transport() -> None:
    client = _client()
    _install_requirements(client)
    payload = _payload(messages=[{"content": {"parts": ["hello"]}}])
    original = copy.deepcopy(payload)
    observed_payloads: list[dict[str, Any]] = []

    def fake_stream(stream_payload: dict[str, Any], *_args: Any, **_kwargs: Any) -> tuple[str, str, str]:
        observed_payloads.append(stream_payload)
        stream_payload["messages"][0]["content"]["parts"][0] = "mutated"
        return "conv-1", "msg-1", "ok"

    client._stream_backend_payload = fake_stream

    client.send_payload(payload)

    assert payload == original
    assert observed_payloads[0] is not payload


def test_send_payload_gets_requirements_and_builds_stream_headers() -> None:
    client = _client()
    header_inputs = _install_requirements(client, turnstile_required=True)
    client._stream_backend_payload = lambda *_args, **_kwargs: ("conv-1", "msg-1", "ok")

    client.send_payload(_payload())

    assert header_inputs == [
        {
            "accept": "text/event-stream",
            "content-type": "application/json",
            "openai-sentinel-chat-requirements-token": "requirements-token",
            "openai-sentinel-proof-token": "proof-token",
            "openai-sentinel-turnstile-token": "turnstile-token",
        }
    ]


def test_send_payload_omits_turnstile_header_when_not_required() -> None:
    client = _client()
    header_inputs = _install_requirements(client)
    client._stream_backend_payload = lambda *_args, **_kwargs: ("conv-1", "msg-1", "ok")

    client.send_payload(_payload())

    assert header_inputs[0]["openai-sentinel-turnstile-token"] is None


def test_send_payload_requires_chat_requirements_token() -> None:
    client = _client()
    client._get_ready_requirements = lambda: ({"token": ""}, "proof-token")
    client._build_headers = lambda extra=None: dict(extra or {})
    client._stream_backend_payload = lambda *_args, **_kwargs: pytest.fail("stream must not run")

    with pytest.raises(RequestError, match="chat-requirements token is missing"):
        client.send_payload(_payload())


def test_send_payload_calls_stream_backend_with_payload_headers_and_callbacks() -> None:
    client = _client()
    _install_requirements(client)
    tokens: list[str] = []
    events: list[dict[str, Any]] = []
    on_token = tokens.append
    on_event = events.append
    payload = _payload(messages=[{"id": "msg"}])
    observed: dict[str, Any] = {}

    def fake_stream(
        stream_payload: dict[str, Any],
        headers: dict[str, Any],
        *,
        on_token: Any = None,
        on_event: Any = None,
    ) -> tuple[str, str, str]:
        observed.update(
            payload=stream_payload,
            headers=headers,
            on_token=on_token,
            on_event=on_event,
        )
        return "conv-1", "msg-1", "hello"

    client._stream_backend_payload = fake_stream

    response = client.send_payload(payload, on_token=on_token, on_event=on_event)

    assert observed["payload"] == payload
    assert observed["payload"] is not payload
    assert observed["headers"]["openai-sentinel-chat-requirements-token"] == "requirements-token"
    assert observed["on_token"] is on_token
    assert observed["on_event"] is on_event
    assert response.text == "hello"


def test_send_payload_returns_chat_response() -> None:
    client = _client()
    _install_requirements(client)
    client._stream_backend_payload = lambda *_args, **_kwargs: ("conv-1", "msg-1", "hello")

    response = client.send_payload(_payload())

    assert isinstance(response, ChatResponse)
    assert response.text == "hello"
    assert response.conversation.conversation_id == "conv-1"
    assert response.conversation.message_id == "msg-1"
    assert response.conversation.parent_message_id == "msg-1"
    assert response.conversation.finish_reason == "stop"
    assert response.conversation.is_thinking is False
    assert response.metrics.total is not None


def test_send_payload_uses_payload_id_fallbacks_when_stream_returns_none() -> None:
    client = _client()
    _install_requirements(client)
    client._stream_backend_payload = lambda *_args, **_kwargs: (None, None, "hello")

    response = client.send_payload(_payload(conversation_id="conv-existing"))

    assert response.conversation.conversation_id == "conv-existing"
    assert response.conversation.message_id == "parent-1"
    assert response.conversation.parent_message_id == "parent-1"


def test_send_payload_emits_raw_payload_sent_on_success() -> None:
    client = _client()
    _install_requirements(client)
    events: list[dict[str, Any]] = []
    client._stream_backend_payload = lambda *_args, **_kwargs: ("conv-1", "msg-1", "hello")

    client.send_payload(_payload(messages=[{"id": "m1"}]), on_event=events.append)

    assert events[-1] == {
        "type": "raw_payload_sent",
        "experimental": True,
        "conversation_id": "conv-1",
        "message_id": "msg-1",
        "message_count": 1,
    }


def test_send_payload_does_not_emit_success_event_on_stream_error() -> None:
    client = _client()
    _install_requirements(client)
    events: list[dict[str, Any]] = []

    def fake_stream(*_args: Any, **_kwargs: Any) -> tuple[str, str, str]:
        raise RequestError("transport failed")

    client._stream_backend_payload = fake_stream

    with pytest.raises(RequestError, match="transport failed"):
        client.send_payload(_payload(), on_event=events.append)

    assert events == []
