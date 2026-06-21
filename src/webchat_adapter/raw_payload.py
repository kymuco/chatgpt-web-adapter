from __future__ import annotations

import copy
import time
from typing import Any, Callable

from .payload_validation import validate_payload
from .types import ChatConversation, ChatMetrics, ChatResponse


def send_payload(
    self: Any,
    payload: dict[str, Any],
    *,
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> ChatResponse:
    """Send a raw ChatGPT web backend payload.

    Experimental. This is not an official or stable API. The ChatGPT web
    backend may change at any time. The payload creates real ChatGPT web
    conversations and messages. Use at your own risk.
    """

    validate_payload(payload)

    payload_copy = copy.deepcopy(payload)
    requirements, proof_header = self._get_ready_requirements()
    chat_token = requirements.get("token") if isinstance(requirements, dict) else None
    if not isinstance(chat_token, str) or not chat_token:
        from .exceptions import RequestError

        raise RequestError("chat-requirements token is missing")

    headers = self._build_headers(
        {
            "accept": "text/event-stream",
            "content-type": "application/json",
            "openai-sentinel-chat-requirements-token": chat_token,
            "openai-sentinel-proof-token": proof_header,
            "openai-sentinel-turnstile-token": self.auth.turnstile_token
            if (requirements.get("turnstile") or {}).get("required")
            else None,
        }
    )

    started_at = time.perf_counter()
    observed_conversation_id, observed_message_id, text = self._stream_backend_payload(
        payload_copy,
        headers,
        on_token=on_token,
        on_event=on_event,
    )
    total_latency = time.perf_counter() - started_at

    fallback_conversation_id = payload_copy.get("conversation_id")
    if not isinstance(fallback_conversation_id, str) or not fallback_conversation_id:
        fallback_conversation_id = None
    fallback_message_id = payload_copy.get("parent_message_id")
    if not isinstance(fallback_message_id, str) or not fallback_message_id:
        fallback_message_id = None

    conversation_id = observed_conversation_id or fallback_conversation_id
    message_id = observed_message_id or fallback_message_id
    response = ChatResponse(
        text=text,
        conversation=ChatConversation(
            conversation_id=conversation_id,
            message_id=message_id,
            parent_message_id=message_id,
            finish_reason="stop",
            is_thinking=False,
        ),
        metrics=ChatMetrics(total=total_latency),
    )

    messages = payload_copy.get("messages")
    self._emit_event(
        on_event,
        "raw_payload_sent",
        experimental=True,
        conversation_id=response.conversation.conversation_id,
        message_id=response.conversation.message_id,
        message_count=len(messages) if isinstance(messages, list) else None,
    )
    return response
