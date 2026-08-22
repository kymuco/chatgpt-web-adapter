from __future__ import annotations

import chatgpt_web_adapter as adapter


def test_every_root_public_export_has_exactly_one_surface_tier() -> None:
    classified = adapter.PUBLIC_SURFACE_CLASSIFICATION

    assert set(classified) == set(adapter.__all__)
    assert len(classified) == len(adapter.__all__)

    tier_symbols = []
    for symbols in adapter.PUBLIC_SURFACE_TIERS.values():
        tier_symbols.extend(symbols)
    assert len(tier_symbols) == len(set(tier_symbols))


def test_primary_product_runtime_is_forward_looking_surface() -> None:
    primary = adapter.PublicSurfaceTier.PRIMARY_PRODUCTION

    for symbol in (
        "ChatGPTProductRuntime",
        "assemble_product_runtime",
        "ProductWriteTransport",
        "CanonicalConversationClient",
        "ProductCapabilities",
        "ProductExecutionProvenance",
        "PRODUCT_RUNTIME_CONTRACT_SCHEMA",
        "ProductTransportSupportTier",
        "ProductRuntimeContract",
        "product_runtime_contract",
        "product_transport_support_tier",
    ):
        assert adapter.public_surface_tier(symbol) is primary


def test_legacy_experimental_and_research_surfaces_are_distinct() -> None:
    assert adapter.public_surface_tier("ChatGPTWebClient") is adapter.PublicSurfaceTier.COMPATIBILITY
    assert adapter.public_surface_tier("WebChatClient") is adapter.PublicSurfaceTier.COMPATIBILITY
    assert adapter.public_surface_tier("PayloadBuilder") is adapter.PublicSurfaceTier.EXPERIMENTAL
    assert adapter.public_surface_tier("ApprovalPolicy") is adapter.PublicSurfaceTier.EXPERIMENTAL
    assert adapter.public_surface_tier("SentinelBundleProvider") is adapter.PublicSurfaceTier.RESEARCH_DIAGNOSTIC
    assert adapter.public_surface_tier("BrowserNativeTurnProvider") is adapter.PublicSurfaceTier.RESEARCH_DIAGNOSTIC


def test_shared_types_are_not_misclassified_as_legacy() -> None:
    shared = adapter.PublicSurfaceTier.SHARED_SUPPORT

    for symbol in (
        "ChatConversation",
        "ChatResponse",
        "ConversationRef",
        "AuthStatus",
        "DEFAULT_AUTH_FILE",
    ):
        assert adapter.public_surface_tier(symbol) is shared


def test_unknown_symbol_has_no_implied_support_tier() -> None:
    assert adapter.public_surface_tier("FutureProductTransport") is None
