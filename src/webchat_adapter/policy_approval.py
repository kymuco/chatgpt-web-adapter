from __future__ import annotations

import time
from typing import Any, Callable, Sequence

from .approval_policy import ApprovalPolicy
from .exceptions import RequestError
from .types import ChatConversation, ChatMetrics, ChatResponse, MediaItem, PendingApproval


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


def _pending_approval(
    tool_message_id: str,
    target_message_id: str,
    recipient: str,
) -> PendingApproval:
    return PendingApproval(
        tool_message_id=tool_message_id,
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
            approval = _pending_approval(tool_id, target_message_id, recipient)
            decision = approval_policy.evaluate(approval)
            event_payload = {
                "pending_tool_id": tool_id,
                "target_message_id": target_message_id,
                "recipient": recipient,
                "approval": approval.to_dict(),
                "decision": decision.to_dict(),
            }
            if not decision.allowed:
                self._emit_event(on_event, "approval_policy_denied", **event_payload)
                raise ApprovalDeniedError(approval=approval, decision=decision)
            self._emit_event(on_event, "approval_policy_allowed", **event_payload)
            return tool_id, target_message_id, recipient

        self._latest_confirm_action_leaf = guarded_finder
        try:
            return original(self, conversation, on_event=on_event, **kwargs)
        finally:
            self._latest_confirm_action_leaf = original_finder

    return wrapper


def wait_and_approve_pending_actions(
    self: Any,
    conversation: ChatConversation | dict[str, Any],
    *,
    model: str = "gpt-4o-mini",
    reasoning_effort: str | None = "extended",
    poll_timeout: float = 90.0,
    poll_interval: float = 2.0,
    pending_poll_interval: float = 3.0,
    settle_delay: float = 2.0,
    max_rounds: int = 0,
    timezone: str | None = None,
    timezone_offset_min: int | None = None,
    verify: Callable[[ChatResponse], bool] | None = None,
    policy: ApprovalPolicy | None = None,
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> ChatResponse:
    approval_policy = _resolve_policy(policy)
    conversation_dict = self._conversation_to_dict(conversation)
    if not isinstance(conversation_dict, dict):
        raise ValueError("conversation is required")
    conversation_id = conversation_dict.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("conversation.conversation_id is required")

    last_response = ChatResponse(
        text="",
        conversation=ChatConversation.from_dict(conversation_dict),
        metrics=ChatMetrics(),
    )
    round_index = 0
    waiting_announced = False
    while True:
        payload = self._get_conversation_payload(conversation_id)
        tool_id, _target_message_id, _recipient = self._latest_confirm_action_leaf(payload)
        if tool_id:
            waiting_announced = False
            round_index += 1
            self._emit_event(
                on_event,
                "approval_round_started",
                conversation_id=conversation_id,
                round_index=round_index,
                pending_tool_id=tool_id,
            )
            last_response = self.approve_pending_action(
                ChatConversation.from_dict(conversation_dict),
                model=model,
                reasoning_effort=reasoning_effort,
                poll=True,
                poll_timeout=poll_timeout,
                poll_interval=poll_interval,
                timezone=timezone,
                timezone_offset_min=timezone_offset_min,
                policy=approval_policy,
                on_token=on_token,
                on_event=on_event,
            )
            conversation_dict = last_response.conversation.to_dict()
            conversation_id = str(last_response.conversation.conversation_id or conversation_id)
            self._emit_event(
                on_event,
                "approval_round_finished",
                conversation_id=conversation_id,
                round_index=round_index,
                message_id=last_response.conversation.message_id,
            )
            if max_rounds > 0 and round_index >= max_rounds:
                return last_response
            if settle_delay > 0:
                time.sleep(max(0.0, settle_delay))
            continue
        if max_rounds > 0 and round_index >= max_rounds:
            return last_response
        if self._is_conversation_idle(conversation_id, payload):
            final_response = self._build_response_from_conversation_payload(
                payload,
                fallback_conversation_id=conversation_id,
                fallback_user_id=conversation_dict.get("user_id"),
            )
            self._emit_event(
                on_event,
                "conversation_idle",
                conversation_id=conversation_id,
                round_index=round_index,
                message_id=final_response.conversation.message_id,
            )
            if verify is not None:
                verified = bool(verify(final_response))
                self._emit_event(
                    on_event,
                    "verification_completed",
                    conversation_id=conversation_id,
                    verified=verified,
                )
                if not verified:
                    raise RequestError("verification failed after workflow completion")
            return final_response
        if not waiting_announced:
            self._emit_event(
                on_event,
                "waiting_for_pending_approval",
                conversation_id=conversation_id,
                round_index=round_index,
            )
            waiting_announced = True
        time.sleep(max(0.5, pending_poll_interval))


def send_and_auto_approve(
    original: Callable[..., ChatResponse]
) -> Callable[..., ChatResponse]:
    def wrapper(
        self: Any,
        prompt: str,
        *,
        policy: ApprovalPolicy | None = None,
        media: Sequence[MediaItem] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        approval_policy = _resolve_policy(policy)
        original_wait = self.wait_and_approve_pending_actions

        def wait_with_policy(
            wait_conversation: ChatConversation | dict[str, Any],
            **wait_kwargs: Any,
        ) -> ChatResponse:
            return original_wait(
                wait_conversation,
                policy=approval_policy,
                **wait_kwargs,
            )

        self.wait_and_approve_pending_actions = wait_with_policy
        try:
            return original(self, prompt, media=media, **kwargs)
        finally:
            self.wait_and_approve_pending_actions = original_wait

    return wrapper
