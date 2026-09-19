from __future__ import annotations

from chatgpt_web_adapter.canonical_conversation_snapshot import (
    canonical_snapshot_from_payload,
)
from chatgpt_web_adapter.post_delegation_reconciliation import (
    POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE,
    POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT,
    POST_DELEGATION_UNKNOWN,
    reconcile_post_delegation_failure,
)


def _message(
    message_id: str,
    role: str,
    *,
    text: str,
    finish_reason: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if finish_reason is not None:
        metadata["finish_details"] = {"type": finish_reason}
    return {
        "id": message_id,
        "author": {"role": role},
        "content": {"content_type": "text", "parts": [text]},
        "metadata": metadata,
    }


def _snapshot_payload(*, include_terminal_assistant: bool) -> dict[str, object]:
    mapping: dict[str, object] = {
        "root": {
            "id": "root",
            "parent": None,
            "children": ["user-node"],
            "message": None,
        },
        "user-node": {
            "id": "user-node",
            "parent": "root",
            "children": ["assistant-node"] if include_terminal_assistant else [],
            "message": _message("user-1", "user", text="hello"),
        },
    }
    current_node = "user-node"
    if include_terminal_assistant:
        mapping["assistant-node"] = {
            "id": "assistant-node",
            "parent": "user-node",
            "children": [],
            "message": _message(
                "assistant-1",
                "assistant",
                text="done",
                finish_reason="stop",
            ),
        }
        current_node = "assistant-node"
    return {
        "conversation_id": "conversation-1",
        "current_node": current_node,
        "mapping": mapping,
    }


class _Client:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_conversation_snapshot(self, conversation: str):
        self.calls.append(conversation)
        return canonical_snapshot_from_payload(conversation, self.payload)


def test_reconciliation_classifies_persisted_user_without_assistant_as_incomplete() -> None:
    client = _Client(_snapshot_payload(include_terminal_assistant=False))

    result = reconcile_post_delegation_failure(
        client,
        conversation_id="conversation-1",
        user_message_id="user-1",
    )

    assert result.outcome == POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE
    assert result.canonical_read_performed is True
    assert result.canonical_read_complete is True
    assert result.user_turn_persisted is True
    assert result.canonical_status == "user_last_message"
    assert result.terminal_assistant_message_id is None
    assert client.calls == ["conversation-1"]


def test_reconciliation_classifies_terminal_assistant_from_same_snapshot() -> None:
    client = _Client(_snapshot_payload(include_terminal_assistant=True))

    result = reconcile_post_delegation_failure(
        client,
        conversation_id="conversation-1",
        user_message_id="user-1",
    )

    assert result.outcome == POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT
    assert result.user_turn_persisted is True
    assert result.canonical_status == "completed"
    assert result.terminal_assistant_message_id == "assistant-1"
    assert client.calls == ["conversation-1"]


def test_reconciliation_keeps_absent_request_bound_user_message_unknown() -> None:
    client = _Client(_snapshot_payload(include_terminal_assistant=False))

    result = reconcile_post_delegation_failure(
        client,
        conversation_id="conversation-1",
        user_message_id="different-user",
    )

    assert result.outcome == POST_DELEGATION_UNKNOWN
    assert result.canonical_read_complete is True
    assert result.user_turn_persisted is False
    assert result.reason == "REQUEST_BOUND_USER_MESSAGE_NOT_PRESENT"
    assert client.calls == ["conversation-1"]


def test_reconciliation_without_snapshot_surface_performs_no_read() -> None:
    result = reconcile_post_delegation_failure(
        object(),
        conversation_id="conversation-1",
        user_message_id="user-1",
    )

    assert result.outcome == POST_DELEGATION_UNKNOWN
    assert result.canonical_read_performed is False
    assert result.canonical_read_complete is False
    assert result.user_turn_persisted is None
    assert result.reason == "CANONICAL_SNAPSHOT_UNAVAILABLE"
