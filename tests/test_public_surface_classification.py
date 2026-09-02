from __future__ import annotations

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter import (
    product_observations,
    product_submission,
    product_ui_liveness,
)


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
        "SubmissionEvidenceSource",
        "ProductSubmissionProvenance",
        "ProductSubmissionAck",
        "BrowserUILivenessState",
        "BrowserUILivenessObservation",
        "PRODUCT_RUNTIME_CONTRACT_SCHEMA",
        "ProductTransportSupportTier",
        "ProductRuntimeContract",
        "product_runtime_contract",
        "product_transport_support_tier",
        "ProductObservationKind",
        "ProductObservationPhase",
        "ProductActivityObservation",
        "ProductSourceObservation",
        "ProductCitationObservation",
        "ProductRequiredActionObservation",
        "StructuredProductObservation",
    ):
        assert adapter.public_surface_tier(symbol) is primary


def test_pr114_submission_value_types_are_bound_at_root() -> None:
    assert adapter.SubmissionEvidenceSource is product_submission.SubmissionEvidenceSource
    assert adapter.ProductSubmissionProvenance is product_submission.ProductSubmissionProvenance
    assert adapter.ProductSubmissionAck is product_submission.ProductSubmissionAck
    assert callable(getattr(adapter.ChatGPTProductRuntime, "submit", None))
    assert callable(getattr(adapter.ChatGPTProductRuntime, "await_final", None))
    assert callable(
        getattr(adapter.ChatGPTProductRuntime, "submission_lifecycle_snapshot", None)
    )


def test_pr115_ui_liveness_value_types_and_runtime_method_are_bound_at_root() -> None:
    assert adapter.BrowserUILivenessState is product_ui_liveness.BrowserUILivenessState
    assert (
        adapter.BrowserUILivenessObservation
        is product_ui_liveness.BrowserUILivenessObservation
    )
    assert callable(getattr(adapter.ChatGPTProductRuntime, "observe_ui_liveness", None))


def test_pr93_observation_value_types_are_bound_at_root_without_promoting_collector() -> None:
    assert adapter.ProductObservationKind is product_observations.ProductObservationKind
    assert adapter.ProductObservationPhase is product_observations.ProductObservationPhase
    assert adapter.ProductActivityObservation is product_observations.ProductActivityObservation
    assert adapter.ProductSourceObservation is product_observations.ProductSourceObservation
    assert adapter.ProductCitationObservation is product_observations.ProductCitationObservation
    assert (
        adapter.ProductRequiredActionObservation
        is product_observations.ProductRequiredActionObservation
    )
    assert adapter.StructuredProductObservation is product_observations.StructuredProductObservation
    assert "ProductObservationCollector" not in adapter.__all__
    assert adapter.public_surface_tier("ProductObservationCollector") is None


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
        "MediaItem",
        "MediaSource",
        "AuthStatus",
        "DEFAULT_AUTH_FILE",
    ):
        assert adapter.public_surface_tier(symbol) is shared


def test_unknown_symbol_has_no_implied_support_tier() -> None:
    assert adapter.public_surface_tier("FutureProductTransport") is None
