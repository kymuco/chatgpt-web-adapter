from __future__ import annotations

import time
from typing import Any, Callable, Sequence

from .approval_events import emit_approval_event, make_approval_event
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
        _approval_round_index: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        if policy is None:
            return original(self, conversation, on_event=on_event, **kwargs)
        approval_policy = _resolve_policy(policy)
        original_finder = self._latest_confirm_action_leaf
        approval_state: dict[str, Any] = {}

        def emit_canonical(event_type: str, **event_kwargs: Any) -> None:
            event = make_approval_event(
                event_type,
                round_index=_approval_round_index,
                **event_kwargs,
            )
            emit_approval_event(self._emit_event, on_event, event)

        def guarded_finder(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
            tool_id, target_message_id, recipient = original_finder(payload)
            if not (tool_id and target_message_id and recipient):
                return tool_id, target_message_id, recipient
            conversation_id = payload.get("conversation_id")
            if not isinstance(conversation_id, str):
                conversation_id = None
            approval = _pending_approval(tool_id, target_message_id, recipient)
            decision = approval_policy.evaluate(approval)
            approval_state["approval"] = approval
            approval_state["decision"] = decision
            approval_state["conversation_id"] = conversation_id

            emit_canonical(
                "approval_detected",
                conversation_id=conversation_id,
                approval=approval,
            )
            if not decision.allowed:
                emit_canonical(
                    "approval_denied",
                    conversation_id=conversation_id,
                    approval=approval,
                    decision=decision,
                )
                raise ApprovalDeniedError(approval=approval, decision=decision)
            emit_canonical(
                "approval_allowed",
                conversation_id=conversation_id,
                approval=approval,
                decision=decision,
            )
            return tool_id, target_message_id, recipient

        def normalized_on_event(event: dict[str, Any]) -> None:
            if not isinstance(event, dict):
                if on_event is not None:
                    on_event(event)
                return
            event_type = event.get("type")
            if event_type in {
                "pending_approval_detected",
                "approval_policy_allowed",
                "approval_policy_denied",
            }:
                return

            approval = approval_state.get("approval")
            conversation_id = event.get("conversation_id")
            if not isinstance(conversation_id, str):
                conversation_id = approval_state.get("conversation_id")
            if event_type == "approval_sent" and isinstance(approval, PendingApproval):
                emit_canonical(
                    "approval_sent",
                    conversation_id=conversation_id,
                    approval=approval,
                    metadata_preview={"legacy_event": dict(event)},
                )
                return
            if event_type == "approval_completed" and isinstance(approval, PendingApproval):
                message_id = event.get("message_id")
                if not isinstance(message_id, str):
                    message_id = None
                emit_canonical(
                    "approval_completed",
                    conversation_id=conversation_id,
                    approval=approval,
                    message_id=message_id,
                    metadata_preview={"legacy_event": dict(event)},
                )
                return
            if on_event is not None:
                on_event(event)

        self._latest_confirm_action_leaf = guarded_finder
        try:
            return original(self, conversation, on_event=normalized_on_event, **kwargs)
        except ApprovalDeniedError:
            raise
        except Exception as error:
            approval = approval_state.get("approval")
            if isinstance(approval, PendingApproval):
                emit_canonical(
                    "approval_failed",
                    conversation_id=approval_state.get("conversation_id"),
                    approval=approval,
                    error=str(error),
                )
            raise
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
                _approval_round_index=round_index,
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
