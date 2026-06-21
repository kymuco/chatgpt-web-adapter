from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from .types import PendingApproval

ApprovalDecisionReason = Literal[
    "recipient_allowed",
    "recipient_denied",
    "manual_required_for_unknown_recipient",
    "unknown_recipient_denied",
    "read_only_auto_approve_disabled",
    "read_only_auto_approved",
]
APPROVAL_DECISION_REASONS: tuple[ApprovalDecisionReason, ...] = (
    "recipient_allowed",
    "recipient_denied",
    "manual_required_for_unknown_recipient",
    "unknown_recipient_denied",
    "read_only_auto_approve_disabled",
    "read_only_auto_approved",
)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _required_recipient(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("recipient must be a string")
    recipient = value.strip()
    if not recipient:
        raise ValueError("recipient must not be empty")
    return recipient


def _normalize_recipients(value: Any, field_name: str) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be an iterable of strings")
    try:
        iterator = iter(value)
    except TypeError as error:
        raise TypeError(f"{field_name} must be an iterable of strings") from error

    recipients = []
    for recipient in iterator:
        try:
            recipients.append(_required_recipient(recipient))
        except (TypeError, ValueError) as error:
            raise type(error)(f"{field_name} contains invalid recipient: {error}") from error
    return frozenset(recipients)


def _metadata_preview(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("metadata_preview must be a dict")
    return copy.deepcopy(value)


@dataclass
class ApprovalDecision:
    allowed: bool
    reason: ApprovalDecisionReason
    recipient: str | None = None
    manual_required: bool = False
    metadata_preview: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        reason = _optional_str(self.reason)
        if reason not in APPROVAL_DECISION_REASONS:
            raise ValueError(f"unsupported approval decision reason: {self.reason!r}")
        self.reason = reason
        self.recipient = _optional_str(self.recipient)
        if not isinstance(self.manual_required, bool):
            raise TypeError("manual_required must be a bool")
        self.metadata_preview = _metadata_preview(self.metadata_preview)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ApprovalDecision":
        if not isinstance(payload, dict):
            raise TypeError("approval decision payload must be a dict")
        return cls(
            allowed=payload.get("allowed"),
            reason=payload.get("reason"),
            recipient=payload.get("recipient"),
            manual_required=payload.get("manual_required", False),
            metadata_preview=payload.get("metadata_preview"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "recipient": self.recipient,
            "manual_required": self.manual_required,
            "metadata_preview": copy.deepcopy(self.metadata_preview),
        }


@dataclass(frozen=True)
class ApprovalPolicy:
    allowed_recipients: frozenset[str] = field(default_factory=frozenset)
    denied_recipients: frozenset[str] = field(default_factory=frozenset)
    auto_approve_read_only: bool = False
    require_manual_for_unknown: bool = True

    def __post_init__(self) -> None:
        allowed_recipients = _normalize_recipients(
            self.allowed_recipients,
            "allowed_recipients",
        )
        denied_recipients = _normalize_recipients(
            self.denied_recipients,
            "denied_recipients",
        )
        overlap = allowed_recipients & denied_recipients
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"recipients cannot be both allowed and denied: {joined}")

        if not isinstance(self.auto_approve_read_only, bool):
            raise TypeError("auto_approve_read_only must be a bool")
        if not isinstance(self.require_manual_for_unknown, bool):
            raise TypeError("require_manual_for_unknown must be a bool")

        object.__setattr__(self, "allowed_recipients", allowed_recipients)
        object.__setattr__(self, "denied_recipients", denied_recipients)

    def evaluate(self, approval: PendingApproval) -> ApprovalDecision:
        if not isinstance(approval, PendingApproval):
            raise TypeError("approval must be a PendingApproval")

        recipient = approval.recipient
        if recipient in self.denied_recipients:
            return ApprovalDecision(
                allowed=False,
                reason="recipient_denied",
                recipient=recipient,
                manual_required=False,
            )

        if recipient in self.allowed_recipients:
            return ApprovalDecision(
                allowed=True,
                reason="recipient_allowed",
                recipient=recipient,
                manual_required=False,
            )

        if self.require_manual_for_unknown:
            return ApprovalDecision(
                allowed=False,
                reason="manual_required_for_unknown_recipient",
                recipient=recipient,
                manual_required=True,
            )

        return ApprovalDecision(
            allowed=False,
            reason="unknown_recipient_denied",
            recipient=recipient,
            manual_required=False,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ApprovalPolicy":
        if not isinstance(payload, dict):
            raise TypeError("approval policy payload must be a dict")
        return cls(
            allowed_recipients=payload.get("allowed_recipients"),
            denied_recipients=payload.get("denied_recipients"),
            auto_approve_read_only=payload.get("auto_approve_read_only", False),
            require_manual_for_unknown=payload.get("require_manual_for_unknown", True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_recipients": sorted(self.allowed_recipients),
            "denied_recipients": sorted(self.denied_recipients),
            "auto_approve_read_only": self.auto_approve_read_only,
            "require_manual_for_unknown": self.require_manual_for_unknown,
        }
