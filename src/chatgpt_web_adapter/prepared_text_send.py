from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Sequence

from .auth import CHAT_URL
from .client import DEFAULT_STREAM_RECOVERY_POLL_INTERVAL_SECONDS
from .conversation_prepare import prepare_text_turn
from .exceptions import RequestError
from .types import ChatConversation, ChatMetrics, ChatRequestDiagnostics, ChatResponse, MediaItem

CONVERSATION_PATH = "/backend-api/f/conversation"


def _clear_prefetched_requirements(client: Any) -> None:
    client.prefetched_requirements = None
    client.prefetched_proof_header = None
    client.prefetched_ts = 0.0


def _metadata_finish_reason(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    finish_details = metadata.get("finish_details")
    if not isinstance(finish_details, dict):
        return None
    value = finish_details.get("type")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _finish_reason(message: Any) -> str | None:
    if not isinstance(message, dict):
        return None
    return _metadata_finish_reason(message.get("metadata"))


def _capture_stream_event_diagnostics(client: Any, event: Any, state: dict[str, Any]) -> None:
    """Capture only non-secret response metadata already exposed by stream events."""

    if not isinstance(event, dict):
        return
    parsed = event.get("parsed") if event.get("type") == "raw_sse_event" else event
    if not isinstance(parsed, dict):
        return

    metadata = parsed.get("metadata")
    if isinstance(metadata, dict):
        client._capture_metadata_diagnostics(metadata, state)
        finish_reason = _metadata_finish_reason(metadata)
        if finish_reason:
            state["finish_reason"] = finish_reason

    value = parsed.get("v")
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, dict):
            client._capture_message_diagnostics(message, state)
            finish_reason = _finish_reason(message)
            if finish_reason:
                state["finish_reason"] = finish_reason
        return

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict) or item.get("p") != "/message/metadata":
                continue
            item_metadata = item.get("v")
            if not isinstance(item_metadata, dict):
                continue
            client._capture_metadata_diagnostics(item_metadata, state)
            finish_reason = _metadata_finish_reason(item_metadata)
            if finish_reason:
                state["finish_reason"] = finish_reason


