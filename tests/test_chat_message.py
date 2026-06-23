from __future__ import annotations

import pytest

from chatgpt_web_adapter import ChatMessage


def test_chat_message_basic_construction() -> None:
    message = ChatMessage(
        node_id="node-1",
        message_id="msg-1",
        role="assistant",
        text="Hello",
        create_time=123.4,
        recipient="all",
        model="gpt-5-5-thinking",
        finish_reason="stop",
        metadata_preview={"content_type": "text"},
    )

    assert message.node_id == "node-1"
    assert message.message_id == "msg-1"
    assert message.role == "assistant"
    assert message.text == "Hello"
    assert message.create_time == 123.4
    assert message.recipient == "all"
    assert message.model == "gpt-5-5-thinking"
    assert message.finish_reason == "stop"
    assert message.metadata_preview == {"content_type": "text"}


def test_chat_message_strips_optional_strings() -> None:
    message = ChatMessage(
        node_id=" node-1 ",
        message_id=" msg-1 ",
        role=" assistant ",
        recipient=" all ",
        model=" gpt-4.1 ",
        finish_reason=" stop ",
    )

    assert message.node_id == "node-1"
    assert message.message_id == "msg-1"
    assert message.role == "assistant"
    assert message.recipient == "all"
    assert message.model == "gpt-4.1"
    assert message.finish_reason == "stop"


def test_chat_message_empty_optional_strings_become_none() -> None:
    message = ChatMessage(
        node_id=" ",
        message_id="",
        role="   ",
        recipient="",
        model=" ",
        finish_reason="",
    )

    assert message.node_id is None
    assert message.message_id is None
    assert message.role is None
    assert message.recipient is None
    assert message.model is None
    assert message.finish_reason is None


def test_chat_message_text_defaults_to_empty_string() -> None:
    assert ChatMessage().text == ""


def test_chat_message_non_string_text_is_coerced_safely() -> None:
    assert ChatMessage(text=123).text == "123"
    assert ChatMessage(text=None).text == ""


def test_chat_message_create_time_coerces_to_float() -> None:
    assert ChatMessage(create_time="123.5").create_time == 123.5


def test_chat_message_invalid_create_time_becomes_none() -> None:
    assert ChatMessage(create_time="bad").create_time is None


def test_chat_message_metadata_preview_copies_dict() -> None:
    metadata = {"content_type": "text"}

    message = ChatMessage(metadata_preview=metadata)
    metadata["content_type"] = "changed"

    assert message.metadata_preview == {"content_type": "text"}


def test_chat_message_metadata_preview_deep_copies_nested_values() -> None:
    metadata = {
        "finish_details": {"type": "stop"},
        "attachments": [{"name": "image.png"}],
    }

    message = ChatMessage(metadata_preview=metadata)
    metadata["finish_details"]["type"] = "changed"
    metadata["attachments"][0]["name"] = "changed.png"

    assert message.metadata_preview == {
        "finish_details": {"type": "stop"},
        "attachments": [{"name": "image.png"}],
    }


def test_chat_message_invalid_metadata_preview_raises_type_error() -> None:
    with pytest.raises(TypeError, match="metadata_preview must be a dict"):
        ChatMessage(metadata_preview=["bad"])


def test_chat_message_to_dict_returns_copied_metadata_preview() -> None:
    message = ChatMessage(metadata_preview={"content_type": "text"})

    payload = message.to_dict()
    payload["metadata_preview"]["content_type"] = "changed"

    assert message.metadata_preview == {"content_type": "text"}


def test_chat_message_to_dict_deep_copies_nested_metadata_preview() -> None:
    message = ChatMessage(
        metadata_preview={
            "finish_details": {"type": "stop"},
            "attachments": [{"name": "image.png"}],
        }
    )

    payload = message.to_dict()
    payload["metadata_preview"]["finish_details"]["type"] = "changed"
    payload["metadata_preview"]["attachments"][0]["name"] = "changed.png"

    assert message.metadata_preview == {
        "finish_details": {"type": "stop"},
        "attachments": [{"name": "image.png"}],
    }


def test_chat_message_from_dict_roundtrip() -> None:
    original = ChatMessage(
        node_id="node-1",
        message_id="msg-1",
        role="assistant",
        text="Hello",
        create_time=123.4,
        recipient="all",
        model="gpt-5-5-thinking",
        finish_reason="stop",
        metadata_preview={"content_type": "text"},
    )

    restored = ChatMessage.from_dict(original.to_dict())

    assert restored == original


def test_chat_message_from_dict_non_dict_returns_empty_message() -> None:
    assert ChatMessage.from_dict(None) == ChatMessage()
