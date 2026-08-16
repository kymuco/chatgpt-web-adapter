from __future__ import annotations

from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .browser_owned_write_runtime import (
    BrowserOwnedProductWriteRuntime,
    BrowserOwnedWriteExecution,
    BrowserOwnedWriteRuntimeHealth,
)
from .product_capabilities import (
    APPROVALS,
    CANONICAL_READBACK,
    CONTINUATION,
    CONVERSATION_ATTACH,
    CONVERSATION_BRANCHING,
    CONVERSATION_READ,
    CONVERSATION_STATUS,
    FILES,
    IMAGES,
    MODEL_PRESERVATION,
    MODEL_SELECTION,
    MULTIMODAL_CONTINUATION,
    NEW_CHAT,
    ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    PRODUCT_CAPABILITY_NAMES,
    PRODUCT_MEMORY_PERSONALIZATION,
    REASONING_PRESERVATION,
    REASONING_SELECTION,
    STREAMING,
    TEMPORARY_CHAT,
    TEXT_TURNS,
    TOOLS_CONNECTORS,
    WEB_SEARCH,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from .product_transport import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    ConversationInput,
    EventCallback,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    TokenCallback,
    require_canonical_conversation_client,
)
from .types import ChatResponse


_BROWSER_OWNED_CAPABILITY_STATES: dict[str, CapabilityState] = {
    TEXT_TURNS: CapabilityState.AVAILABLE,
    NEW_CHAT: CapabilityState.AVAILABLE,
    CONTINUATION: CapabilityState.AVAILABLE,
    CANONICAL_READBACK: CapabilityState.AVAILABLE,
    CONVERSATION_ATTACH: CapabilityState.AVAILABLE,
    CONVERSATION_READ: CapabilityState.AVAILABLE,
    CONVERSATION_STATUS: CapabilityState.AVAILABLE,
    STREAMING: CapabilityState.UNKNOWN,
    IMAGES: CapabilityState.UNIMPLEMENTED,
    FILES: CapabilityState.UNKNOWN,
    WEB_SEARCH: CapabilityState.UNKNOWN,
    TEMPORARY_CHAT: CapabilityState.UNIMPLEMENTED,
    MODEL_SELECTION: CapabilityState.UNKNOWN,
    MODEL_PRESERVATION: CapabilityState.UNKNOWN,
    REASONING_SELECTION: CapabilityState.UNKNOWN,
    REASONING_PRESERVATION: CapabilityState.UNKNOWN,
    PRODUCT_MEMORY_PERSONALIZATION: CapabilityState.UNKNOWN,
    TOOLS_CONNECTORS: CapabilityState.UNKNOWN,
    APPROVALS: CapabilityState.UNIMPLEMENTED,
    CONVERSATION_BRANCHING: CapabilityState.UNKNOWN,
    MULTIMODAL_CONTINUATION: CapabilityState.UNIMPLEMENTED,
}

_BROWSER_OWNED_CAPABILITY_OWNERS: dict[str, CapabilityOwner] = {
    CANONICAL_READBACK: CapabilityOwner.CANONICAL,
    CONVERSATION_ATTACH: CapabilityOwner.CANONICAL,
    CONVERSATION_READ: CapabilityOwner.CANONICAL,
    CONVERSATION_STATUS: CapabilityOwner.CANONICAL,
    PRODUCT_MEMORY_PERSONALIZATION: CapabilityOwner.PRODUCT,
}

_BROWSER_OWNED_CAPABILITY_EVIDENCE: dict[str, str] = {
    TEXT_TURNS: "PR8.3 live ordinary-product text turns",
    NEW_CHAT: "PR8.3 live new-chat production gate",
    CONTINUATION: "PR8.3 live continuation production gate",
    CANONICAL_READBACK: "browser-owned writer requires canonical final assistant readback",
    CONVERSATION_ATTACH: "canonical ChatGPTWebClient attach surface",
    CONVERSATION_READ: "canonical ChatGPTWebClient message-read surface",
    CONVERSATION_STATUS: "canonical ChatGPTWebClient status surface",
    IMAGES: "production ProductWriteTransport currently exposes text turns only",
    TEMPORARY_CHAT: (
        "PR8.7 T13 review: Temporary product semantics and lifecycle are characterized, "
        "but the production ProductWriteTransport has no mode-aware Temporary write route"
    ),
    APPROVALS: "production ProductWriteTransport has no approval continuation surface",
    MULTIMODAL_CONTINUATION: "production ProductWriteTransport currently exposes text turns only",
}


def _build_browser_owned_capabilities() -> ProductCapabilities:
    return ProductCapabilities.from_entries(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        product_semantics=ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
        entries=(
            ProductCapability(
                name=name,
                state=_BROWSER_OWNED_CAPABILITY_STATES[name],
                owner=_BROWSER_OWNED_CAPABILITY_OWNERS.get(
                    name,
                    CapabilityOwner.TRANSPORT,
                ),
                evidence=_BROWSER_OWNED_CAPABILITY_EVIDENCE.get(name),
            )
            for name in PRODUCT_CAPABILITY_NAMES
        ),
    )


_BROWSER_OWNED_CAPABILITIES = _build_browser_owned_capabilities()


class BrowserOwnedProductTransport:
    """Adapter exposing the proven browser-owned runtime through product protocol.

    PR8.4 intentionally wraps rather than rewrites BrowserOwnedProductWriteRuntime.
    PR8.5 adds evidence-backed capability declarations while leaving the proven
    preflight, commit-point recheck, ambiguity classification, and canonical
    readback mechanics untouched.
    """

    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(
        self,
        canonical_client: Any,
        *,
        provider: BrowserNativeTurnProvider | None = None,
    ) -> None:
        self.canonical_client = require_canonical_conversation_client(canonical_client)
        self.provider = provider or BrowserNativeTurnProvider()
        self._runtime = BrowserOwnedProductWriteRuntime(
            self.canonical_client,
            provider=self.provider,
        )

    @staticmethod
    def _health_from_runtime(
        health: BrowserOwnedWriteRuntimeHealth,
    ) -> ProductRuntimeHealth:
        return ProductRuntimeHealth(
            transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
            ready=health.ready,
            reason=health.reason,
            conversation_id=health.conversation_id,
            canonical_status=health.canonical_status,
            canonical_read_checked=health.canonical_read_checked,
            read_plane=health.read_plane,
            session_plane=health.session_plane,
            write_plane=health.write_plane,
            automatic_write_retry=health.automatic_write_retry,
            fallback_transport=None,
            bridge_available=health.bridge_available,
            extension_connected=health.extension_connected,
            runtime_tab_id=health.runtime_tab_id,
            runtime_tab_preexisting=health.runtime_tab_preexisting,
        )

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth:
        return self._health_from_runtime(self._runtime.health(conversation))

    def capabilities(self) -> ProductCapabilities:
        return _BROWSER_OWNED_CAPABILITIES

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
        return self._runtime.send_text(
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
        execution: BrowserOwnedWriteExecution = self._runtime.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=execution.response,
            observation=execution.observation,
        )

    def governance(self) -> dict[str, Any]:
        governance = dict(self._runtime.governance())
        governance["product_semantics"] = ORDINARY_CHATGPT_PRODUCT_SEMANTICS
        return governance
