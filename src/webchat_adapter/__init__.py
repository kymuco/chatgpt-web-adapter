from __future__ import annotations

from .attach import attach_conversation as _attach_conversation
from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .client import DEFAULT_MODEL, ChatGPTWebClient
from .conversation_send import send_to_conversation as _send_to_conversation
from .exceptions import AuthError, MediaError, RequestError, WebChatAdapterError
from .export import export_conversation as _export_conversation
from .messages import get_messages as _get_messages
from .types import (
    AttachedConversation,
    AuthData,
    ChatConversation,
    ChatMessage,
    ChatMetrics,
    ChatResponse,
    ConversationRef,
    MediaItem,
    MediaSource,
)

ChatGPTWebClient.attach_conversation = _attach_conversation
ChatGPTWebClient.export_conversation = _export_conversation
ChatGPTWebClient.get_messages = _get_messages
ChatGPTWebClient.send_to_conversation = _send_to_conversation
WebChatClient = ChatGPTWebClient

__all__ = [
    "AttachedConversation",
    "AuthData",
    "AuthError",
    "ChatConversation",
    "ChatGPTWebClient",
    "ChatMessage",
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
