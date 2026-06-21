from __future__ import annotations

import pytest

import webchat_adapter
from webchat_adapter import ConversationStatus
from webchat_adapter.types import CONVERSATION_STATUS_VALUES


def test_conversation_status_defaults_to_unknown() -> None:
    status = ConversationStatus()

    assert status.status == "unknown"
    assert status.node_id is None
    assert status.message_id is None
    assert status.role is None
    assert status.recipient is None
    assert status.async_status is None
    assert status.finish_reason is None
    assert status.pending_approval is False
    assert status.metadata_preview == {}


def test_conversation_status_accepts_known_statuses() -> None:
    for value in CONVERSATION_STATUS_VALUES:
        assert ConversationStatus(status=value).status == value


def test_conversation_status_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="unsupported conversation status"):
        ConversationStatus(status="done")


def test_conversation_status_normalizes_optional_string_fields() -> None:
    status = ConversationStatus(
        status=" completed ",
        node_id=" node ",
        message_id=" msg ",
        role=" assistant ",
        recipient=" all ",
        async_status=" completed ",
        finish_reason=" stop ",
    )

    assert status.status == "completed"
    assert status.node_id == "node"
    assert status.message_id == "msg"
    assert status.role == "assistant"
    assert status.recipient == "all"
    assert status.async_status == "completed"
    assert status.finish_reason == "stop"


def test_conversation_status_non_string_optional_fields_become_none() -> None:
    status = ConversationStatus(
        node_id=123,
        message_id=[],
        role={},
        recipient=object(),
        async_status=False,
        finish_reason=0,
    )

    assert status.node_id is None
    assert status.message_id is None
    assert status.role is None
    assert status.recipient is None
    assert status.async_status is None
    assert status.finish_reason is None


def test_conversation_status_pending_approval_coerces_bool() -> None:
    assert ConversationStatus(pending_approval=1).pending_approval is True
    assert ConversationStatus(pending_approval=0).pending_approval is False


def test_conversation_status_metadata_preview_none_becomes_empty_dict() -> None:
    assert ConversationStatus(metadata_preview=None).metadata_preview == {}


def test_conversation_status_metadata_preview_non_dict_raises_type_error() -> None:
    with pytest.raises(TypeError, match="metadata_preview must be a dict"):
        ConversationStatus(metadata_preview=[])


def test_conversation_status_deep_copies_metadata_preview_on_construction() -> None:
    metadata = {"nested": {"value": 1}}

    status = ConversationStatus(metadata_preview=metadata)
    metadata["nested"]["value"] = 2

    assert status.metadata_preview["nested"]["value"] == 1


def test_conversation_status_to_dict_deep_copies_metadata_preview() -> None:
    status = ConversationStatus(metadata_preview={"nested": {"value": 1}})

    payload = status.to_dict()
    payload["metadata_preview"]["nested"]["value"] = 2

    assert status.metadata_preview["nested"]["value"] == 1


def test_conversation_status_to_dict_returns_stable_keys() -> None:
    status = ConversationStatus(
        status="completed",
        node_id="node-1",
        message_id="msg-1",
        role="assistant",
        recipient="all",
        async_status="completed",
        finish_reason="stop",
        pending_approval=True,
        metadata_preview={"finish_details": {"type": "stop"}},
    )

    assert status.to_dict() == {
        "status": "completed",
        "node_id": "node-1",
        "message_id": "msg-1",
        "role": "assistant",
        "recipient": "all",
        "async_status": "completed",
        "finish_reason": "stop",
        "pending_approval": True,
        "metadata_preview": {"finish_details": {"type": "stop"}},
    }


def test_conversation_status_from_dict_roundtrip() -> None:
    original = ConversationStatus(
        status="running",
        node_id="node-1",
        message_id="msg-1",
        role="assistant",
        recipient="python",
        async_status="in_progress",
        finish_reason=None,
        pending_approval=False,
        metadata_preview={"async_status": "in_progress"},
    )

    loaded = ConversationStatus.from_dict(original.to_dict())

    assert loaded == original


def test_conversation_status_from_dict_non_dict_returns_default() -> None:
    assert ConversationStatus.from_dict(None) == ConversationStatus()
    assert ConversationStatus.from_dict([]) == ConversationStatus()


def test_conversation_status_is_exported_from_public_package() -> None:
    assert webchat_adapter.ConversationStatus is ConversationStatus
    assert "ConversationStatus" in webchat_adapter.__all__
