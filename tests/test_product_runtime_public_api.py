from __future__ import annotations

import chatgpt_web_adapter as adapter


PRODUCT_RUNTIME_EXPORTS = [
    "BROWSER_OWNED_PRODUCT_TRANSPORT",
    "DEFAULT_PRODUCT_TRANSPORT",
    "SUPPORTED_PRODUCT_TRANSPORTS",
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
    assert adapter.SUPPORTED_PRODUCT_TRANSPORTS == ("browser-owned",)
