from __future__ import annotations

from typing import Any, Callable, Sequence

from .approval_policy import ApprovalPolicy
from .types import ChatConversation, ChatResponse, MediaItem, PendingApproval


class ApprovalDeniedError(RuntimeError):
    """Raised when an approval policy blocks an approval action."""

    def __init__(self, *, approval: PendingApproval, decision: Any) -> None:
        self.approval = approval
        self.decision = decision
        super().__init__(
            f"approval blocked for recipient {approval.recipient!r}: "
            f"{getattr(decision, 'reason', None)}"
        )


def _resolve_policy(policy: ApprovalPolicy | None) -> ApprovalPolicy:
    if policy is None:
        return ApprovalPolicy()
    if not isinstance(policy, ApprovalPolicy):
        raise TypeError("policy must be an ApprovalPolicy or None")
    return policy


def _approval(tool_id: str, target_message_id: str, recipient: str) -> PendingApproval:
    return PendingApproval(
        tool_message_id=tool_id,
        target_message_id=target_message_id,
        recipient=recipient,
    )


def approve_pending_action(original: Callable[..., ChatResponse]) -> Callable[..., ChatResponse]:
    def wrapper(
        self: Any,
        conversation: ChatConversation | dict[str, Any],
        *,
        policy: ApprovalPolicy | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        approval_policy = _resolve_policy(policy)
        original_finder = self._latest_confirm_action_leaf

        def guarded_finder(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
            tool_id, target_message_id, recipient = original_finder(payload)
            if not (tool_id and target_message_id and recipient):
                return tool_id, target_message_id, recipient
            pending_approval = _approval(tool_id, target_message_id, recipient)
            decision = approval_policy.evaluate(pending_approval)
            event_payload = {
                "pending_tool_id": tool_id,
                "target_message_id": target_message_id,
                "recipient": recipient,
                "approval": pending_approval.to_dict(),
                "decision": decision.to_dict(),
            }
            if not decision.allowed:
                self._emit_event(on_event, "approval_policy_denied", **event_payload)
                raise ApprovalDeniedError(
                    approval=pending_approval,
                    decision=decision,
                )
            self._emit_event(on_event, "approval_policy_allowed", **event_payload)
            return tool_id, target_message_id, recipient

        self._latest_confirm_action_leaf = guarded_finder
        try:
            return original(self, conversation, on_event=on_event, **kwargs)
        finally:
            self._latest_confirm_action_leaf = original_finder

    return wrapper


def wait_and_approve_pending_actions(
    original: Callable[..., ChatResponse]
) -> Callable[..., ChatResponse]:
    def wrapper(
        self: Any,
        conversation: ChatConversation | dict[str, Any],
        *,
        policy: ApprovalPolicy | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return original(self, conversation, policy=_resolve_policy(policy), **kwargs)

    return wrapper


def send_and_auto_approve(original: Callable[..., ChatResponse]) -> Callable[..., ChatResponse]:
    def wrapper(
        self: Any,
        prompt: str,
        *,
        policy: ApprovalPolicy | None = None,
        media: Sequence[MediaItem] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return original(
            self,
            prompt,
            policy=_resolve_policy(policy),
            media=media,
            **kwargs,
        )

    return wrapper
