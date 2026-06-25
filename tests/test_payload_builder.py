from __future__ import annotations

import pytest

import chatgpt_web_adapter
from chatgpt_web_adapter import ChatConversation, PayloadBuilder


def test_text_message_builds_web_text_message_shape() -> None:
    message = PayloadBuilder.text_message(
        "hello",
        message_id="msg-1",
        create_time=123.0,
    )

    assert message == {
        "id": "msg-1",
        "author": {"role": "user"},
        "content": {"content_type": "text", "parts": ["hello"]},
        "metadata": {
            "serialization_metadata": {"custom_symbol_offsets": []},
        },
        "create_time": 123.0,
    }


def test_text_message_uses_explicit_role_message_id_and_create_time() -> None:
    message = PayloadBuilder.text_message(
        "system prompt",
        role="system",
        message_id="system-msg",
        create_time=42,
    )

    assert message["author"] == {"role": "system"}
    assert message["id"] == "system-msg"
    assert message["create_time"] == 42.0


def test_text_message_generates_message_id_and_create_time() -> None:
    message = PayloadBuilder.text_message("hello")

    assert isinstance(message["id"], str)
    assert message["id"]
    assert isinstance(message["create_time"], float)


def test_text_message_rejects_empty_role() -> None:
    with pytest.raises(ValueError, match="role must not be empty"):
        PayloadBuilder.text_message("hello", role="  ")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (123, "123"),
        ("hello", "hello"),
    ],
)
def test_text_message_converts_text_to_string(value: object, expected: str) -> None:
    message = PayloadBuilder.text_message(value)

    assert message["content"]["parts"] == [expected]


def test_text_message_deep_copies_metadata() -> None:
    metadata = {"nested": {"value": 1}}
    message = PayloadBuilder.text_message("hello", metadata=metadata)

    metadata["nested"]["value"] = 2

    assert message["metadata"]["nested"] == {"value": 1}


def test_text_message_preserves_serialization_metadata_default() -> None:
    message = PayloadBuilder.text_message("hello", metadata={"foo": "bar"})

    assert message["metadata"] == {
        "serialization_metadata": {"custom_symbol_offsets": []},
        "foo": "bar",
    }


def test_text_message_merges_serialization_metadata() -> None:
    message = PayloadBuilder.text_message(
        "hello",
        metadata={"serialization_metadata": {"extra": True}},
    )

    assert message["metadata"] == {
        "serialization_metadata": {
            "custom_symbol_offsets": [],
            "extra": True,
        },
    }


def test_text_message_rejects_invalid_metadata() -> None:
    with pytest.raises(TypeError, match="metadata must be a dict or None"):
        PayloadBuilder.text_message("hello", metadata="bad")
    with pytest.raises(TypeError, match="metadata.serialization_metadata must be a dict"):
        PayloadBuilder.text_message(
            "hello",
            metadata={"serialization_metadata": "bad"},
        )


def test_new_chat_builds_minimal_payload() -> None:
    payload = PayloadBuilder.new_chat(
        "hello",
        model="gpt-5-3-mini",
        parent_message_id="parent-1",
    )

    assert payload["action"] == "next"
    assert payload["parent_message_id"] == "parent-1"
    assert payload["model"] == "gpt-5-3-mini"
    assert payload["conversation_mode"] == {"kind": "primary_assistant"}
    assert payload["enable_message_followups"] is False
    assert payload["supports_buffering"] is True
    assert payload["supported_encodings"] == ["v1"]
    assert "conversation_id" not in payload
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["author"] == {"role": "user"}
    assert payload["messages"][0]["content"]["parts"] == ["hello"]


def test_new_chat_generates_parent_message_id() -> None:
    payload = PayloadBuilder.new_chat("hello")

    assert isinstance(payload["parent_message_id"], str)
    assert payload["parent_message_id"]


def test_new_chat_adds_system_message_before_user_message() -> None:
    payload = PayloadBuilder.new_chat(
        "hello",
        system="You are concise",
        parent_message_id="parent-1",
    )

    assert [message["author"]["role"] for message in payload["messages"]] == [
        "system",
        "user",
    ]
    assert payload["messages"][0]["content"]["parts"] == ["You are concise"]
    assert payload["messages"][1]["content"]["parts"] == ["hello"]


def test_new_chat_web_search_adds_system_hints() -> None:
    payload = PayloadBuilder.new_chat(
        "search",
        web_search=True,
        parent_message_id="parent-1",
    )

    assert payload["system_hints"] == ["search"]
    assert payload["messages"][-1]["metadata"]["system_hints"] == ["search"]


def test_new_chat_temporary_sets_history_disabled() -> None:
    payload = PayloadBuilder.new_chat(
        "private",
        temporary=True,
        parent_message_id="parent-1",
    )

    assert payload["history_and_training_disabled"] is True


@pytest.mark.parametrize("reasoning_effort", ["standard", "extended"])
def test_new_chat_reasoning_effort(reasoning_effort: str) -> None:
    payload = PayloadBuilder.new_chat(
        "think",
        reasoning_effort=reasoning_effort,
        parent_message_id="parent-1",
    )

    assert payload["thinking_effort"] == reasoning_effort


