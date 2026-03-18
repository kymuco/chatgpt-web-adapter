from __future__ import annotations

from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .client import DEFAULT_MODEL, ChatGPTWebClient
from .exceptions import AuthError, MediaError, RequestError, WebChatAdapterError
from .types import AuthData, ChatConversation, ChatMetrics, ChatResponse, MediaItem, MediaSource

WebChatClient = ChatGPTWebClient

__all__ = [
    "AuthData",
    "AuthError",
    "ChatConversation",
    "ChatGPTWebClient",
    "ChatMetrics",
    "ChatResponse",
    "DEFAULT_AUTH_FILE",
    "DEFAULT_MODEL",
    "MediaError",
    "MediaItem",
    "MediaSource",
    "RequestError",
    "WebChatAdapterError",
    "WebChatClient",
    "load_auth_data",
]
