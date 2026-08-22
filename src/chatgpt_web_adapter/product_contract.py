from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .product_capabilities import (
    ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    CapabilityState,
    ProductCapabilities,
)
from .product_support import (
    PRODUCT_RUNTIME_CONTRACT_SCHEMA,
    ProductTransportSupportTier,
    product_transport_support_tier,
)

STABLE_PRODUCT_RUNTIME_OPERATIONS: tuple[str, ...] = (
    "health",
    "readiness",
    "capabilities",
    "contract",
    "send",
    "send_text",
    "send_text_observed",
    "get_status",
    "get_messages",
    "attach_conversation",
    "end_temporary_chat",
    "temporary_lifecycle_snapshot",
    "governance",
)


@dataclass(frozen=True)
class ProductRuntimeContract:
    """Versioned standalone SDK contract above concrete product transports."""

    schema: int
    product_semantics: str
    transport: str
    transport_support_tier: ProductTransportSupportTier
    canonical_interface: str
    write_transport_interface: str
    operations: tuple[str, ...]
    capability_states: tuple[str, ...]
    automatic_write_retry: bool
    fallback_transport: str | None
    ambiguous_write_requires_reconciliation: bool
    incremental_observation_is_canonical_finality: bool
    browser_implementation_required_by_caller: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "runtime": "ChatGPTProductRuntime",
            "product_semantics": self.product_semantics,
            "transport": self.transport,
            "transport_support_tier": self.transport_support_tier.value,
            "interfaces": {
                "canonical": self.canonical_interface,
                "write_transport": self.write_transport_interface,
            },
            "operations": list(self.operations),
            "capability_states": list(self.capability_states),
            "invariants": {
                "automatic_write_retry": self.automatic_write_retry,
                "fallback_transport": self.fallback_transport,
                "ambiguous_write_requires_reconciliation": (
                    self.ambiguous_write_requires_reconciliation
                ),
                "incremental_observation_is_canonical_finality": (
                    self.incremental_observation_is_canonical_finality
                ),
                "browser_implementation_required_by_caller": (
                    self.browser_implementation_required_by_caller
                ),
            },
        }


def _require_false(governance: Mapping[str, Any], name: str) -> bool:
    value = governance.get(name)
    if value is not False:
        raise RuntimeError(
            f"product runtime contract requires {name}=False; observed {value!r}"
        )
    return False


def _require_true(governance: Mapping[str, Any], name: str) -> bool:
    value = governance.get(name)
    if value is not True:
        raise RuntimeError(
            f"product runtime contract requires {name}=True; observed {value!r}"
        )
    return True


def build_product_runtime_contract(
    *,
    transport: str,
    capabilities: ProductCapabilities,
    governance: Mapping[str, Any],
) -> ProductRuntimeContract:
    """Build and validate the schema-1 runtime contract for one runtime instance."""

    if not isinstance(capabilities, ProductCapabilities):
        raise TypeError("capabilities must be ProductCapabilities")
    normalized_transport = transport.strip().lower()
    if capabilities.transport != normalized_transport:
        raise RuntimeError(
            "runtime contract capability transport mismatch: "
            f"{capabilities.transport!r} != {normalized_transport!r}"
        )
    if capabilities.product_semantics != ORDINARY_CHATGPT_PRODUCT_SEMANTICS:
        raise RuntimeError(
            "ChatGPTProductRuntime contract requires ordinary ChatGPT product semantics"
        )

    automatic_write_retry = _require_false(governance, "automatic_write_retry")
    if governance.get("fallback_transport") is not None:
        raise RuntimeError(
            "product runtime contract requires fallback_transport=None; observed "
            f"{governance.get('fallback_transport')!r}"
        )
    _require_false(governance, "legacy_direct_write_fallback")
    ambiguous_write_requires_reconciliation = _require_true(
        governance,
        "ambiguous_write_requires_reconciliation",
    )
    browser_implementation_required_by_caller = _require_false(
        governance,
        "runtime_depends_on_concrete_browser_transport",
    )

    return ProductRuntimeContract(
        schema=PRODUCT_RUNTIME_CONTRACT_SCHEMA,
        product_semantics=capabilities.product_semantics,
        transport=normalized_transport,
        transport_support_tier=product_transport_support_tier(normalized_transport),
        canonical_interface=str(
            governance.get("canonical_interface") or "CanonicalConversationClient"
        ),
        write_transport_interface=str(
            governance.get("write_transport_interface") or "ProductWriteTransport"
        ),
        operations=STABLE_PRODUCT_RUNTIME_OPERATIONS,
        capability_states=tuple(state.value for state in CapabilityState),
        automatic_write_retry=automatic_write_retry,
        fallback_transport=None,
        ambiguous_write_requires_reconciliation=(
            ambiguous_write_requires_reconciliation
        ),
        incremental_observation_is_canonical_finality=False,
        browser_implementation_required_by_caller=(
            browser_implementation_required_by_caller
        ),
    )