def send_existing_text_prepared(
    self: Any,
    prompt: str,
    *,
    model: str,
    conversation: ChatConversation | dict[str, Any],
    system: str | None = None,
    reasoning_effort: str | None = None,
    web_search: bool = False,
    temporary: bool = False,
    media: Sequence[MediaItem] | None = None,
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> ChatResponse:
    """Send one ordinary text turn through the observed prepare/conduit contract.

    This path is intentionally scoped to an existing conversation with no media.
    New-chat and multimodal writes continue through the legacy ``send()`` path
    until they receive independent live-contract evidence. ``system`` is accepted
    for send-surface compatibility but, as before for an existing conversation,
    is not injected as a new system message.
    """

    if media:
        raise ValueError("prepared existing-text send does not accept media")

    conversation_dict = self._conversation_to_dict(conversation)
    if not isinstance(conversation_dict, dict):
        raise ValueError("conversation is required")
    conversation_id = conversation_dict.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation.conversation_id is required")
    conversation_id = conversation_id.strip()

    parent_message_id = (
        conversation_dict.get("parent_message_id")
        or conversation_dict.get("message_id")
    )
    if not isinstance(parent_message_id, str) or not parent_message_id.strip():
        raise ValueError("conversation parent/message id is required")
    parent_message_id = parent_message_id.strip()

    normalized_effort = self._normalize_reasoning_effort(reasoning_effort)
    resolved_model = self._resolve_model(model, reasoning_effort)
    messages = self._create_messages(
        prompt,
        None,
        system_hints=["search"] if web_search else None,
    )
    user_message = messages[-1] if messages else None
    user_message_id = user_message.get("id") if isinstance(user_message, dict) else None
    if not isinstance(user_message_id, str) or not user_message_id.strip():
        raise RequestError(
            "conversation prepare could not resolve user message id",
            request_stage="conversation_prepare",
        )

    # The live contract is prepare -> fresh requirements -> final write. Discard
    # any material produced by warmup before prepare so it cannot be reused after
    # the conduit token is minted.
    _clear_prefetched_requirements(self)
    self._emit_event(
        on_event,
        "conversation_prepare_started",
        existing_conversation=True,
        ordinary_text=True,
        partial_query_message_id_present=True,
    )
    prepare_result, _prepare_payload = prepare_text_turn(
        self,
        prompt,
        model=resolved_model,
        conversation=conversation_dict,
        reasoning_effort=normalized_effort,
        web_search=web_search,
        temporary=temporary,
        partial_query_message_id=user_message_id,
    )
    if not prepare_result.status_ok:
        raise RequestError(
            f"conversation prepare status={prepare_result.status_code}: rejected",
            status_code=prepare_result.status_code,
            request_stage="conversation_prepare",
        )
    conduit_token = prepare_result.conduit_token
    if not isinstance(conduit_token, str) or not conduit_token.strip():
        raise RequestError(
            "conversation prepare response missing conduit_token",
            request_stage="conversation_prepare",
        )
    conduit_token = conduit_token.strip()
    self._emit_event(
        on_event,
        "conversation_prepare_succeeded",
        status_code=prepare_result.status_code,
        conduit_token_present=True,
    )

    started_at = time.perf_counter()
    observed_conversation_id: str | None = None
    observed_message_id: str | None = None
    text = ""
    stream_diagnostics: dict[str, Any] = {}
    observed_model: str | None = None
    observed_reasoning_effort: str | None = None
    finish_reason: str | None = None

    def capture_stream_event(event: dict[str, Any]) -> None:
        _capture_stream_event_diagnostics(self, event, stream_diagnostics)
        if on_event is not None:
            on_event(event)

    try:
        requirements, proof_header = self._get_ready_requirements()
        chat_token = requirements.get("token") if isinstance(requirements, dict) else None
        if not isinstance(chat_token, str) or not chat_token:
            raise RequestError("chat-requirements token is missing")

        payload: dict[str, Any] = {
            "action": "next",
            "fork_from_shared_post": False,
            "conversation_id": conversation_id,
            "parent_message_id": parent_message_id,
            "model": resolved_model,
            "client_prepare_state": "success",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": False,
            "system_hints": ["search"] if web_search else [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
            "messages": messages,
        }
        if temporary:
            payload["history_and_training_disabled"] = True
        if normalized_effort is not None:
            payload["thinking_effort"] = normalized_effort

        headers = self._build_headers(
            {
                "accept": "text/event-stream",
                "content-type": "application/json",
                "origin": CHAT_URL.rstrip("/"),
                "referer": f"{CHAT_URL.rstrip('/')}/c/{conversation_id}",
                "x-openai-target-path": CONVERSATION_PATH,
                "x-openai-target-route": CONVERSATION_PATH,
                "x-conduit-token": conduit_token,
                "x-oai-turn-trace-id": str(uuid.uuid4()),
                "openai-sentinel-chat-requirements-token": chat_token,
                "openai-sentinel-proof-token": proof_header,
                "openai-sentinel-turnstile-token": self.auth.turnstile_token
                if (requirements.get("turnstile") or {}).get("required")
                else None,
            }
        )
        self._emit_event(
            on_event,
            "prepared_conversation_write_started",
            client_prepare_state="success",
            conduit_token_present=True,
            turn_trace_id_present=True,
        )

        observed_conversation_id, observed_message_id, text = self._stream_backend_payload(
            payload,
            headers,
            on_token=on_token,
            on_event=capture_stream_event,
        )
        observed_model = stream_diagnostics.get("observed_model")
        observed_reasoning_effort = stream_diagnostics.get("observed_reasoning_effort")
        finish_reason = stream_diagnostics.get("finish_reason")

        effective_conversation_id = observed_conversation_id or conversation_id
        if not text or not observed_message_id or observed_message_id == parent_message_id:
            message, polled_text, _polled_payload = self._poll_conversation_after_prepare(
                effective_conversation_id,
                previous_message_id=parent_message_id,
                timeout=max(1.0, float(self.timeout)),
                interval=DEFAULT_STREAM_RECOVERY_POLL_INTERVAL_SECONDS,
                on_token=None if text else on_token,
                on_event=on_event,
                reason="prepared_text_send_recovery",
                allow_global_fallback=False,
            )
            if isinstance(message, dict):
                message_id = message.get("id")
                if isinstance(message_id, str) and message_id:
                    observed_message_id = message_id
                if polled_text:
                    text = polled_text
                polled_finish_reason = _finish_reason(message)
                if polled_finish_reason:
                    finish_reason = polled_finish_reason
                diagnostics: dict[str, Any] = {}
                self._capture_message_diagnostics(message, diagnostics)
                if diagnostics.get("observed_model") is not None:
                    observed_model = diagnostics.get("observed_model")
                if diagnostics.get("observed_reasoning_effort") is not None:
                    observed_reasoning_effort = diagnostics.get("observed_reasoning_effort")
        observed_conversation_id = effective_conversation_id
    finally:
        _clear_prefetched_requirements(self)

    total_latency = time.perf_counter() - started_at
    self._emit_event(
        on_event,
        "prepared_conversation_write_completed",
        conversation_id_present=bool(observed_conversation_id),
        message_id_present=bool(observed_message_id),
        response_text_present=bool(text),
    )
    return ChatResponse(
        text=text,
        conversation=ChatConversation(
            conversation_id=observed_conversation_id or conversation_id,
            message_id=observed_message_id or parent_message_id,
            user_id=conversation_dict.get("user_id"),
            finish_reason=finish_reason or "stop",
            parent_message_id=observed_message_id or parent_message_id,
            is_thinking=False,
        ),
        metrics=ChatMetrics(total=total_latency),
        request=ChatRequestDiagnostics(
            requested_model=model.strip() if isinstance(model, str) and model.strip() else None,
            requested_reasoning_effort=reasoning_effort.strip()
            if isinstance(reasoning_effort, str) and reasoning_effort.strip()
            else None,
            sent_model=resolved_model,
            sent_reasoning_effort=normalized_effort,
            conversation_id=observed_conversation_id or conversation_id,
            parent_message_id=parent_message_id,
            is_continuation=True,
            web_search=web_search,
            temporary=temporary,
            has_media=False,
            message_count=len(messages),
            observed_model=observed_model,
            observed_reasoning_effort=observed_reasoning_effort,
        ),
    )
