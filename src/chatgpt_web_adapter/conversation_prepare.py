from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import client as client_mod
from .auth import CHAT_URL
from .types import ChatConversation

PREPARE_PATH = "/backend-api/f/conversation/prepare"


@dataclass(frozen=True)
class PrepareResult:
    """Result of a conversation prepare request.

    ``conduit_token`` is intentionally excluded from repr and should never be
    serialized into diagnostic artifacts. It exists only in memory so prepared
    write paths can reuse the response safely.
    """

    status_code: int
    status_ok: bool
    conduit_token_present: bool
    response_keys: tuple[str, ...] = ()
    conduit_token: str | None = field(default=None, repr=False, compare=False)


def _conversation_dict(value: ChatConversation | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, ChatConversation):
        return value.to_dict()
    if isinstance(value, dict):
        return dict(value)
    return {}


def _partial_query(prompt: str, *, message_id: str | None = None) -> dict[str, Any]:
    return {
        "id": message_id or str(uuid.uuid4()),
        "author": {"role": "user"},
        "content": {"content_type": "text", "parts": [str(prompt)]},
    }


def build_text_prepare_payload(
    prompt: str,
    *,
    model: str,
    conversation: ChatConversation | dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
    web_search: bool = False,
    temporary: bool = False,
    timezone: str | None = None,
    timezone_offset_min: int | None = None,
    partial_query_message_id: str | None = None,
) -> dict[str, Any]:
    """Build the observed ordinary-text ``conversation/prepare`` payload shape."""

    conversation_dict = _conversation_dict(conversation)
    parent_message_id = (
        conversation_dict.get("parent_message_id")
        or conversation_dict.get("message_id")
        or "client-created-root"
    )
    payload: dict[str, Any] = {
        "action": "next",
        "fork_from_shared_post": False,
        "parent_message_id": parent_message_id,
        "model": str(model),
        "client_prepare_state": "success",
        "conversation_mode": {"kind": "primary_assistant"},
        "system_hints": ["search"] if web_search else [],
        "partial_query": _partial_query(prompt, message_id=partial_query_message_id),
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {"app_name": "chatgpt.com"},
    }
    conversation_id = conversation_dict.get("conversation_id")
    if isinstance(conversation_id, str) and conversation_id:
        payload["conversation_id"] = conversation_id
    if temporary:
        payload["history_and_training_disabled"] = True
    if reasoning_effort is not None:
        payload["thinking_effort"] = reasoning_effort
    if timezone is not None:
        payload["timezone"] = timezone
    if timezone_offset_min is not None:
        payload["timezone_offset_min"] = int(timezone_offset_min)
    return payload


def build_prepare_headers(client: Any, *, conversation_id: str | None = None) -> dict[str, str]:
    referer = CHAT_URL
    if conversation_id:
        referer = f"{CHAT_URL.rstrip('/')}/c/{conversation_id}"
    return client._build_headers(
        {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": CHAT_URL.rstrip("/"),
            "referer": referer,
            "x-conduit-token": "no-token",
            "x-openai-target-path": PREPARE_PATH,
            "x-openai-target-route": PREPARE_PATH,
        }
    )


def prepare_text_turn(
    client: Any,
    prompt: str,
    *,
    model: str,
    conversation: ChatConversation | dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
    web_search: bool = False,
    temporary: bool = False,
    timezone: str | None = None,
    timezone_offset_min: int | None = None,
    partial_query_message_id: str | None = None,
) -> tuple[PrepareResult, dict[str, Any]]:
    """Issue only the prepare request and return structural evidence plus payload.

    The returned payload contains the prompt and must not be serialized into a
    diagnostic report. Callers should retain only structural booleans/counts.
    """

    payload = build_text_prepare_payload(
        prompt,
        model=model,
        conversation=conversation,
        reasoning_effort=reasoning_effort,
        web_search=web_search,
        temporary=temporary,
        timezone=timezone,
        timezone_offset_min=timezone_offset_min,
        partial_query_message_id=partial_query_message_id,
    )
    conversation_id = payload.get("conversation_id")
    headers = build_prepare_headers(
        client,
        conversation_id=conversation_id if isinstance(conversation_id, str) else None,
    )
    status, data = client._json_request(
        "POST",
        client_mod.CHAT_CONVERSATION_PREPARE_URL,
        payload,
        headers,
    )
    response = data if isinstance(data, dict) else {}
    conduit_token = response.get("conduit_token")
    if not isinstance(conduit_token, str) or not conduit_token.strip():
        conduit_token = None
    result = PrepareResult(
        status_code=int(status),
        status_ok=200 <= int(status) < 300 and response.get("status") in {None, "ok"},
        conduit_token_present=conduit_token is not None,
        response_keys=tuple(sorted(str(key) for key in response)),
        conduit_token=conduit_token,
    )
    return result, copy.deepcopy(payload)
