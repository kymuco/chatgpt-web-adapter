from __future__ import annotations

from typing import Any

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.client import DEFAULT_MODEL


CONVERSATION_ID = "conv-123"


def _attached(
    *,
    detected_model: str | None = "gpt-5-5-thinking",
    detected_reasoning_effort: str | None = None,
) -> adapter.AttachedConversation:
    return adapter.AttachedConversation(
        conversation=adapter.ChatConversation(
            conversation_id=CONVERSATION_ID,
            message_id="message-123",
            parent_message_id="message-123",
        ),
        detected_model=detected_model,
        detected_reasoning_effort=detected_reasoning_effort,
    )


def _client_with_attach_and_send(
    attached: adapter.AttachedConversation,
) -> tuple[adapter.ChatGPTWebClient, list[Any], list[dict[str, Any]], adapter.ChatResponse]:
    client = object.__new__(adapter.ChatGPTWebClient)
    attach_calls: list[Any] = []
    send_calls: list[dict[str, Any]] = []
    response = adapter.ChatResponse(
        text="continued",
        conversation=adapter.ChatConversation(
            conversation_id=CONVERSATION_ID,
            message_id="assistant-1",
        ),
    )

    def attach_conversation(url_or_id: Any) -> adapter.AttachedConversation:
        attach_calls.append(url_or_id)
        return attached

    def send(prompt: str, **kwargs: Any) -> adapter.ChatResponse:
        send_calls.append({"prompt": prompt, **kwargs})
        return response

    client.attach_conversation = attach_conversation
    client.send = send
    return client, attach_calls, send_calls, response


def test_send_to_conversation_is_available_on_public_client_class() -> None:
    assert hasattr(adapter.ChatGPTWebClient, "send_to_conversation")


def test_send_to_conversation_attaches_and_sends_with_detected_model() -> None:
    attached = _attached(detected_model="gpt-5-5-thinking")
    client, attach_calls, send_calls, response = _client_with_attach_and_send(attached)

    result = client.send_to_conversation(CONVERSATION_ID, "РџСЂРѕРґРѕР»Р¶Рё")

    assert result is response
    assert attach_calls == [CONVERSATION_ID]
    assert send_calls == [
        {
            "prompt": "РџСЂРѕРґРѕР»Р¶Рё",
            "model": "gpt-5-5-thinking",
            "system": None,
            "web_search": False,
            "temporary": False,
            "reasoning_effort": None,
            "conversation": attached.conversation,
            "media": None,
            "on_token": None,
        }
    ]


def test_send_to_conversation_passes_url_to_attach_unchanged() -> None:
    attached = _attached()
    client, attach_calls, _send_calls, _response = _client_with_attach_and_send(attached)
    url = f"https://chatgpt.com/c/{CONVERSATION_ID}"

    client.send_to_conversation(url, "РџСЂРѕРґРѕР»Р¶Рё")

    assert attach_calls == [url]


def test_send_to_conversation_explicit_model_wins_over_detected_model() -> None:
    attached = _attached(detected_model="gpt-5-5-thinking")
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(
        CONVERSATION_ID,
        "РџСЂРѕРґРѕР»Р¶Рё",
        model="gpt-4.1",
        preserve_model=True,
    )

    assert send_calls[0]["model"] == "gpt-4.1"


def test_send_to_conversation_preserve_model_false_ignores_detected_model() -> None:
    attached = _attached(detected_model="gpt-5-5-thinking")
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(
        CONVERSATION_ID,
        "РџСЂРѕРґРѕР»Р¶Рё",
        preserve_model=False,
    )

    assert send_calls[0]["model"] == DEFAULT_MODEL


def test_send_to_conversation_unknown_detected_model_uses_default_model() -> None:
    attached = _attached(detected_model=None)
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(CONVERSATION_ID, "РџСЂРѕРґРѕР»Р¶Рё")

    assert send_calls[0]["model"] == DEFAULT_MODEL


def test_send_to_conversation_default_reasoning_effort_stays_none_when_not_detected() -> None:
    attached = _attached()
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(CONVERSATION_ID, "РџСЂРѕРґРѕР»Р¶Рё")

    assert send_calls[0]["reasoning_effort"] is None


def test_send_to_conversation_preserves_detected_reasoning_effort() -> None:
    attached = _attached(detected_reasoning_effort="extended")
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(CONVERSATION_ID, "Р СџРЎР‚Р С•Р Т‘Р С•Р В»Р В¶Р С‘")

    assert send_calls[0]["reasoning_effort"] == "extended"


def test_send_to_conversation_passes_explicit_reasoning_effort() -> None:
    attached = _attached()
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(
        CONVERSATION_ID,
        "РџСЂРѕРґРѕР»Р¶Рё",
        reasoning_effort="extended",
    )

    assert send_calls[0]["reasoning_effort"] == "extended"


def test_send_to_conversation_explicit_model_does_not_carry_detected_reasoning_effort() -> None:
    attached = _attached(
        detected_model="gpt-5-5-thinking",
        detected_reasoning_effort="extended",
    )
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(
        CONVERSATION_ID,
        "Р СџРЎР‚Р С•Р Т‘Р С•Р В»Р В¶Р С‘",
        model="gpt-4.1",
    )

    assert send_calls[0]["reasoning_effort"] is None


def test_send_to_conversation_preserve_model_false_does_not_carry_detected_reasoning_effort() -> None:
    attached = _attached(
        detected_model="gpt-5-5-thinking",
        detected_reasoning_effort="extended",
    )
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)

    client.send_to_conversation(
        CONVERSATION_ID,
        "Р СџРЎР‚Р С•Р Т‘Р С•Р В»Р В¶Р С‘",
        preserve_model=False,
    )

    assert send_calls[0]["reasoning_effort"] is None


def test_send_to_conversation_passes_send_options_through() -> None:
    attached = _attached()
    client, _attach_calls, send_calls, _response = _client_with_attach_and_send(attached)
    media = [(b"image-bytes", "image.png")]

    def on_token(token: str) -> None:
        assert token

    client.send_to_conversation(
        CONVERSATION_ID,
        "РџСЂРѕРґРѕР»Р¶Рё",
        system="system prompt",
        web_search=True,
        temporary=True,
        media=media,
        on_token=on_token,
    )

    call = send_calls[0]
    assert call["system"] == "system prompt"
    assert call["web_search"] is True
    assert call["temporary"] is True
    assert call["media"] == media
    assert call["on_token"] is on_token


def test_send_to_conversation_propagates_attach_errors_without_sending() -> None:
    client = object.__new__(adapter.ChatGPTWebClient)
    send_called = False

    def attach_conversation(url_or_id: Any) -> adapter.AttachedConversation:
        raise adapter.RequestError(f"conversation status=404: {url_or_id}")

    def send(prompt: str, **kwargs: Any) -> adapter.ChatResponse:
        nonlocal send_called
        send_called = True
        return adapter.ChatResponse(text="unexpected")

    client.attach_conversation = attach_conversation
    client.send = send

    with pytest.raises(adapter.RequestError, match="status=404"):
        client.send_to_conversation(CONVERSATION_ID, "РџСЂРѕРґРѕР»Р¶Рё")

    assert send_called is False
