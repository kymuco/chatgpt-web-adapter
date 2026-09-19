from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .canonical_conversation_snapshot import CanonicalConversationSnapshot
from .status import _status_from_payload

POST_DELEGATION_UNKNOWN = "UNKNOWN"
POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT = "SUBMITTED_TERMINAL_ASSISTANT"
POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE = "SUBMITTED_GENERATION_INCOMPLETE"


@dataclass(frozen=True)
class PostDelegationReconciliation:
    outcome: str
    canonical_read_performed: bool
    canonical_read_complete: bool
    conversation_id: str
    user_message_id: str
    user_turn_persisted: bool | None
    canonical_status: str | None = None
    canonical_current_message_id: str | None = None
    canonical_current_role: str | None = None
    terminal_assistant_message_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unknown(
    *,
    conversation_id: str,
    user_message_id: str,
    canonical_read_performed: bool,
    canonical_read_complete: bool,
    user_turn_persisted: bool | None,
    reason: str,
    canonical_status: str | None = None,
    canonical_current_message_id: str | None = None,
    canonical_current_role: str | None = None,
) -> PostDelegationReconciliation:
    return PostDelegationReconciliation(
        outcome=POST_DELEGATION_UNKNOWN,
        canonical_read_performed=canonical_read_performed,
        canonical_read_complete=canonical_read_complete,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        user_turn_persisted=user_turn_persisted,
        canonical_status=canonical_status,
        canonical_current_message_id=canonical_current_message_id,
        canonical_current_role=canonical_current_role,
        reason=reason,
    )


def reconcile_post_delegation_failure(
    client: Any,
    *,
    conversation_id: str,
    user_message_id: str,
) -> PostDelegationReconciliation:
    """Classify one already-delegated ordinary-turn failure without replay.

    The browser request-correlation layer must supply the exact product-generated
    user message id. This function performs at most one complete canonical
    conversation snapshot read and never submits, retries, navigates, or grants
    write authority.
    """

    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id is required")
    if not isinstance(user_message_id, str) or not user_message_id.strip():
        raise ValueError("user_message_id is required")
    conversation_id = conversation_id.strip()
    user_message_id = user_message_id.strip()

    reader = getattr(client, "get_conversation_snapshot", None)
    if not callable(reader):
        return _unknown(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            canonical_read_performed=False,
            canonical_read_complete=False,
            user_turn_persisted=None,
            reason="CANONICAL_SNAPSHOT_UNAVAILABLE",
        )

    try:
        snapshot = reader(conversation_id)
    except Exception as error:
        return _unknown(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            canonical_read_performed=True,
            canonical_read_complete=False,
            user_turn_persisted=None,
            reason=f"CANONICAL_SNAPSHOT_FAILED:{type(error).__name__}",
        )

    if not isinstance(snapshot, CanonicalConversationSnapshot):
        return _unknown(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            canonical_read_performed=True,
            canonical_read_complete=False,
            user_turn_persisted=None,
            reason="CANONICAL_SNAPSHOT_INVALID_TYPE",
        )
    if snapshot.conversation_id != conversation_id or snapshot.complete is not True:
        return _unknown(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            canonical_read_performed=True,
            canonical_read_complete=False,
            user_turn_persisted=None,
            reason="CANONICAL_SNAPSHOT_IDENTITY_OR_COMPLETENESS_UNPROVEN",
        )

    messages = list(snapshot.messages)
    user_index = next(
        (
            index
            for index, message in enumerate(messages)
            if message.message_id == user_message_id and message.role == "user"
        ),
        None,
    )
    payload = snapshot.to_canonical_payload()
    status = _status_from_payload(payload)
    if user_index is None:
        return _unknown(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            canonical_read_performed=True,
            canonical_read_complete=True,
            user_turn_persisted=False,
            canonical_status=status.status,
            canonical_current_message_id=status.message_id,
            canonical_current_role=status.role,
            reason="REQUEST_BOUND_USER_MESSAGE_NOT_PRESENT",
        )

    later_messages = messages[user_index + 1 :]
    terminal_assistant = next(
        (
            message
            for message in reversed(later_messages)
            if message.role == "assistant"
            and message.message_id == status.message_id
            and status.status == "completed"
        ),
        None,
    )
    if terminal_assistant is not None:
        return PostDelegationReconciliation(
            outcome=POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT,
            canonical_read_performed=True,
            canonical_read_complete=True,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            user_turn_persisted=True,
            canonical_status=status.status,
            canonical_current_message_id=status.message_id,
            canonical_current_role=status.role,
            terminal_assistant_message_id=terminal_assistant.message_id,
            reason="REQUEST_BOUND_USER_AND_TERMINAL_ASSISTANT_CANONICALLY_PRESENT",
        )

    if status.status in {"user_last_message", "running"}:
        return PostDelegationReconciliation(
            outcome=POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE,
            canonical_read_performed=True,
            canonical_read_complete=True,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            user_turn_persisted=True,
            canonical_status=status.status,
            canonical_current_message_id=status.message_id,
            canonical_current_role=status.role,
            reason="REQUEST_BOUND_USER_PRESENT_WITHOUT_TERMINAL_ASSISTANT",
        )

    return _unknown(
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        canonical_read_performed=True,
        canonical_read_complete=True,
        user_turn_persisted=True,
        canonical_status=status.status,
        canonical_current_message_id=status.message_id,
        canonical_current_role=status.role,
        reason="REQUEST_BOUND_USER_PRESENT_BUT_CANONICAL_STATE_NOT_CLASSIFIED",
    )


__all__ = [
    "POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE",
    "POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT",
    "POST_DELEGATION_UNKNOWN",
    "PostDelegationReconciliation",
    "reconcile_post_delegation_failure",
]
