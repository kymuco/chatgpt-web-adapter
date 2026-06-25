from __future__ import annotations

import chatgpt_web_adapter as adapter


CORE_PUBLIC_API = [
    "ChatGPTWebClient",
    "WebChatClient",
    "ChatConversation",
    "AttachedConversation",
    "ChatMessage",
    "ConversationStatus",
    "PendingApproval",
    "ChatResponse",
    "ChatMetrics",
    "ChatRequestDiagnostics",
    "AuthData",
    "errors",
]


ERROR_EXPORTS = [
    "WebChatAdapterError",
    "AuthError",
    "ConversationTimeoutError",
    "MediaError",
    "PayloadValidationError",
    "RequestError",
]


def test_core_public_api_is_ordered_first() -> None:
    assert adapter.__all__[: len(CORE_PUBLIC_API)] == CORE_PUBLIC_API


def test_public_api_exports_are_available() -> None:
    assert len(adapter.__all__) == len(set(adapter.__all__))
    for name in adapter.__all__:
        assert hasattr(adapter, name)


def test_webchat_client_alias_remains_compatible() -> None:
    assert adapter.WebChatClient is adapter.ChatGPTWebClient


def test_errors_namespace_matches_direct_error_exports() -> None:
    assert adapter.errors.__all__ == ERROR_EXPORTS
    for name in ERROR_EXPORTS:
        assert getattr(adapter.errors, name) is getattr(adapter, name)
