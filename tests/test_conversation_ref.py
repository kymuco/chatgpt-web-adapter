from __future__ import annotations

import pytest

import webchat_adapter as adapter


CONVERSATION_ID = "conv-123"


def test_conversation_ref_accepts_raw_id() -> None:
    ref = adapter.ConversationRef.from_any(f"  {CONVERSATION_ID}  ")

    assert ref == adapter.ConversationRef(CONVERSATION_ID)
    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_chatgpt_url() -> None:
    ref = adapter.ConversationRef.from_any(f"https://chatgpt.com/c/{CONVERSATION_ID}")

    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_chatgpt_url_with_query_and_fragment() -> None:
    ref = adapter.ConversationRef.from_any(
        f"https://chatgpt.com/c/{CONVERSATION_ID}?model=gpt-5#message"
    )

    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_legacy_chat_openai_url() -> None:
    ref = adapter.ConversationRef.from_any(f"https://chat.openai.com/c/{CONVERSATION_ID}/")

    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_chat_conversation() -> None:
    conversation = adapter.ChatConversation(
        conversation_id=CONVERSATION_ID,
        message_id="message-123",
    )

    ref = adapter.ConversationRef.from_any(conversation)

    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_dict_with_conversation_id() -> None:
    ref = adapter.ConversationRef.from_any(
        {
            "conversation_id": CONVERSATION_ID,
            "message_id": "message-123",
        }
    )

    assert ref.conversation_id == CONVERSATION_ID


def test_conversation_ref_accepts_existing_ref() -> None:
    existing = adapter.ConversationRef(CONVERSATION_ID)

    assert adapter.ConversationRef.from_any(existing) is existing


def test_conversation_ref_rejects_empty_raw_id() -> None:
    with pytest.raises(ValueError, match="conversation_id is required"):
        adapter.ConversationRef.from_any("  ")


def test_conversation_ref_rejects_raw_url_like_id() -> None:
    with pytest.raises(ValueError, match="raw id"):
        adapter.ConversationRef("https://chatgpt.com/c/conv-123")


def test_conversation_ref_rejects_non_conversation_url() -> None:
    with pytest.raises(ValueError, match="/c/<conversation_id>"):
        adapter.ConversationRef.from_any("https://chatgpt.com/g/g-example")


def test_conversation_ref_rejects_unsupported_url_host() -> None:
    with pytest.raises(ValueError, match="host"):
        adapter.ConversationRef.from_any("https://example.com/c/conv-123")


def test_conversation_ref_rejects_missing_dict_conversation_id() -> None:
    with pytest.raises(ValueError, match="conversation_id is required"):
        adapter.ConversationRef.from_any({"id": CONVERSATION_ID})


def test_conversation_ref_rejects_empty_chat_conversation() -> None:
    with pytest.raises(ValueError, match="conversation.conversation_id is required"):
        adapter.ConversationRef.from_any(adapter.ChatConversation())


def test_conversation_ref_rejects_unsupported_input_type() -> None:
    with pytest.raises(TypeError, match="conversation reference"):
        adapter.ConversationRef.from_any(None)  # type: ignore[arg-type]


def test_conversation_ref_is_exported_from_public_api() -> None:
    assert "ConversationRef" in adapter.__all__
    assert adapter.ConversationRef(CONVERSATION_ID).conversation_id == CONVERSATION_ID
