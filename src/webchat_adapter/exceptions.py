from __future__ import annotations


class WebChatAdapterError(RuntimeError):
    """Base exception for the package."""


class AuthError(WebChatAdapterError):
    """Authentication or auth-data loading failure."""


class RequestError(WebChatAdapterError):
    """HTTP transport or backend request failure."""


class MediaError(WebChatAdapterError):
    """Media normalization, download, or upload failure."""
