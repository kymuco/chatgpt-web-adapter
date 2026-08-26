from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import ConversationTimeoutError, RequestError
from .messages import _chat_message_from_node, _current_branch_nodes
from .product_media import current_browser_owned_attachment_paths
from .revision_safe_streaming_pr8_9 import RevisionSafeTextAccumulator
from .status import _status_from_payload
from .types import (
    AttachedConversation,
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


def _assistant_candidates_from_payload(
    payload: dict[str, Any],
    *,
    baseline_assistant_ids: set[str],
) -> list[Any]:
    candidates: list[Any] = []
    for node_id, node in _current_branch_nodes(payload):
        message = _chat_message_from_node(node_id, node)
        if message is None or getattr(message, "role", None) != "assistant":
            continue
        message_id = getattr(message, "message_id", None)
        if not isinstance(message_id, str) or message_id in baseline_assistant_ids:
            continue
        if not bool(getattr(message, "text", "").strip()):
            continue
        candidates.append(message)
    return candidates


def _wait_for_new_final_assistant(
    self: Any,
    conversation_id: str,
    *,
    baseline_assistant_ids: set[str],
    timeout: float,
    interval: float,
    include_readback: bool = False,
) -> Any | tuple[Any, dict[str, Any] | None, int | None]:
    """Wait for canonical finality, optionally returning the reused payload.

    The default return remains the historical assistant-message object. PR8.11
    production callers opt into ``include_readback=True`` so status, assistant
    messages and attach metadata can be derived from one canonical payload per
    poll instead of issuing three serial reads after browser completion.
    Lightweight/custom clients without the private canonical reader retain the
    previous get_status/get_messages path.
    """

    deadline = time.monotonic() + timeout
    last_status = None
    canonical_reader = getattr(self, "_get_conversation_payload", None)
    use_single_payload = callable(canonical_reader)
    canonical_payload_read_count = 0

    while True:
        if use_single_payload:
            payload = None
            try:
                canonical_payload_read_count += 1
                payload = canonical_reader(conversation_id)
            except Exception:
                payload = None

            if isinstance(payload, dict):
                last_status = _status_from_payload(payload)
                candidates = _assistant_candidates_from_payload(
                    payload,
                    baseline_assistant_ids=baseline_assistant_ids,
                )
                for candidate in reversed(candidates):
                    finish_reason = getattr(candidate, "finish_reason", None)
                    if isinstance(finish_reason, str) and bool(finish_reason.strip()):
                        if include_readback:
                            return candidate, payload, canonical_payload_read_count
                        return candidate
                    if _status_finalizes_message(last_status, candidate.message_id):
                        if include_readback:
                            return candidate, payload, canonical_payload_read_count
                        return candidate
        else:
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
                    if include_readback:
                        return candidate, None, None
                    return candidate
                if _status_finalizes_message(last_status, candidate.message_id):
                    if include_readback:
                        return candidate, None, None
                    return candidate

        if time.monotonic() >= deadline:
            raise ConversationTimeoutError(
                "browser-native write completed but canonical assistant readback did not finish",
                timeout=timeout,
                last_status=last_status,
            )
        time.sleep(max(0.2, interval))


def _emit_revision_safe_event(
    self: Any,
    on_event: Callable[[dict[str, Any]], None] | None,
    event: dict[str, Any],
) -> None:
    if on_event is None:
        return
    event_type = event.get("type")
    if not isinstance(event_type, str) or not event_type:
        return
    payload = {key: value for key, value in event.items() if key != "type"}
    try:
        self._emit_event(on_event, event_type, **payload)
    except Exception:
        # PR8.9 observation callbacks never change write authority or authorize
        # replay after delegation.
        pass


def _provider_supports_revision_safe_streaming(provider: Any) -> bool:
    if not callable(getattr(provider, "send_text_streaming", None)):
        return False
    rpc = getattr(provider, "_rpc", None)
    if not callable(rpc):
        return False
    try:
        parameters = inspect.signature(rpc).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "on_event" or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _callable_accepts_attachment_paths(value: Any) -> bool:
    if not callable(value):
        return False
    try:
        parameters = inspect.signature(value).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "attachment_paths"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def send_browser_native(
    self: Any,
    prompt: str,
    *,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
    timeout: float = 150.0,
    poll_interval: float = 0.5,
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    attachment_paths: Sequence[str | Path] | None = None,
) -> ChatResponse:
    """Send one ordinary product turn through the persistent ChatGPT browser tab.

    PR8.9 exposes revision-safe early assistant text through ``on_event`` while
    keeping canonical readback authoritative. ``on_token`` intentionally remains
    final-only because it cannot retract revisions. PR9.2 carries validated local
    attachment paths to the official page; attachment bytes are never embedded in
    Native Messaging JSON and canonical assistant finality is unchanged.
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

    if attachment_paths is None:
        scoped_paths = current_browser_owned_attachment_paths()
        if scoped_paths is not None:
            attachment_paths = scoped_paths
    normalized_attachment_paths = tuple(attachment_paths or ())
    if normalized_attachment_paths and not _callable_accepts_attachment_paths(provider.send_text):
        raise RequestError(
            "BROWSER_NATIVE_RICH_INPUT_PROVIDER_UNSUPPORTED",
            request_stage="browser_native_turn_preflight",
        )

    started = time.monotonic()
    baseline_assistant_ids: set[str] = set()
    is_continuation = conversation is not None
    canonical_status_before_turn = None
    if conversation is not None:
        baseline_assistant_ids = _assistant_message_ids(self, conversation)
        canonical_status_before_turn = _canonical_status_value(self, conversation)

    recovery_send = getattr(provider, "send_text_with_stale_ui_recovery", None)
    recovery_stream_send = getattr(
        provider, "send_text_with_stale_ui_recovery_streaming", None
    )
    stream_send = getattr(provider, "send_text_streaming", None)
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
        attachment_count=len(normalized_attachment_paths),
    )

    stream_state = RevisionSafeTextAccumulator()

    def handle_text_event(event: dict[str, Any]) -> None:
        normalized = stream_state.apply(event)
        if normalized is not None:
            _emit_revision_safe_event(self, on_event, normalized)

    streaming_requested = (
        on_event is not None and _provider_supports_revision_safe_streaming(provider)
    )
    attachment_kwargs = (
        {"attachment_paths": normalized_attachment_paths}
        if normalized_attachment_paths
        else {}
    )
    if recovery_authorized:
        canonical_completed_at_ms = int(time.time() * 1000)
        if streaming_requested and callable(recovery_stream_send):
            if normalized_attachment_paths and not _callable_accepts_attachment_paths(recovery_stream_send):
                raise RequestError(
                    "BROWSER_NATIVE_RICH_INPUT_RECOVERY_PROVIDER_UNSUPPORTED",
                    request_stage="browser_native_turn_preflight",
                )
            turn = recovery_stream_send(
                prompt,
                conversation=conversation,
                timeout=timeout,
                canonical_completed_at_ms=canonical_completed_at_ms,
                on_text_event=handle_text_event,
                **attachment_kwargs,
            )
        else:
            if normalized_attachment_paths and not _callable_accepts_attachment_paths(recovery_send):
                raise RequestError(
                    "BROWSER_NATIVE_RICH_INPUT_RECOVERY_PROVIDER_UNSUPPORTED",
                    request_stage="browser_native_turn_preflight",
                )
            turn = recovery_send(
                prompt,
                conversation=conversation,
                timeout=timeout,
                canonical_completed_at_ms=canonical_completed_at_ms,
                **attachment_kwargs,
            )
    elif streaming_requested and callable(stream_send):
        if normalized_attachment_paths and not _callable_accepts_attachment_paths(stream_send):
            raise RequestError(
                "BROWSER_NATIVE_RICH_INPUT_STREAM_PROVIDER_UNSUPPORTED",
                request_stage="browser_native_turn_preflight",
            )
        turn = stream_send(
            prompt,
            conversation=conversation,
            timeout=timeout,
            on_text_event=handle_text_event,
            **attachment_kwargs,
        )
    else:
        turn = provider.send_text(
            prompt,
            conversation=conversation,
            timeout=timeout,
            **attachment_kwargs,
        )

    raw_attachment_count = getattr(turn, "attachment_count", None)
    if normalized_attachment_paths:
        expected_attachment_count = len(normalized_attachment_paths)
        if (
            not isinstance(raw_attachment_count, int)
            or isinstance(raw_attachment_count, bool)
            or raw_attachment_count != expected_attachment_count
        ):
            raise RequestError(
                "BROWSER_NATIVE_RICH_INPUT_ATTACHMENT_CONFIRMATION_MISMATCH",
                request_stage="browser_native_turn_postwrite",
            )
        attachment_count = raw_attachment_count
    elif (
        isinstance(raw_attachment_count, int)
        and not isinstance(raw_attachment_count, bool)
        and raw_attachment_count >= 0
    ):
        attachment_count = raw_attachment_count
    else:
        attachment_count = 0

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
        attachment_count=attachment_count,
        revision_safe_stream_observation_count=stream_state.observation_count,
    )

    remaining = max(1.0, timeout - (time.monotonic() - started))
    final_message, canonical_payload, canonical_payload_read_count = _wait_for_new_final_assistant(
        self,
        turn.conversation_id,
        baseline_assistant_ids=baseline_assistant_ids,
        timeout=remaining,
        interval=poll_interval,
        include_readback=True,
    )

    if canonical_payload is not None:
        result_conversation = ChatConversation(
            conversation_id=turn.conversation_id,
            message_id=final_message.message_id,
            parent_message_id=final_message.message_id,
            finish_reason=final_message.finish_reason,
            is_thinking=False,
        )
        attached = AttachedConversation.from_payload(
            canonical_payload,
            conversation=result_conversation,
        )
    else:
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

    finalization = stream_state.finalization_event(
        canonical_text=final_message.text,
        conversation_id=turn.conversation_id,
        message_id=final_message.message_id,
        model=final_message.model,
        finish_reason=final_message.finish_reason,
    )
    _emit_revision_safe_event(self, on_event, finalization)

    if on_token is not None and response.text:
        on_token(response.text)
    self._emit_event(
        on_event,
        "browser_native_readback_completed",
        conversation_id=turn.conversation_id,
        message_id=final_message.message_id,
        model=final_message.model,
        total=total,
        attachment_count=attachment_count,
        canonical_payload_read_count=canonical_payload_read_count,
        canonical_payload_reused_for_attach=canonical_payload is not None,
        stream_canonical_reconciliation=finalization["reconciliation"],
        revision_safe_stream_observation_count=stream_state.observation_count,
        revision_safe_stream_revision_count=stream_state.revision_count,
        revision_safe_stream_delivery_incomplete=stream_state.delivery_incomplete,
    )
    return response