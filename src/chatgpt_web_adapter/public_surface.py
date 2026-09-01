from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class PublicSurfaceTier(str, Enum):
    PRIMARY_PRODUCTION = "PRIMARY_PRODUCTION"
    SHARED_SUPPORT = "SHARED_SUPPORT"
    COMPATIBILITY = "COMPATIBILITY"
    EXPERIMENTAL = "EXPERIMENTAL"
    RESEARCH_DIAGNOSTIC = "RESEARCH_DIAGNOSTIC"


PRIMARY_PRODUCT_RUNTIME_EXPORTS: tuple[str, ...] = (
    "BROWSER_OWNED_PRODUCT_TRANSPORT",
    "DEFAULT_PRODUCT_TRANSPORT",
    "SUPPORTED_PRODUCT_TRANSPORTS",
    "PRODUCT_RUNTIME_CONTRACT_SCHEMA",
    "ProductTransportSupportTier",
    "product_transport_support_tier",
    "ProductRuntimeContract",
    "product_runtime_contract",
    "ORDINARY_CHATGPT_PRODUCT_SEMANTICS",
    "PRODUCT_CAPABILITY_NAMES",
    "CapabilityState",
    "CapabilityOwner",
    "ProductCapability",
    "ProductCapabilities",
    "CompletionSource",
    "ProductCompletionProvenance",
    "ProductIdentityProvenance",
    "ProductExecutionProvenance",
    "ProductObservationKind",
    "ProductObservationPhase",
    "ProductActivityObservation",
    "ProductSourceObservation",
    "ProductCitationObservation",
    "ProductRequiredActionObservation",
    "StructuredProductObservation",
    "CanonicalConversationClient",
    "ProductWriteTransport",
    "ChatGPTProductRuntime",
    "ProductRuntimeExecution",
    "ProductRuntimeHealth",
    "assemble_product_runtime",
)

SHARED_SUPPORT_EXPORTS: tuple[str, ...] = (
    "ChatConversation",
    "AttachedConversation",
    "ChatMessage",
    "ConversationStatus",
    "ChatResponse",
    "AuthData",
    "ConversationRef",
    "WaitResult",
    "MediaItem",
    "MediaSource",
    "errors",
    "WebChatAdapterError",
    "AuthError",
    "ConversationTimeoutError",
    "MediaError",
    "PayloadValidationError",
    "RequestError",
    "AuthStatus",
    "AuthRefreshResult",
    "BrowserLoginResult",
    "DEFAULT_AUTH_FILE",
    "browser_login",
    "default_browser_profile_dir",
    "get_auth_status",
    "load_auth_data",
    "PublicSurfaceTier",
    "PUBLIC_SURFACE_TIERS",
    "PUBLIC_SURFACE_CLASSIFICATION",
    "public_surface_tier",
)

COMPATIBILITY_WEB_CLIENT_EXPORTS: tuple[str, ...] = (
    "ChatGPTWebClient",
    "WebChatClient",
    "PendingApproval",
    "ChatMetrics",
    "ChatRequestDiagnostics",
    "DEFAULT_MODEL",
)

EXPERIMENTAL_WEB_BACKEND_EXPORTS: tuple[str, ...] = (
    "ApprovalDecision",
    "ApprovalDeniedError",
    "ApprovalEvent",
    "ApprovalPolicy",
    "ApprovalResult",
    "ApprovalRound",
    "RequiredAction",
    "find_required_action",
    "PayloadBuilder",
    "validate_payload",
    "PrepareResult",
    "prepare_text_turn",
)

RESEARCH_DIAGNOSTIC_EXPORTS: tuple[str, ...] = (
    "FinalizedSentinelBundle",
    "OBSERVED_FINALIZE_REQUEST_KEYS",
    "OBSERVED_FINALIZE_RESPONSE_KEYS",
    "SentinelBundleProvider",
    "SentinelChallengeContext",
    "SentinelChallengeEvidence",
    "SentinelChallengeProvider",
    "SentinelPrepareProbeResult",
    "ZendriverSentinelBundleProvider",
    "probe_sentinel_requirements_prepare",
    "BROWSER_NATIVE_EXTENSION_ID",
    "BrowserNativeBridgeStatus",
    "BrowserNativeInstallResult",
    "BrowserNativeTurnProvider",
    "BrowserNativeTurnResult",
    "browser_native_extension_dir",
    "install_native_messaging_host",
)

_PUBLIC_SURFACE_TIERS = {
    PublicSurfaceTier.PRIMARY_PRODUCTION: PRIMARY_PRODUCT_RUNTIME_EXPORTS,
    PublicSurfaceTier.SHARED_SUPPORT: SHARED_SUPPORT_EXPORTS,
    PublicSurfaceTier.COMPATIBILITY: COMPATIBILITY_WEB_CLIENT_EXPORTS,
    PublicSurfaceTier.EXPERIMENTAL: EXPERIMENTAL_WEB_BACKEND_EXPORTS,
    PublicSurfaceTier.RESEARCH_DIAGNOSTIC: RESEARCH_DIAGNOSTIC_EXPORTS,
}

PUBLIC_SURFACE_TIERS: Mapping[PublicSurfaceTier, tuple[str, ...]] = MappingProxyType(
    _PUBLIC_SURFACE_TIERS
)
PUBLIC_SURFACE_CLASSIFICATION: Mapping[str, PublicSurfaceTier] = MappingProxyType(
    {
        symbol: tier
        for tier, symbols in _PUBLIC_SURFACE_TIERS.items()
        for symbol in symbols
    }
)


def public_surface_tier(symbol: str) -> PublicSurfaceTier | None:
    """Return the support tier for a classified root-package symbol."""

    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    return PUBLIC_SURFACE_CLASSIFICATION.get(symbol)
