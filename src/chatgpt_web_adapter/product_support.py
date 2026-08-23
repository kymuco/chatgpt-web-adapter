from __future__ import annotations

from enum import Enum
from typing import Any

PRODUCT_RUNTIME_CONTRACT_SCHEMA = 1


class ProductTransportSupportTier(str, Enum):
    """Stability/support tier for one concrete ChatGPT product transport.

    This is deliberately independent from capability state. A transport can be
    EXPERIMENTAL while an individual capability is AVAILABLE on that transport.
    """

    PRODUCTION = "PRODUCTION"
    EXPERIMENTAL = "EXPERIMENTAL"


_BUILTIN_PRODUCT_TRANSPORT_SUPPORT_TIERS: dict[str, ProductTransportSupportTier] = {
    "browser-owned": ProductTransportSupportTier.PRODUCTION,
    "browserless-request": ProductTransportSupportTier.EXPERIMENTAL,
}


def product_transport_support_tier(transport: Any) -> ProductTransportSupportTier:
    """Return the frozen support tier for a transport identity.

    Unknown/future transport ids are conservative by default: they are
    EXPERIMENTAL until explicitly graduated. This prevents adding a working
    prototype from silently acquiring production support semantics.
    """

    if not isinstance(transport, str) or not transport.strip():
        raise ValueError("transport identity is required")
    normalized = transport.strip().lower()
    return _BUILTIN_PRODUCT_TRANSPORT_SUPPORT_TIERS.get(
        normalized,
        ProductTransportSupportTier.EXPERIMENTAL,
    )