def test_new_chat_instant_mode_omits_thinking_effort_and_uses_instant_model() -> None:
    payload = PayloadBuilder.new_chat(
        "think",
        reasoning_effort="instant",
        parent_message_id="parent-1",
    )

    assert payload["model"] == "gpt-5-3-mini"
    assert "thinking_effort" not in payload
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["author"] == {"role": "user"}


@pytest.mark.parametrize(
    ("reasoning_effort", "expected_model", "expected_effort"),
    [
        ("medium", "gpt-5-5-thinking", "standard"),
        ("high", "gpt-5-5-thinking", "extended"),
    ],
)
def test_new_chat_ui_reasoning_modes_map_to_current_backend_values(
    reasoning_effort: str,
    expected_model: str,
    expected_effort: str,
) -> None:
    payload = PayloadBuilder.new_chat(
        "think",
        reasoning_effort=reasoning_effort,
        parent_message_id="parent-1",
    )

    assert payload["model"] == expected_model
    assert payload["thinking_effort"] == expected_effort


@pytest.mark.parametrize("reasoning_effort", [None, "", "off", "none", "-"])
def test_new_chat_reasoning_effort_off_omits_field(reasoning_effort: str | None) -> None:
    payload = PayloadBuilder.new_chat(
        "think",
        reasoning_effort=reasoning_effort,
        parent_message_id="parent-1",
    )

    assert "thinking_effort" not in payload


def test_new_chat_invalid_reasoning_effort_raises() -> None:
    with pytest.raises(ValueError, match="reasoning_effort must be one of"):
        PayloadBuilder.new_chat("hello", reasoning_effort="maximum")


def test_new_chat_rejects_invalid_model() -> None:
    with pytest.raises(ValueError, match="model must not be empty"):
        PayloadBuilder.new_chat("hello", model=" ")


def test_continue_chat_builds_payload_from_chat_conversation() -> None:
    conversation = ChatConversation(
        conversation_id="conv-1",
        message_id="msg-1",
    )

    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation=conversation,
    )

    assert payload["conversation_id"] == "conv-1"
    assert payload["parent_message_id"] == "msg-1"
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["content"]["parts"] == ["continue"]


def test_continue_chat_builds_payload_from_dict_conversation() -> None:
    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation={"conversation_id": "conv-1", "message_id": "msg-1"},
    )

    assert payload["conversation_id"] == "conv-1"
    assert payload["parent_message_id"] == "msg-1"


def test_continue_chat_explicit_conversation_id_wins() -> None:
    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation={"conversation_id": "old", "message_id": "msg-1"},
        conversation_id="new",
    )

    assert payload["conversation_id"] == "new"


def test_continue_chat_explicit_parent_message_id_wins() -> None:
    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation={"conversation_id": "conv-1", "parent_message_id": "old", "message_id": "msg"},
        parent_message_id="explicit-parent",
    )

    assert payload["parent_message_id"] == "explicit-parent"


def test_continue_chat_uses_parent_message_id_before_message_id() -> None:
    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation={
            "conversation_id": "conv-1",
            "parent_message_id": "parent-msg",
            "message_id": "msg",
        },
    )

    assert payload["parent_message_id"] == "parent-msg"


def test_continue_chat_requires_conversation_id() -> None:
    with pytest.raises(ValueError, match="conversation_id is required"):
        PayloadBuilder.continue_chat(
            "continue",
            conversation={"message_id": "msg-1"},
        )


def test_continue_chat_requires_parent_message_id() -> None:
    with pytest.raises(ValueError, match="parent_message_id is required"):
        PayloadBuilder.continue_chat(
            "continue",
            conversation={"conversation_id": "conv-1"},
        )


def test_continue_chat_does_not_include_system_message() -> None:
    payload = PayloadBuilder.continue_chat(
        "continue",
        conversation={"conversation_id": "conv-1", "message_id": "msg-1"},
    )

    assert [message["author"]["role"] for message in payload["messages"]] == ["user"]


def test_continue_chat_web_search_adds_system_hints() -> None:
    payload = PayloadBuilder.continue_chat(
        "search",
        conversation={"conversation_id": "conv-1", "message_id": "msg-1"},
        web_search=True,
    )

    assert payload["system_hints"] == ["search"]
    assert payload["messages"][0]["metadata"]["system_hints"] == ["search"]


def test_continue_chat_does_not_mutate_input_conversation() -> None:
    conversation = {"conversation_id": "conv-1", "message_id": "msg-1"}

    PayloadBuilder.continue_chat("continue", conversation=conversation)

    assert conversation == {"conversation_id": "conv-1", "message_id": "msg-1"}


def test_payload_builder_is_exported_from_public_package() -> None:
    assert chatgpt_web_adapter.PayloadBuilder is PayloadBuilder
    assert "PayloadBuilder" in chatgpt_web_adapter.__all__
