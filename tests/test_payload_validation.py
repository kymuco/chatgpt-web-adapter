from __future__ import annotations

import copy

import pytest

import webchat_adapter
from webchat_adapter import PayloadBuilder, PayloadValidationError, validate_payload


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "action": "next",
        "parent_message_id": "parent-1",
        "model": "gpt-4o-mini",
        "messages": [{"id": "msg-1"}],
    }
    payload.update(overrides)
    return payload


def test_validate_payload_accepts_minimal_valid_payload() -> None:
    validate_payload(_valid_payload())


def test_validate_payload_accepts_conversation_id_when_non_empty() -> None:
    validate_payload(_valid_payload(conversation_id="conv-1"))


def test_validate_payload_accepts_null_conversation_id_for_new_chat_payloads() -> None:
    validate_payload(_valid_payload(conversation_id=None))


def test_validate_payload_accepts_payload_builder_new_chat() -> None:
    validate_payload(
        PayloadBuilder.new_chat(
            "hello",
            model="gpt-4o-mini",
            parent_message_id="parent-1",
        )
    )


def test_validate_payload_accepts_payload_builder_continue_chat() -> None:
    validate_payload(
        PayloadBuilder.continue_chat(
            "continue",
            conversation={"conversation_id": "conv-1", "message_id": "msg-1"},
            model="gpt-4o-mini",
        )
    )


def test_validate_payload_does_not_mutate_payload() -> None:
    payload = _valid_payload(messages=[{"nested": {"value": 1}}])
    original = copy.deepcopy(payload)

    validate_payload(payload)

    assert payload == original


def test_payload_validation_exports() -> None:
    assert webchat_adapter.PayloadValidationError is PayloadValidationError
    assert webchat_adapter.validate_payload is validate_payload
    assert "PayloadValidationError" in webchat_adapter.__all__
    assert "validate_payload" in webchat_adapter.__all__


def test_validate_payload_rejects_non_dict() -> None:
    with pytest.raises(PayloadValidationError, match="payload must be a dict"):
        validate_payload("bad")


@pytest.mark.parametrize("field_name", ["action", "parent_message_id", "model"])
def test_validate_payload_requires_top_level_string_fields(field_name: str) -> None:
    payload = _valid_payload()
    payload.pop(field_name)

    with pytest.raises(PayloadValidationError, match=f"{field_name} is required"):
        validate_payload(payload)


@pytest.mark.parametrize("field_name", ["action", "parent_message_id", "model"])
@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_validate_payload_rejects_invalid_top_level_string_fields(
    field_name: str,
    value: object,
) -> None:
    payload = _valid_payload(**{field_name: value})

    with pytest.raises(PayloadValidationError, match=f"{field_name} must be a non-empty string"):
        validate_payload(payload)


def test_validate_payload_requires_messages() -> None:
    payload = _valid_payload()
    payload.pop("messages")

    with pytest.raises(PayloadValidationError, match="messages is required"):
        validate_payload(payload)


@pytest.mark.parametrize("messages", ["bad", None, 123, {"id": "msg"}])
def test_validate_payload_rejects_non_list_messages(messages: object) -> None:
    with pytest.raises(PayloadValidationError, match="messages must be a list"):
        validate_payload(_valid_payload(messages=messages))


def test_validate_payload_rejects_empty_messages() -> None:
    with pytest.raises(PayloadValidationError, match="messages must not be empty"):
        validate_payload(_valid_payload(messages=[]))


@pytest.mark.parametrize("message", ["bad", None, 123, ["bad"]])
def test_validate_payload_rejects_non_dict_message_items(message: object) -> None:
    with pytest.raises(PayloadValidationError, match="messages\[0\] must be a dict"):
        validate_payload(_valid_payload(messages=[message]))


@pytest.mark.parametrize("conversation_id", ["", "   ", 123])
def test_validate_payload_rejects_invalid_conversation_id(conversation_id: object) -> None:
    with pytest.raises(
        PayloadValidationError,
        match="conversation_id must be None or a non-empty string when present",
    ):
        validate_payload(_valid_payload(conversation_id=conversation_id))
