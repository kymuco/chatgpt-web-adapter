from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .auth import DEFAULT_AUTH_FILE
from .browser_native_provider import BrowserNativeTurnProvider
from .browser_owned_write_runtime import (
    BrowserOwnedProductWriteRuntime,
    BrowserOwnedWriteExecution,
    BrowserOwnedWriteObservation,
    BrowserOwnedWriteRuntimeHealth,
)
from .client import ChatGPTWebClient, DEFAULT_TIMEOUT_SECONDS
from .types import ChatConversation, ChatMessage, ChatResponse, ConversationRef, ConversationStatus

BROWSER_OWNED_PRODUCT_TRANSPORT = "browser-owned"
DEFAULT_PRODUCT_TRANSPORT = BROWSER_OWNED_PRODUCT_TRANSPORT
SUPPORTED_PRODUCT_TRANSPORTS: tuple[str, ...] = (BROWSER_OWNED_PRODUCT_TRANSPORT,)


def normalize_product_transport(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("transport must be a string")
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_PRODUCT_TRANSPORTS:
        supported = ", ".join(SUPPORTED_PRODUCT_TRANSPORTS)
        raise ValueError(f"unsupported product transport {value!r}; expected one of: {supported}")
    return normalized


@dataclass(frozen=True)
class ProductRuntimeHealth:
    transport: str
    ready: bool
    reason: str
    bridge_available: bool
    extension_connected: bool
    runtime_tab_id: int | None
    runtime_tab_preexisting: bool
    conversation_id: str | None
    canonical_status: str | None
    canonical_read_checked: bool
    read_plane: str
    session_plane: str
    write_plane: str
    automatic_write_retry: bool = False
    fallback_transport: str | None = None

    @classmethod
    def from_browser_owned(
        cls,
        health: BrowserOwnedWriteRuntimeHealth,
    ) -> "ProductRuntimeHealth":
        return cls(
            transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
            ready=health.ready,
            reason=health.reason,
            bridge_available=health.bridge_available,
            extension_connected=health.extension_connected,
            runtime_tab_id=health.runtime_tab_id,
            runtime_tab_preexisting=health.runtime_tab_preexisting,
            conversation_id=health.conversation_id,
            canonical_status=health.canonical_status,
            canonical_read_checked=health.canonical_read_checked,
            read_plane=health.read_plane,
            session_plane=health.session_plane,
            write_plane=health.write_plane,
            automatic_write_retry=health.automatic_write_retry,
            fallback_transport=None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductRuntimeExecution:
    transport: str
    response: ChatResponse
    observation: BrowserOwnedWriteObservation


class ChatGPTProductRuntime:
    """Production ordinary-ChatGPT product runtime.

    PR8.3 intentionally exposes browser-owned product write as an explicit
    transport. It never silently falls back to the legacy direct-web write path.
    Browserless canonical reads/session renewal remain owned by ChatGPTWebClient;
    only ordinary product writes are delegated to BrowserOwnedProductWriteRuntime.
    """

    def __init__(
        self,
        client: Any,
        *,
        transport: str = DEFAULT_PRODUCT_TRANSPORT,
        provider: BrowserNativeTurnProvider | None = None,
    ) -> None:
        self.transport = normalize_product_transport(transport)
        self.client = client
        self.provider = provider or BrowserNativeTurnProvider()
        self._writer = BrowserOwnedProductWriteRuntime(
            self.client,
            provider=self.provider,
        )

    def health(
        self,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
    ) -> ProductRuntimeHealth:
        return ProductRuntimeHealth.from_browser_owned(self._writer.health(conversation))

    readiness = health

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        return self._writer.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )

    def send(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        return self.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ProductRuntimeExecution:
        execution: BrowserOwnedWriteExecution = self._writer.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )
        return ProductRuntimeExecution(
            transport=self.transport,
            response=execution.response,
            observation=execution.observation,
        )

    def get_status(self, conversation: Any) -> ConversationStatus:
        return self.client.get_status(conversation)

    def get_messages(self, conversation: Any, **kwargs: Any) -> list[ChatMessage]:
        return self.client.get_messages(conversation, **kwargs)

    def attach_conversation(self, conversation: Any) -> Any:
        return self.client.attach_conversation(conversation)

    def governance(self) -> dict[str, Any]:
        writer = dict(self._writer.governance())
        writer.update(
            {
                "transport": self.transport,
                "transport_selection_explicit": True,
                "supported_product_transports": list(SUPPORTED_PRODUCT_TRANSPORTS),
                "fallback_transport": None,
                "legacy_direct_write_fallback": False,
                "new_chat_supported": True,
                "continuation_supported": True,
                "daily_use_entrypoint": "ChatGPTProductRuntime.send",
                "canonical_lifecycle_access": True,
            }
        )
        return writer


def assemble_product_runtime(
    *,
    transport: str = DEFAULT_PRODUCT_TRANSPORT,
    client: Any | None = None,
    provider: BrowserNativeTurnProvider | None = None,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    client_timeout: int = DEFAULT_TIMEOUT_SECONDS,
    auto_refresh_auth: bool = True,
    persist_refreshed_auth: bool = True,
) -> ChatGPTProductRuntime:
    """Assemble the production ordinary-ChatGPT runtime.

    Assembly never performs interactive browser login and never enables the
    legacy Sentinel/direct-write machinery. If the browser-owned bridge is not
    available, ``health()`` reports that state and writes fail closed.
    """

    normalized = normalize_product_transport(transport)
    if client is None:
        client = ChatGPTWebClient(
            auth_file=auth_file,
            timeout=client_timeout,
            auto_refresh_auth=auto_refresh_auth,
            persist_refreshed_auth=persist_refreshed_auth,
            auto_login=False,
            auto_sentinel=False,
        )
    return ChatGPTProductRuntime(
        client,
        transport=normalized,
        provider=provider,
    )
