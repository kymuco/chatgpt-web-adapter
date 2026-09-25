from __future__ import annotations

import chatgpt_web_adapter as adapter


PRODUCT_RUNTIME_EXPORTS = [
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
    "CanonicalConversationClient",
    "ProductWriteTransport",
    "ChatGPTProductRuntime",
    "ProductRuntimeExecution",
    "ProductRuntimeHealth",
    "assemble_product_runtime",
]


def test_product_runtime_is_public_production_surface() -> None:
    for name in PRODUCT_RUNTIME_EXPORTS:
        assert name in adapter.__all__
        assert hasattr(adapter, name)


def test_product_runtime_transport_default_is_browser_owned() -> None:
    assert adapter.DEFAULT_PRODUCT_TRANSPORT == "browser-owned"
    assert adapter.SUPPORTED_PRODUCT_TRANSPORTS == (
        "browser-owned",
        "browserless-request",
    )
    assert adapter.PRODUCT_RUNTIME_CONTRACT_SCHEMA == 1
    assert adapter.product_transport_support_tier("browser-owned") is (
        adapter.ProductTransportSupportTier.PRODUCTION
    )
    assert adapter.product_transport_support_tier("browserless-request") is (
        adapter.ProductTransportSupportTier.EXPERIMENTAL
    )
    assert adapter.ORDINARY_CHATGPT_PRODUCT_SEMANTICS == "ordinary-chatgpt"


def test_capability_state_contract_is_stable_and_non_boolean() -> None:
    assert [state.value for state in adapter.CapabilityState] == [
        "AVAILABLE",
        "UNSUPPORTED",
        "UNKNOWN",
        "UNIMPLEMENTED",
    ]


def test_transport_support_tier_is_stable_and_separate_from_capabilities() -> None:
    assert [tier.value for tier in adapter.ProductTransportSupportTier] == [
        "PRODUCTION",
        "EXPERIMENTAL",
    ]
