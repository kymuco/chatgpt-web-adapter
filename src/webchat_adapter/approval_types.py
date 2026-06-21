from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from .types import ChatConversation, ChatMetrics, ChatResponse, PendingApproval

ApprovalEventType = Literal[
    "approval_detected",
    "approval_allowed",
    "approval_denied",
    "approval_sent",
    "approval_completed",
    "approval_failed",
]
APPROVAL_EVENT_TYPES: tuple[ApprovalEventType, ...] = (
    "approval_detected",
    "approval_allowed",
    "approval_denied",
    "approval_sent",
    "approval_completed",
    "approval_failed",
)

ApprovalRoundStatus = Literal[
    "detected",
    "allowed",
    "denied",
    "sent",
    "completed",
    "failed",
]
APPROVAL_ROUND_STATUSES: tuple[ApprovalRoundStatus, ...] = (
    "detected",
    "allowed",
    "denied",
    "sent",
    "completed",
    "failed",
)

ApprovalResultStatus = Literal[
    "completed",
    "approval_required",
    "denied",
    "failed",
]
APPROVAL_RESULT_STATUSES: tuple[ApprovalResultStatus, ...] = (
    "completed",
    "approval_required",
    "denied",
    "failed",
)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{field_name} must be an integer") from error
    if result <= 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, field_name)


