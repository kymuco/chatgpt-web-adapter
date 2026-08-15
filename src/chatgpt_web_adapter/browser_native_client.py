from __future__ import annotations

import time
from typing import Any, Callable

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import ConversationTimeoutError, RequestError
from .types import (
    ChatConversation,
    ChatMetrics,
    ChatRequestDiagnostics,
    ChatResponse,
    ConversationRef,
)


def set_browser_native_turn_provider(self: Any, provider: BrowserNativeTurnProvider | None) -> None:
    if provider is not None and not callable(getattr(provider, "send_text", None)):
        raise TypeError("provider must expose a callable send_text() or be None")
    self._browser_native_turn_provider = provider


def _assistant_message_ids(self: Any, conversation: Any) -> set[str]:
    messages = self.get_messages(
        conversation,
        limit=None,
        roles={"assistant"},
        include_empty=True,
    )
    return {
        message.message_id
        for message in messages
        if isinstance(getattr(message, "message_id", None), str)
    }


def _canonical_status_value(self: Any, conversation: Any) -> str | None:
    try:
        status = self.get_status(conversation)
    except Exception:
        return None
    value = getattr(status, "status", None)
    return value if isinstance(value, str) else None


def _status_finalizes_message(status: Any, message_id: str) -> bool:
    if status is None or not isinstance(message_id, str) or not message_id:
        return False
    return (
        getattr(status, "status", None) == "completed"
        and getattr(status, "message_id", None) == message_id
    )


def _wait_for_new_final_assistant(
    self: Any,
    conversation_id: str,
    *,
    baseline_assistant_ids: set[str],
    timeout: float,
    interval: float,
) -> Any:
    deadline = time.monotonic() + timeout
    last_status = None
    while True:
        try:
            last_status = self.get_status(conversation_id)
        except Exception:
            last_status = None
        messages = self.get_messages(
            conversation_id,
            limit=None,
            roles={"assistant"},
            include_empty=True,
        )
        candidates = [
            message
            for message in messages
            if isinstance(getattr(message, "message_id", None), str)
            and message.message_id not in baseline_assistant_ids
            and bool(getattr(message, "text", "").strip())
        ]
        for candidate in reversed(candidates):
            finish_reason = getattr(candidate, "finish_reason", None)
            if isinstance(finish_reason, str) and bool(finish_reason.strip()):
                return candidate
            if _status_finalizes_message(last_status, candidate.message_id):
                return candidate
        if time.monotonic() >= deadline:
            raise ConversationTimeoutError(
                "browser-native write completed but canonical assistant readback did not finish",
                timeout=timeout,
                last_status=last_status,
            )
        time.sleep(max(0.2, interval))


def send_browser_native(
    self: Any,
    prompt: str,
    *,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
    timeout: float = 150.0,
    poll_interval: float = 0.5,
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> ChatResponse:
    """Send one ordinary text turn through the persistent ChatGPT browser tab.

    The official page owns the protected write. For continuation turns, a fresh
    canonical ``completed`` status may authorize one bounded stale-UI reload
    before any text is inserted. After the write finishes, the existing SDK
    read path fetches the canonical final assistant message.
    """

    provider = getattr(self, "_browser_native_turn_provider", None)
    if not callable(getattr(provider, "send_text", None)):
        raise RequestError(
            "BROWSER_NATIVE_PROVIDER_NOT_CONFIGURED",
            request_stage="browser_native_turn",
        )
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if poll_interval <= 0:
        raise ValueError("poll_interval must be positive")

    started = time.monotonic()
    baseline_assistant_ids: set[str] = set()
    is_continuation = conversation is not None
    canonical_status_before_turn = None
    if conversation is not None:
        baseline_assistant_ids = _assistant_message_ids(self, conversation)
        canonical_status_before_turn = _canonical_status_value(self, conversation)

    recovery_send = getattr(provider, "send_text_with_stale_ui_recovery", None)
    canonical_status_recovery_confirm = None
    recovery_authorized = False
    if (
        is_continuation
        and canonical_status_before_turn == "completed"
        and callable(recovery_send)
    ):
        canonical_status_recovery_confirm = _canonical_status_value(self, conversation)
        recovery_authorized = canonical_status_recovery_confirm == "completed"

    self._emit_event(
        on_event,
        "browser_native_turn_started",
        is_continuation=is_continuation,
        canonical_status_before_turn=canonical_status_before_turn,
        canonical_status_recovery_confirm=canonical_status_recovery_confirm,
        stale_ui_recovery_authorized=recovery_authorized,
    )

    if recovery_authorized:
        canonical_completed_at_ms = int(time.time() * 1000)
        turn = recovery_send(
            prompt,
            conversation=conversation,
            timeout=timeout,
            canonical_completed_at_ms=canonical_completed_at_ms,
        )
    else:
        turn = provider.send_text(prompt, conversation=conversation, timeout=timeout)

    self._emit_event(
        on_event,
        "browser_native_write_completed",
        conversation_id=turn.conversation_id,
        turn_exchange_id=turn.turn_exchange_id,
        status_code=turn.response_status,
        elapsed_ms=turn.elapsed_ms,
        runtime_reloaded=turn.runtime_reloaded,
        runtime_reload_ms=turn.runtime_reload_ms,
        runtime_tab_id=turn.tab_id,
        runtime_tab_preexisting=turn.runtime_tab_preexisting,
        runtime_tab_created_for_turn=turn.runtime_tab_created_for_turn,
        tab_was_active_at_write_start=turn.tab_was_active,
        tab_active_after_write=turn.tab_active_after,
        tab_activated_during_turn=turn.tab_activated_during_turn,
        foreground_activation_observed=turn.foreground_activation_observed,
    )

    remaining = max(1.0, timeout - (time.monotonic() - started))
    final_message = _wait_for_new_final_assistant(
        self,
        turn.conversation_id,
        baseline_assistant_ids=baseline_assistant_ids,
        timeout=remaining,
        interval=poll_interval,
    )
    attached = self.attach_conversation(turn.conversation_id)
    conversation_data = attached.conversation.to_dict()
    conversation_data.update(
        {
            "conversation_id": turn.conversation_id,
            "message_id": final_message.message_id,
            "finish_reason": final_message.finish_reason,
            "is_thinking": False,
        }
    )
    result_conversation = ChatConversation.from_dict(conversation_data)
    total = time.monotonic() - started
    response = ChatResponse(
        text=final_message.text,
        title=attached.title,
        conversation=result_conversation,
        metrics=ChatMetrics(total=total, backend_status=turn.response_status),
        request=ChatRequestDiagnostics(
            conversation_id=turn.conversation_id,
            is_continuation=is_continuation,
            observed_model=final_message.model,
            turn_exchange_id=turn.turn_exchange_id,
        ),
    )
    if on_token is not None and response.text:
        on_token(response.text)
    self._emit_event(
        on_event,
        "browser_native_readback_completed",
        conversation_id=turn.conversation_id,
        message_id=final_message.message_id,
        model=final_message.model,
        total=total,
    )
    return response
