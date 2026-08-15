from __future__ import annotations

from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .client import ChatGPTWebClient, DEFAULT_TIMEOUT_SECONDS
from .product_transport import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    DEFAULT_PRODUCT_TRANSPORT,
    SUPPORTED_PRODUCT_TRANSPORTS,
    CanonicalConversationClient,
    CanonicalSessionClient,
    ConversationInput,
    EventCallback,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    ProductWriteTransport,
    TokenCallback,
    normalize_product_transport,
    require_canonical_conversation_client,
    require_product_write_transport,
)
from .types import ChatMessage, ChatResponse, ConversationStatus


def _assemble_default_write_transport(
    client: CanonicalConversationClient,
    *,
    transport: str,
    provider: Any | None,
) -> ProductWriteTransport:
    if transport != BROWSER_OWNED_PRODUCT_TRANSPORT:
        # normalize_product_transport() makes this unreachable for the current
        # production registry. Keep the branch explicit so future transports
        # cannot accidentally fall through to browser-owned.
        raise ValueError(f"no production transport assembler registered for {transport!r}")

    from .browser_owned_product_transport import BrowserOwnedProductTransport

    return BrowserOwnedProductTransport(client, provider=provider)


class ChatGPTProductRuntime:
    """Implementation-independent ordinary-ChatGPT product runtime.

    PR8.4 separates canonical observation from product mutation. The runtime
    depends on a CanonicalConversationClient plus a ProductWriteTransport
    protocol. The proven browser-owned mechanism is one adapter behind that
    contract; it is no longer the definition of the runtime contract.

    ``provider=`` remains as a compatibility assembly shortcut for PR8.3
    callers. New composition code should inject ``write_transport=`` or use
    ``assemble_product_runtime()``.
    """

    def __init__(
        self,
        client: Any,
        *,
        transport: str = DEFAULT_PRODUCT_TRANSPORT,
        provider: Any | None = None,
        write_transport: ProductWriteTransport | None = None,
    ) -> None:
        self.transport = normalize_product_transport(transport)
        self.client = require_canonical_conversation_client(client)
        self.canonical = self.client

        if write_transport is not None and provider is not None:
            raise ValueError("provider and write_transport are mutually exclusive")

        if write_transport is None:
            write_transport = _assemble_default_write_transport(
                self.canonical,
                transport=self.transport,
                provider=provider,
            )
        else:
            write_transport = require_product_write_transport(write_transport)
            injected_id = write_transport.transport_id.strip().lower()
            if injected_id != self.transport:
                raise ValueError(
                    "write transport identity does not match selected transport: "
                    f"{injected_id!r} != {self.transport!r}"
                )

        self.write_transport = write_transport
        self._transport = write_transport
        # Private PR8.3 compatibility alias for existing tests/diagnostics. The
        # runtime itself never dispatches through this attribute.
        self._writer = getattr(write_transport, "_runtime", write_transport)

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth:
        return self.write_transport.health(conversation)

    readiness = health

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
    ) -> ChatResponse:
        return self.write_transport.send_text(
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
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
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
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
    ) -> ProductRuntimeExecution:
        execution = self.write_transport.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )
        if execution.transport != self.transport:
            raise RuntimeError(
                "write transport returned execution for unexpected transport "
                f"{execution.transport!r}"
            )
        return execution

    def get_status(self, conversation: Any) -> ConversationStatus:
        return self.canonical.get_status(conversation)

    def get_messages(self, conversation: Any, **kwargs: Any) -> list[ChatMessage]:
        return self.canonical.get_messages(conversation, **kwargs)

    def attach_conversation(self, conversation: Any) -> Any:
        return self.canonical.attach_conversation(conversation)

    def governance(self) -> dict[str, Any]:
        transport_governance = dict(self.write_transport.governance())
        transport_governance.update(
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
                "canonical_interface": "CanonicalConversationClient",
                "write_transport_interface": "ProductWriteTransport",
                "runtime_depends_on_concrete_browser_transport": False,
            }
        )
        return transport_governance


def assemble_product_runtime(
    *,
    transport: str = DEFAULT_PRODUCT_TRANSPORT,
    client: Any | None = None,
    provider: Any | None = None,
    write_transport: ProductWriteTransport | None = None,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    client_timeout: int = DEFAULT_TIMEOUT_SECONDS,
    auto_refresh_auth: bool = True,
    persist_refreshed_auth: bool = True,
) -> ChatGPTProductRuntime:
    """Assemble the production ordinary-ChatGPT runtime.

    Assembly never performs interactive browser login and never enables the
    legacy Sentinel/direct-write machinery. Unknown production transports fail
    closed. A custom protocol-conforming transport can be injected explicitly
    for composition/testing, but its identity must still match the selected
    production transport.
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

    canonical = require_canonical_conversation_client(client)

    if write_transport is None:
        write_transport = _assemble_default_write_transport(
            canonical,
            transport=normalized,
            provider=provider,
        )
        provider = None

    return ChatGPTProductRuntime(
        canonical,
        transport=normalized,
        provider=provider,
        write_transport=write_transport,
    )