def _metadata_preview(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("metadata_preview must be a dict")
    return copy.deepcopy(value)


def _chat_metrics_to_dict(metrics: ChatMetrics) -> dict[str, Any]:
    payload = {
        "first_token": metrics.first_token,
        "last_token": metrics.last_token,
        "total": metrics.total,
    }
    to_dict = getattr(metrics, "to_dict", None)
    if not callable(to_dict):
        return payload
    expanded_payload = to_dict()
    if not isinstance(expanded_payload, dict):
        return payload
    for key in (
        "requirements_latency",
        "stream_duration",
        "chars_per_second",
        "backend_status",
    ):
        value = expanded_payload.get(key)
        if value is not None:
            payload[key] = copy.deepcopy(value)
    return payload


def _chat_response_to_dict(response: ChatResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {
        "text": response.text,
        "title": response.title,
        "conversation": response.conversation.to_dict(),
        "metrics": _chat_metrics_to_dict(response.metrics),
    }


def _chat_response_from_dict(payload: Any) -> ChatResponse | None:
    if not isinstance(payload, dict):
        return None
    metrics = payload.get("metrics")
    return ChatResponse(
        text="" if payload.get("text") is None else str(payload.get("text")),
        title=_optional_str(payload.get("title")),
        conversation=ChatConversation.from_dict(payload.get("conversation")),
        metrics=ChatMetrics.from_dict(metrics if isinstance(metrics, dict) else None),
    )


@dataclass
class ApprovalEvent:
    type: ApprovalEventType
    conversation_id: str | None = None
    round_index: int | None = None
    tool_message_id: str | None = None
    target_message_id: str | None = None
    recipient: str | None = None
    allowed: bool | None = None
    reason: str | None = None
    metadata_preview: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_type = _optional_str(self.type)
        if event_type not in APPROVAL_EVENT_TYPES:
            raise ValueError(f"unsupported approval event type: {self.type!r}")
        self.type = event_type
        self.conversation_id = _optional_str(self.conversation_id)
        self.round_index = _optional_positive_int(self.round_index, "round_index")
        self.tool_message_id = _optional_str(self.tool_message_id)
        self.target_message_id = _optional_str(self.target_message_id)
        self.recipient = _optional_str(self.recipient)
        if self.allowed is not None and not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool or None")
        self.reason = _optional_str(self.reason)
        self.metadata_preview = _metadata_preview(self.metadata_preview)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ApprovalEvent":
        if not isinstance(payload, dict):
            raise TypeError("approval event payload must be a dict")
        return cls(
            type=payload.get("type"),
            conversation_id=payload.get("conversation_id"),
            round_index=payload.get("round_index"),
            tool_message_id=payload.get("tool_message_id"),
            target_message_id=payload.get("target_message_id"),
            recipient=payload.get("recipient"),
            allowed=payload.get("allowed"),
            reason=payload.get("reason"),
            metadata_preview=payload.get("metadata_preview"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "conversation_id": self.conversation_id,
            "round_index": self.round_index,
            "tool_message_id": self.tool_message_id,
            "target_message_id": self.target_message_id,
            "recipient": self.recipient,
            "allowed": self.allowed,
            "reason": self.reason,
            "metadata_preview": copy.deepcopy(self.metadata_preview),
        }


@dataclass
class ApprovalRound:
    index: int
    approval: PendingApproval | None = None
    status: ApprovalRoundStatus = "detected"
    events: list[ApprovalEvent] = field(default_factory=list)
    error: str | None = None

    def __post_init__(self) -> None:
        self.index = _positive_int(self.index, "index")
        if self.approval is not None and not isinstance(self.approval, PendingApproval):
            raise TypeError("approval must be a PendingApproval or None")
        status = _optional_str(self.status)
        if status not in APPROVAL_ROUND_STATUSES:
            raise ValueError(f"unsupported approval round status: {self.status!r}")
        self.status = status
        events = []
        for event in self.events or []:
            if not isinstance(event, ApprovalEvent):
                raise TypeError("events must contain ApprovalEvent items")
            events.append(event)
        self.events = events
        self.error = _optional_str(self.error)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ApprovalRound":
        if not isinstance(payload, dict):
            raise TypeError("approval round payload must be a dict")
        events_payload = payload.get("events")
        events = []
        if isinstance(events_payload, list):
            events = [ApprovalEvent.from_dict(event) for event in events_payload]
        return cls(
            index=payload.get("index"),
            approval=PendingApproval.from_dict(payload.get("approval")),
            status=payload.get("status", "detected"),
            events=events,
            error=payload.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "approval": self.approval.to_dict() if self.approval is not None else None,
            "status": self.status,
            "events": [event.to_dict() for event in self.events],
            "error": self.error,
        }


@dataclass
class ApprovalResult:
    status: ApprovalResultStatus = "completed"
    rounds: list[ApprovalRound] = field(default_factory=list)
    events: list[ApprovalEvent] = field(default_factory=list)
    response: ChatResponse | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        status = _optional_str(self.status)
        if status not in APPROVAL_RESULT_STATUSES:
            raise ValueError(f"unsupported approval result status: {self.status!r}")
        self.status = status

        rounds = []
        for round_item in self.rounds or []:
            if not isinstance(round_item, ApprovalRound):
                raise TypeError("rounds must contain ApprovalRound items")
            rounds.append(round_item)
        self.rounds = rounds

        events = []
        for event in self.events or []:
            if not isinstance(event, ApprovalEvent):
                raise TypeError("events must contain ApprovalEvent items")
            events.append(event)
        self.events = events

        if self.response is not None and not isinstance(self.response, ChatResponse):
            raise TypeError("response must be a ChatResponse or None")
        self.error = _optional_str(self.error)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ApprovalResult":
        if not isinstance(payload, dict):
            raise TypeError("approval result payload must be a dict")
        rounds_payload = payload.get("rounds")
        events_payload = payload.get("events")
        rounds = []
        events = []
        if isinstance(rounds_payload, list):
            rounds = [ApprovalRound.from_dict(round_item) for round_item in rounds_payload]
        if isinstance(events_payload, list):
            events = [ApprovalEvent.from_dict(event) for event in events_payload]
        return cls(
            status=payload.get("status", "completed"),
            rounds=rounds,
            events=events,
            response=_chat_response_from_dict(payload.get("response")),
            error=payload.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rounds": [round_item.to_dict() for round_item in self.rounds],
            "events": [event.to_dict() for event in self.events],
            "response": _chat_response_to_dict(self.response),
            "error": self.error,
        }
