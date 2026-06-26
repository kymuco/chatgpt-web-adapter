from __future__ import annotations

from typing import Any

import pytest

import chatgpt_web_adapter as adapter
import chatgpt_web_adapter.client as client_mod


CONVERSATION_ID = "conv-123"


def _client_with_payload(payload: dict[str, Any]) -> tuple[adapter.ChatGPTWebClient, list[str]]:
    client = object.__new__(adapter.ChatGPTWebClient)
    calls: list[str] = []

    def get_conversation_payload(conversation_id: str) -> dict[str, Any]:
        calls.append(conversation_id)
        return payload

    client._get_conversation_payload = get_conversation_payload
    return client, calls


def _message_node(
    message_id: str,
    *,
    role: str = "assistant",
    text: str = "message",
    create_time: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "message": {
            "id": message_id,
            "author": {"role": role},
            "create_time": create_time,
            "content": {"content_type": "text", "parts": [text]},
            "metadata": dict(metadata or {}),
        }
    }


def test_attach_conversation_is_available_on_public_client_class() -> None:
    assert hasattr(adapter.ChatGPTWebClient, "attach_conversation")
    assert hasattr(client_mod.ChatGPTWebClient, "attach_conversation")


def test_attach_conversation_accepts_raw_id() -> None:
    client, calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "assistant-1",
            "mapping": {
                "assistant-1": _message_node(
                    "assistant-1",
                    metadata={"finish_details": {"type": "stop"}},
                ),
            },
            "title": "Existing chat",
            "async_status": None,
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert calls == [CONVERSATION_ID]
    assert isinstance(attached, adapter.AttachedConversation)
    assert attached.conversation_id == CONVERSATION_ID
    assert attached.conversation.message_id == "assistant-1"
    assert attached.conversation.parent_message_id == "assistant-1"
    assert attached.conversation.finish_reason == "stop"
    assert attached.current_node == "assistant-1"
    assert attached.title == "Existing chat"
    assert attached.raw_status == {"async_status": None}


def test_attach_conversation_accepts_chatgpt_url() -> None:
    client, calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {},
        }
    )

    attached = client.attach_conversation(f"https://chatgpt.com/c/{CONVERSATION_ID}")

    assert calls == [CONVERSATION_ID]
    assert attached.conversation_id == CONVERSATION_ID


def test_attach_conversation_uses_latest_assistant_when_current_node_is_missing() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {
                "assistant-old": _message_node("assistant-old", create_time=1.0),
                "assistant-new": _message_node("assistant-new", create_time=2.0),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.conversation.message_id == "assistant-new"
    assert attached.conversation.parent_message_id == "assistant-new"


def test_attach_conversation_uses_latest_any_message_when_no_assistant_exists() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {
                "user-old": _message_node("user-old", role="user", create_time=1.0),
                "user-new": _message_node("user-new", role="user", create_time=2.0),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.conversation.message_id == "user-new"
    assert attached.conversation.parent_message_id == "user-new"


def test_attach_conversation_detects_model_from_current_message_metadata() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "assistant-1",
            "mapping": {
                "assistant-1": _message_node(
                    "assistant-1",
                    metadata={"model_slug": "gpt-5-5-thinking"},
                ),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_model == "gpt-5-5-thinking"


def test_attach_conversation_detects_reasoning_effort_from_current_message_metadata() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "assistant-1",
            "mapping": {
                "assistant-1": _message_node(
                    "assistant-1",
                    metadata={
                        "model_slug": "gpt-5-5-thinking",
                        "thinking_effort": "extended",
                    },
                ),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_reasoning_effort == "extended"


def test_attach_conversation_detects_model_from_latest_assistant_metadata() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "user-1",
            "mapping": {
                "user-1": _message_node("user-1", role="user", create_time=3.0),
                "assistant-1": _message_node(
                    "assistant-1",
                    create_time=2.0,
                    metadata={"model": "gpt-4.1"},
                ),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_model == "gpt-4.1"


def test_attach_conversation_detects_model_from_payload_metadata() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {},
            "metadata": {"default_model_slug": "gpt-4.1-mini"},
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_model == "gpt-4.1-mini"


def test_attach_conversation_detects_reasoning_effort_from_payload_metadata() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {},
            "metadata": {"thinking_effort": "standard"},
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_reasoning_effort == "standard"


def test_attach_conversation_uses_hardened_nested_model_detection() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "assistant-1",
            "mapping": {
                "assistant-1": _message_node(
                    "assistant-1",
                    metadata={"selected_model": {"slug": "gpt-selected"}},
                ),
            },
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_model == "gpt-selected"


def test_attach_conversation_returns_none_when_model_is_unknown() -> None:
    client, _calls = _client_with_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "mapping": {},
        }
    )

    attached = client.attach_conversation(CONVERSATION_ID)

    assert attached.detected_model is None


def test_attach_conversation_rejects_invalid_reference() -> None:
    client, calls = _client_with_payload({"conversation_id": CONVERSATION_ID})

    with pytest.raises(ValueError, match="/c/<conversation_id>"):
        client.attach_conversation("https://chatgpt.com/g/g-example")

    assert calls == []


def test_attach_conversation_propagates_fetch_errors() -> None:
    client = object.__new__(adapter.ChatGPTWebClient)

    def get_conversation_payload(conversation_id: str) -> dict[str, Any]:
        raise adapter.RequestError(f"conversation status=404: {conversation_id}")

    client._get_conversation_payload = get_conversation_payload

    with pytest.raises(adapter.RequestError, match="status=404"):
        client.attach_conversation(CONVERSATION_ID)
