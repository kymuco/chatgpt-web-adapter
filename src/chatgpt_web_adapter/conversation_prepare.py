from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import client as client_mod
from .auth import CHAT_URL
from .types import ChatConversation
from .web_session import suppress_web_session_debug_trace

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
    include_partial_query: bool = True,
    client_prepare_state: str = "success",
    client_prepare_dispatch: str | None = None,
    client_prepare_source: str | None = None,
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
        "client_prepare_state": client_prepare_state,
        "conversation_mode": {"kind": "primary_assistant"},
        "system_hints": ["search"] if web_search else [],
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {"app_name": "chatgpt.com"},
    }
    if include_partial_query:
        payload["partial_query"] = _partial_query(
            prompt,
            message_id=partial_query_message_id,
        )
    if client_prepare_dispatch is not None:
        payload["client_prepare_dispatch"] = client_prepare_dispatch
    if client_prepare_source is not None:
        payload["client_prepare_source"] = client_prepare_source
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


def build_prepare_headers(
    client: Any,
    *,
    conversation_id: str | None = None,
    initial_conduit_token: str | None = "no-token",
) -> dict[str, str]:
    referer = CHAT_URL
    if conversation_id:
        referer = f"{CHAT_URL.rstrip('/')}/c/{conversation_id}"
    return client._build_headers(
        {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": CHAT_URL.rstrip("/"),
            "referer": referer,
            "x-conduit-token": initial_conduit_token,
            "x-openai-target-path": PREPARE_PATH,
            "x-openai-target-route": PREPARE_PATH,
        }
    )


def _prepare_json_request(
    client: Any,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, Any]:
    """Issue prepare without ever persisting its credential-bearing raw body.

    The shared HTTP tracer records raw response bodies. A prepare response carries
    the short-lived conduit credential, so this boundary suppresses generic trace
    output only for the current execution context and replaces it with a
    structural trace containing status, safe response keys, and token presence.
    """

    trace_dir_marker = object()
    trace_dir = getattr(client, "debug_trace_dir", trace_dir_marker)
    trace_enabled = trace_dir is not trace_dir_marker and trace_dir is not None
    with suppress_web_session_debug_trace():
        status, data = client._json_request(
            "POST",
            client_mod.CHAT_CONVERSATION_PREPARE_URL,
            payload,
            headers,
        )

    if trace_enabled:
        writer = getattr(client, "_write_debug_trace", None)
        if callable(writer):
            response = data if isinstance(data, dict) else {}
            conduit_token = response.get("conduit_token")
            writer(
                "prepare",
                {
                    "method": "POST",
                    "url": client_mod.CHAT_CONVERSATION_PREPARE_URL,
                    "response_status": int(status),
                    "response_keys": sorted(str(key) for key in response),
                    "conduit_token_present": isinstance(conduit_token, str)
                    and bool(conduit_token.strip()),
                    "raw_response_recorded": False,
                },
            )
    return int(status), data


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
    include_partial_query: bool = True,
    client_prepare_state: str = "success",
    client_prepare_dispatch: str | None = None,
    client_prepare_source: str | None = None,
    initial_conduit_token: str | None = "no-token",
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
        include_partial_query=include_partial_query,
        client_prepare_state=client_prepare_state,
        client_prepare_dispatch=client_prepare_dispatch,
        client_prepare_source=client_prepare_source,
    )
    conversation_id = payload.get("conversation_id")
    headers = build_prepare_headers(
        client,
        conversation_id=conversation_id if isinstance(conversation_id, str) else None,
        initial_conduit_token=initial_conduit_token,
    )
    status, data = _prepare_json_request(client, payload, headers)
    response = data if isinstance(data, dict) else {}
    conduit_token = response.get("conduit_token")
    if not isinstance(conduit_token, str) or not conduit_token.strip():
        conduit_token = None
    result = PrepareResult(
        status_code=int(status),
        status_ok=200 <= int(status) < 300 and response.get("status") == "ok",
        conduit_token_present=conduit_token is not None,
        response_keys=tuple(sorted(str(key) for key in response)),
        conduit_token=conduit_token,
    )
    return result, copy.deepcopy(payload)
