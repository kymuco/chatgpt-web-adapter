from __future__ import annotations

from typing import Any


class WebChatAdapterError(RuntimeError):
    """Base exception for the package."""


class AuthError(WebChatAdapterError):
    """Authentication or auth-data loading failure."""


class RequestError(WebChatAdapterError):
    """HTTP transport or backend request failure."""


class MediaError(WebChatAdapterError):
    """Media normalization, download, or upload failure."""


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
