from __future__ import annotations

import pytest

import webchat_adapter as adapter


CONVERSATION_ID = "conv-123"


def test_attached_conversation_exposes_conversation_id() -> None:
    attached = adapter.AttachedConversation(
        conversation=adapter.ChatConversation(conversation_id=f"  {CONVERSATION_ID}  "),
        current_node=" node-123 ",
        detected_model=" gpt-5-5-thinking ",
        title=" Test title ",
        raw_status={"async_status": None},
    )

    assert attached.conversation_id == CONVERSATION_ID
    assert attached.conversation.conversation_id == CONVERSATION_ID
    assert attached.current_node == "node-123"
    assert attached.detected_model == "gpt-5-5-thinking"
    assert attached.title == "Test title"
    assert attached.raw_status == {"async_status": None}


def test_attached_conversation_from_payload_extracts_lightweight_fields() -> None:
    attached = adapter.AttachedConversation.from_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "node-current",
            "title": "Existing chat",
            "async_status": "running",
            "update_time": 123.0,
            "mapping": {"large": "payload should not be copied into raw_status"},
        }
    )

    assert attached.conversation_id == CONVERSATION_ID
    assert attached.conversation.conversation_id == CONVERSATION_ID
    assert attached.current_node == "node-current"
    assert attached.title == "Existing chat"
    assert attached.detected_model is None
    assert attached.raw_status == {
        "async_status": "running",
        "update_time": 123.0,
    }


def test_attached_conversation_from_payload_preserves_supplied_conversation_state() -> None:
    attached = adapter.AttachedConversation.from_payload(
        {
            "conversation_id": CONVERSATION_ID,
            "current_node": "node-current",
            "title": "Payload title",
        },
        conversation=adapter.ChatConversation(
            conversation_id=CONVERSATION_ID,
            message_id="message-123",
            parent_message_id="parent-123",
        ),
        detected_model="gpt-5-5-thinking",
        title="Explicit title",
        raw_status={"source": "summary"},
    )

    assert attached.conversation_id == CONVERSATION_ID
    assert attached.conversation.message_id == "message-123"
    assert attached.conversation.parent_message_id == "parent-123"
    assert attached.detected_model == "gpt-5-5-thinking"
    assert attached.title == "Explicit title"
    assert attached.raw_status == {"source": "summary"}


def test_attached_conversation_from_payload_fills_missing_conversation_id() -> None:
    attached = adapter.AttachedConversation.from_payload(
        {"conversation_id": CONVERSATION_ID},
        conversation=adapter.ChatConversation(message_id="message-123"),
    )

    assert attached.conversation_id == CONVERSATION_ID
    assert attached.conversation.message_id == "message-123"


def test_attached_conversation_copies_raw_status() -> None:
    raw_status = {"async_status": "running"}

    attached = adapter.AttachedConversation(
        conversation=adapter.ChatConversation(conversation_id=CONVERSATION_ID),
        raw_status=raw_status,
    )
    raw_status["async_status"] = "changed"

    assert attached.raw_status == {"async_status": "running"}


def test_attached_conversation_to_dict_includes_convenience_conversation_id() -> None:
    attached = adapter.AttachedConversation(
        conversation=adapter.ChatConversation(
            conversation_id=CONVERSATION_ID,
            message_id="message-123",
        ),
        current_node="node-current",
        detected_model="gpt-5-5-thinking",
        title="Existing chat",
        raw_status={"async_status": None},
    )

    assert attached.to_dict() == {
        "conversation": {
            "conversation_id": CONVERSATION_ID,
            "message_id": "message-123",
            "user_id": None,
            "finish_reason": None,
            "parent_message_id": None,
            "is_thinking": False,
        },
        "conversation_id": CONVERSATION_ID,
        "current_node": "node-current",
        "detected_model": "gpt-5-5-thinking",
        "title": "Existing chat",
        "raw_status": {"async_status": None},
    }


def test_attached_conversation_rejects_missing_conversation_id() -> None:
    with pytest.raises(ValueError, match="conversation.conversation_id is required"):
        adapter.AttachedConversation(conversation=adapter.ChatConversation())


def test_attached_conversation_rejects_non_conversation() -> None:
    with pytest.raises(TypeError, match="ChatConversation"):
        adapter.AttachedConversation(conversation={"conversation_id": CONVERSATION_ID})  # type: ignore[arg-type]


def test_attached_conversation_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="payload"):
        adapter.AttachedConversation.from_payload(None)  # type: ignore[arg-type]


def test_attached_conversation_rejects_non_dict_raw_status() -> None:
    with pytest.raises(TypeError, match="raw_status"):
        adapter.AttachedConversation(
            conversation=adapter.ChatConversation(conversation_id=CONVERSATION_ID),
            raw_status="running",  # type: ignore[arg-type]
        )


def test_attached_conversation_is_exported_from_public_api() -> None:
    assert "AttachedConversation" in adapter.__all__
    assert adapter.AttachedConversation(
        conversation=adapter.ChatConversation(conversation_id=CONVERSATION_ID)
    ).conversation_id == CONVERSATION_ID
