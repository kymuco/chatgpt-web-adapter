from __future__ import annotations

import re
from typing import Any


class WebChatAdapterError(RuntimeError):
    """Base exception for the package."""


class AuthError(WebChatAdapterError):
    """Authentication or auth-data loading failure."""



def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _optional_status_code(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        status_code = int(value)
    except (TypeError, ValueError):
        return None
    return status_code if status_code > 0 else None


def _body_preview(value: Any, *, limit: int = 300) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = text.strip()
    if not text:
        return None
    return text[:limit]


def _status_code_from_message(message: str) -> int | None:
    match = re.search(r"\bstatus=(\d+)\b", message)
    if match is None:
        return None
    return _optional_status_code(match.group(1))


def _body_preview_from_message(message: str) -> str | None:
    if "status=" not in message or ":" not in message:
        return None
    _prefix, body = message.split(":", 1)
    return _body_preview(body)


def _request_stage_from_message(message: str) -> str | None:
    if message.startswith("chat-requirements"):
        return "chat_requirements"
    if message.startswith("backend status="):
        return "conversation_stream"
    if message.startswith("conversation prepare"):
        return "conversation_prepare"
    if message.startswith("conversation status="):
        return "conversation_fetch"
    if message.startswith("conversations status="):
        return "conversation_list"
    if message.startswith("Create file"):
        return "file_create"
    if message.startswith("Upload file"):
        return "file_upload"
    if message.startswith("Finalize file"):
        return "file_finalize"
    if message.startswith("curl failed"):
        return "transport"
    return None


def _endpoint_from_stage(request_stage: str | None) -> str | None:
    if request_stage is None:
        return None
    endpoints = {
        "chat_requirements": "chat-requirements",
        "conversation_stream": "conversation",
        "conversation_prepare": "conversation/prepare",
        "conversation_fetch": "conversation",
        "conversation_list": "conversations",
        "file_create": "files",
        "file_upload": "file-upload-url",
        "file_finalize": "files/uploaded",
        "transport": None,
    }
    return endpoints.get(request_stage)


class RequestError(WebChatAdapterError):
    """HTTP transport or backend request failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        endpoint: str | None = None,
        body_preview: Any = None,
        request_stage: str | None = None,
    ) -> None:
        message = str(message)
        inferred_stage = _request_stage_from_message(message)
        self.status_code = (
            _optional_status_code(status_code) or _status_code_from_message(message)
        )
        self.request_stage = _optional_str(request_stage) or inferred_stage
        self.endpoint = _optional_str(endpoint) or _endpoint_from_stage(self.request_stage)
        self.body_preview = _body_preview(body_preview) or _body_preview_from_message(
            message
        )
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "status_code": self.status_code,
            "endpoint": self.endpoint,
            "body_preview": self.body_preview,
            "request_stage": self.request_stage,
        }


class MediaError(WebChatAdapterError):
    """Media normalization, download, or upload failure."""


class PayloadValidationError(WebChatAdapterError):
    """Raw payload failed lightweight validation."""


class ConversationTimeoutError(WebChatAdapterError):
    """Conversation did not reach a terminal wait state before timeout."""

    def __init__(
        self,
        message: str | None = None,
        *,
        timeout: float,
        last_status: Any = None,
    ) -> None:
        self.timeout = timeout
        self.last_status = last_status
        last_status_value = getattr(last_status, "status", None)
        if message is None:
            suffix = f"; last status: {last_status_value}" if last_status_value else ""
            message = f"conversation did not complete within {timeout:.1f} seconds{suffix}"
        super().__init__(message)
