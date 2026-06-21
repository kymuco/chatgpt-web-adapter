from __future__ import annotations

import time
from typing import Any

from .exceptions import ConversationTimeoutError
from .types import ChatConversation, ChatMessage, ConversationRef, WaitResult


def _coerce_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as error:
        raise TypeError("timeout must be a number") from error
    if timeout < 0:
        raise ValueError("timeout must be >= 0")
    return timeout


def _coerce_interval(value: Any) -> float:
    try:
        interval = float(value)
    except (TypeError, ValueError) as error:
        raise TypeError("interval must be a number") from error
    if interval <= 0:
        raise ValueError("interval must be > 0")
    return interval


def _completed_assistant_message(
    self: Any,
    ref: ConversationRef,
    status: Any,
) -> ChatMessage | None:
    messages = self.get_messages(
        ref,
        limit=None,
        roles={"assistant"},
        include_empty=True,
    )
    if not isinstance(messages, list) or not messages:
        return None

    status_node_id = getattr(status, "node_id", None)
    status_message_id = getattr(status, "message_id", None)
    for message in messages:
        if not isinstance(message, ChatMessage):
            continue
        if status_node_id is not None and message.node_id == status_node_id:
            return message
        if status_message_id is not None and message.message_id == status_message_id:
            return message

    for message in reversed(messages):
        if isinstance(message, ChatMessage):
            return message
    return None


def wait_until_completed(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
    timeout: float = 90,
    *,
    interval: float = 2.0,
) -> WaitResult:
    """Wait until a conversation completes or reaches a controlled lifecycle state."""

    ref = ConversationRef.from_any(url_or_id)
    timeout_seconds = _coerce_timeout(timeout)
    interval_seconds = _coerce_interval(interval)
    started = time.monotonic()
    deadline = started + timeout_seconds
    polls = 0
    last_status = None

    while True:
        polls += 1
        status = self.get_status(ref)
        last_status = status
        elapsed = time.monotonic() - started

        if getattr(status, "status", None) == "completed":
            return WaitResult(
                status=status,
                message=_completed_assistant_message(self, ref, status),
                elapsed=elapsed,
                polls=polls,
            )

        if getattr(status, "status", None) == "awaiting_tool_approval":
            return WaitResult(
                status=status,
                approval=self.get_pending_approval(ref),
                elapsed=elapsed,
                polls=polls,
            )

        now = time.monotonic()
        if now >= deadline:
            raise ConversationTimeoutError(
                timeout=timeout_seconds,
                last_status=last_status,
            )

        sleep_seconds = min(interval_seconds, max(0.0, deadline - now))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
