from __future__ import annotations

from typing import Any

from .browser_authority_lease import (
    BrowserAuthorityPolicy,
    resolve_browser_authority_policy,
)
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
    STREAMING: CapabilityState.AVAILABLE,
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
    STREAMING: (
        "PR8.9.3 production live gate: 33 revision-safe text events reached "
        "ChatGPTProductRuntime.on_event before browser write completion; first text "
        "led write completion by 16472 ms; canonical finalization reconciled EXACT_MATCH"
    ),
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


def _authority_override_kwargs(
    *,
    browser_authority_policy: BrowserAuthorityPolicy | str | None,
    browser_authority_ttl_ms: int | None,
) -> dict[str, Any]:
    if browser_authority_policy is None and browser_authority_ttl_ms is None:
        return {}
    return {
        "browser_authority_policy": browser_authority_policy,
        "browser_authority_ttl_ms": browser_authority_ttl_ms,
    }


class BrowserOwnedProductTransport:
    """Adapter exposing the proven browser-owned runtime through product protocol.

    PR8.4 intentionally wraps rather than rewrites BrowserOwnedProductWriteRuntime.
    PR8.5 adds evidence-backed capability declarations while leaving the proven
    preflight, commit-point recheck, ambiguity classification, and canonical
    readback mechanics untouched. PR8.8 exposes Browser Authority resource-lifetime
    policy at this transport boundary without changing the generic transport protocol.
    PR8.9 graduates revision-safe `on_event` streaming while keeping canonical
    readback authoritative for final text and reconciliation.
    """

    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(
        self,
        canonical_client: Any,
        *,
        provider: BrowserNativeTurnProvider | None = None,
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> None:
        self.canonical_client = require_canonical_conversation_client(canonical_client)
        self.provider = provider or BrowserNativeTurnProvider()
        self._browser_authority_runtime_policy = browser_authority_policy
        self._browser_authority_runtime_ttl_ms = browser_authority_ttl_ms
        self._browser_authority_default_resolution = resolve_browser_authority_policy(
            runtime_policy=browser_authority_policy,
            runtime_ttl_ms=browser_authority_ttl_ms,
        )

        runtime_kwargs: dict[str, Any] = {"provider": self.provider}
        runtime_kwargs.update(
            _authority_override_kwargs(
                browser_authority_policy=browser_authority_policy,
                browser_authority_ttl_ms=browser_authority_ttl_ms,
            )
        )
        self._runtime = BrowserOwnedProductWriteRuntime(
            self.canonical_client,
            **runtime_kwargs,
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
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> ChatResponse:
        authority_kwargs = _authority_override_kwargs(
            browser_authority_policy=browser_authority_policy,
            browser_authority_ttl_ms=browser_authority_ttl_ms,
        )
        return self._runtime.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
            **authority_kwargs,
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
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> ProductRuntimeExecution:
        authority_kwargs = _authority_override_kwargs(
            browser_authority_policy=browser_authority_policy,
            browser_authority_ttl_ms=browser_authority_ttl_ms,
        )
        execution: BrowserOwnedWriteExecution = self._runtime.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
            **authority_kwargs,
        )
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=execution.response,
            observation=execution.observation,
        )

    def governance(self) -> dict[str, Any]:
        governance = dict(self._runtime.governance())
        resolution = self._browser_authority_default_resolution
        governance.update(
            {
                "product_semantics": ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
                "browser_authority_product_runtime_policy_supported": True,
                "browser_authority_runtime_default_configurable": True,
                "browser_authority_per_turn_override_configurable": True,
                "browser_authority_policy_configuration_surface": "PRODUCT_RUNTIME",
                "browser_authority_policy_contract_scope": "RESOURCE_LIFECYCLE_ONLY",
                "browser_authority_effective_runtime_default_policy": resolution.policy.value,
                "browser_authority_effective_runtime_default_ttl_ms": resolution.ttl_ms,
                "browser_authority_runtime_default_policy_source": resolution.policy_source.value,
                "browser_authority_configured_runtime_ttl_ms": self._browser_authority_runtime_ttl_ms,
                "browser_authority_policy_exposes_runtime_tab_identity": False,
                "browser_authority_policy_requires_native_messaging_details": False,
                "streaming_supported": True,
                "streaming_contract_version": 1,
                "streaming_event_surface": "on_event",
                "streaming_event_types": [
                    "assistant_text_snapshot",
                    "assistant_text_delta",
                    "assistant_text_revision",
                    "canonical_text_finalized",
                ],
                "streaming_source": "CDP_NETWORK_STREAM_RESOURCE_CONTENT",
                "streaming_delivery": "REVISION_SAFE_EVENT_STREAM",
                "streaming_canonical_finality": "BROWSERLESS_CANONICAL_HTTP",
                "streaming_canonical_finality_authoritative": True,
                "streaming_reconciliation_states": [
                    "EXACT_MATCH",
                    "CANONICAL_EXTENDS_STREAM",
                    "STREAM_REVISED_BY_CANONICAL",
                    "STREAM_INCOMPLETE",
                    "UNAVAILABLE",
                ],
                "streaming_legacy_on_token_semantics": "FINAL_ONLY",
                "streaming_raw_sse_exported": False,
                "streaming_automatic_write_retry": False,
            }
        )
        return governance
