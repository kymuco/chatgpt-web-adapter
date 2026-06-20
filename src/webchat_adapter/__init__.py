from __future__ import annotations

from .attach import attach_conversation as _attach_conversation
from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .client import DEFAULT_MODEL, ChatGPTWebClient
from .exceptions import AuthError, MediaError, RequestError, WebChatAdapterError
from .types import (
    AttachedConversation,
    AuthData,
    ChatConversation,
    ChatMetrics,
    ChatResponse,
    ConversationRef,
    MediaItem,
    MediaSource,
)

ChatGPTWebClient.attach_conversation = _attach_conversation
WebChatClient = ChatGPTWebClient

__all__ = [
    "AttachedConversation",
    "AuthData",
    "AuthError",
    "ChatConversation",
    "ChatGPTWebClient",
    "ChatMetrics",
    "ChatResponse",
    "ConversationRef",
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
