from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_capabilities import (
    ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)


def test_capability_states_remain_distinct_and_serializable() -> None:
    capabilities = ProductCapabilities.from_entries(
        transport="browser-owned",
        entries=(
            ProductCapability(
                name="available_feature",
                state=CapabilityState.AVAILABLE,
                owner=CapabilityOwner.TRANSPORT,
                evidence="live evidence",
            ),
            ProductCapability(
                name="unsupported_feature",
                state=CapabilityState.UNSUPPORTED,
                owner=CapabilityOwner.PRODUCT,
            ),
            ProductCapability(
                name="unknown_feature",
                state=CapabilityState.UNKNOWN,
                owner=CapabilityOwner.TRANSPORT,
            ),
            ProductCapability(
                name="unimplemented_feature",
                state=CapabilityState.UNIMPLEMENTED,
                owner=CapabilityOwner.CANONICAL,
            ),
        ),
    )

    payload = capabilities.to_dict()

    assert capabilities.product_semantics == ORDINARY_CHATGPT_PRODUCT_SEMANTICS
    assert capabilities.state("available_feature") is CapabilityState.AVAILABLE
    assert capabilities.state("unsupported_feature") is CapabilityState.UNSUPPORTED
    assert capabilities.state("unknown_feature") is CapabilityState.UNKNOWN
    assert capabilities.state("unimplemented_feature") is CapabilityState.UNIMPLEMENTED
    assert payload["capabilities"]["available_feature"]["state"] == "AVAILABLE"
    assert payload["capabilities"]["unsupported_feature"]["state"] == "UNSUPPORTED"
    assert payload["capabilities"]["unknown_feature"]["state"] == "UNKNOWN"
    assert payload["capabilities"]["unimplemented_feature"]["state"] == "UNIMPLEMENTED"


def test_capability_declarations_fail_closed_on_duplicate_names() -> None:
    duplicate = ProductCapability(
        name="text_turns",
        state=CapabilityState.AVAILABLE,
        owner=CapabilityOwner.TRANSPORT,
    )

    with pytest.raises(ValueError, match="duplicate capability"):
        ProductCapabilities.from_entries(
            transport="browser-owned",
            entries=(duplicate, duplicate),
        )


def test_missing_capability_is_not_silently_collapsed_to_unknown() -> None:
    capabilities = ProductCapabilities.from_entries(
        transport="browser-owned",
        entries=(),
    )

    assert capabilities.get("not_declared") is None
    with pytest.raises(KeyError):
        capabilities.state("not_declared")
