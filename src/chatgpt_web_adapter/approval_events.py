from __future__ import annotations

from typing import Any, Callable

from .approval_policy import ApprovalDecision
from .approval_types import ApprovalEvent, ApprovalEventType
from .types import PendingApproval


def make_approval_event(
    event_type: ApprovalEventType,
    *,
    conversation_id: str | None = None,
    round_index: int | None = None,
    approval: PendingApproval | None = None,
    decision: ApprovalDecision | None = None,
    message_id: str | None = None,
    error: str | None = None,
    metadata_preview: dict[str, Any] | None = None,
) -> ApprovalEvent:
    """Build a canonical approval event with a stable public payload shape."""

    metadata = dict(metadata_preview or {})
    if decision is not None:
        metadata["decision"] = decision.to_dict()
    if message_id is not None:
        metadata["message_id"] = message_id
    if error is not None:
        metadata["error"] = error

    return ApprovalEvent(
        type=event_type,
        conversation_id=conversation_id,
        round_index=round_index,
        tool_message_id=approval.tool_message_id if approval is not None else None,
        target_message_id=approval.target_message_id if approval is not None else None,
        recipient=approval.recipient if approval is not None else None,
        allowed=decision.allowed if decision is not None else None,
        reason=decision.reason if decision is not None else error,
        metadata_preview=metadata,
    )


def emit_approval_event(
    emit_event: Callable[..., None],
    on_event: Callable[[dict[str, Any]], None] | None,
    event: ApprovalEvent,
) -> None:
    """Emit an ApprovalEvent through the existing dict-based on_event callback."""

    payload = event.to_dict()
    event_type = payload.pop("type")
    emit_event(on_event, event_type, **payload)
