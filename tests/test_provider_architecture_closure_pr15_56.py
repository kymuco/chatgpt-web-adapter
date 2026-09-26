from __future__ import annotations

import inspect

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.deepseek_web import (
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_WEB_TRANSPORT,
    ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS,
    DeepSeekWebRuntime,
    DeepSeekWebTransport,
)
from chatgpt_web_adapter.gemini_web import (
    GEMINI_PROVIDER_ID,
    GEMINI_WEB_TRANSPORT,
    ORDINARY_GEMINI_PRODUCT_SEMANTICS,
    GeminiWebRuntime,
    GeminiWebTransport,
)
from chatgpt_web_adapter.product_support import ProductTransportSupportTier


def test_schema2_boundary_is_shared_by_both_page_owned_providers() -> None:
    deepseek = adapter.product_provider_boundary(
        DeepSeekWebRuntime(DeepSeekWebTransport(provider=object()))
    )
    gemini = adapter.product_provider_boundary(
        GeminiWebRuntime(GeminiWebTransport(provider=object()))
    )

    assert deepseek.schema == gemini.schema == adapter.PRODUCT_PROVIDER_BOUNDARY_SCHEMA == 2
    assert deepseek.provider_id == DEEPSEEK_PROVIDER_ID == "deepseek"
    assert gemini.provider_id == GEMINI_PROVIDER_ID == "gemini"
    assert deepseek.product_semantics == ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS
    assert gemini.product_semantics == ORDINARY_GEMINI_PRODUCT_SEMANTICS
    assert deepseek.transport == DEEPSEEK_WEB_TRANSPORT == "deepseek-web"
    assert gemini.transport == GEMINI_WEB_TRANSPORT == "gemini-web"

    for boundary in (deepseek, gemini):
        assert boundary.canonical_interface is None
        assert boundary.canonical_readback_required is False
        assert boundary.write_transport_interface == "ProductWriteTransport"
        assert boundary.capability_model == "ProductCapabilities"
        assert boundary.provenance_model == "ProductExecutionProvenance"
        assert boundary.automatic_write_retry is False
        assert boundary.fallback_transport is None
        assert boundary.ambiguous_write_requires_reconciliation is True
        assert boundary.incremental_observation_is_canonical_finality is False


def test_page_owned_provider_transports_remain_experimental() -> None:
    deepseek = DeepSeekWebTransport(provider=object()).capabilities()
    gemini = GeminiWebTransport(provider=object()).capabilities()

    assert deepseek.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL
    assert gemini.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL


def test_provider_neutral_boundary_is_primary_public_surface() -> None:
    assert (
        adapter.public_surface_tier("ProductProviderBoundary")
        is adapter.PublicSurfaceTier.PRIMARY_PRODUCTION
    )
    assert (
        adapter.public_surface_tier("product_provider_boundary")
        is adapter.PublicSurfaceTier.PRIMARY_PRODUCTION
    )
    assert (
        adapter.public_surface_tier("PRODUCT_PROVIDER_BOUNDARY_SCHEMA")
        is adapter.PublicSurfaceTier.PRIMARY_PRODUCTION
    )


def test_provider_specific_web_runtimes_remain_module_only() -> None:
    provider_specific_symbols = (
        "DeepSeekBrowserTurnProvider",
        "DeepSeekWebTransport",
        "DeepSeekWebRuntime",
        "DeepSeekWebWriteOutcomeAmbiguousError",
        "GeminiBrowserTurnProvider",
        "GeminiWebTransport",
        "GeminiWebRuntime",
        "GeminiWebWriteOutcomeAmbiguousError",
    )

    for symbol in provider_specific_symbols:
        assert not hasattr(adapter, symbol)
        assert adapter.public_surface_tier(symbol) is None


def test_neutral_boundary_and_provenance_have_no_page_provider_special_cases() -> None:
    from chatgpt_web_adapter import product_provider, product_provenance

    provider_source = inspect.getsource(product_provider).lower()
    provenance_source = inspect.getsource(product_provenance).lower()

    for provider_name in ("deepseek", "gemini"):
        assert provider_name not in provider_source
        assert provider_name not in provenance_source

    assert "ordinary-chatgpt" not in provenance_source


def test_non_chatgpt_capabilities_declare_semantics_explicitly() -> None:
    from chatgpt_web_adapter import deepseek_web, gemini_web

    deepseek_source = inspect.getsource(deepseek_web)
    gemini_source = inspect.getsource(gemini_web)

    assert "product_semantics=ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS" in deepseek_source
    assert "product_semantics=ORDINARY_GEMINI_PRODUCT_SEMANTICS" in gemini_source


def test_page_owned_providers_share_post_write_uncertainty_invariant() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    extension = root / "src" / "chatgpt_web_adapter" / "browser_native_extension"

    workers = {
        "DEEPSEEK": (
            extension / "service_worker_deepseek_provider.js"
        ).read_text(encoding="utf-8"),
        "GEMINI": (
            extension / "service_worker_gemini_provider.js"
        ).read_text(encoding="utf-8"),
    }

    for prefix, worker in workers.items():
        assert f"{prefix}_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED" in worker
        assert "POST_SUBMIT_OBSERVATION_FAILED" in worker
        assert "automaticWriteRetry: false" in worker
        assert worker.count("SubmitOnce(") >= 1
        assert "PostSubmitAmbiguousError" in worker
