from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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

_CANONICAL_INTERFACE = "CanonicalConversationClient"
_WRITE_TRANSPORT_INTERFACE = "ProductWriteTransport"
_INCREMENTAL_FINALITY_KEY = "incremental_observation_is_canonical_finality"
_LEGACY_CANONICAL_FINALITY_KEY = "streaming_canonical_finality_authoritative"


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


def _require_none(governance: Mapping[str, Any], name: str) -> None:
    if name not in governance:
        raise RuntimeError(
            f"product runtime contract requires explicit {name}=None; observed missing"
        )
    value = governance[name]
    if value is not None:
        raise RuntimeError(
            f"product runtime contract requires {name}=None; observed {value!r}"
        )
    return None


def _require_value(
    governance: Mapping[str, Any],
    name: str,
    expected: Any,
) -> Any:
    value = governance.get(name)
    if value != expected:
        raise RuntimeError(
            f"product runtime contract requires {name}={expected!r}; observed {value!r}"
        )
    return value


def _require_incremental_observation_not_final(
    governance: Mapping[str, Any],
) -> bool:
    """Require explicit evidence that incremental observation is not finality.

    Schema 1 accepts the direct PR9 governance key. For the already-released 0.2
    browser-owned implementation, the older explicit statement that canonical
    finality is authoritative is accepted as equivalent evidence. Missing evidence
    and contradictory direct declarations both fail closed.
    """

    if _INCREMENTAL_FINALITY_KEY in governance:
        return _require_false(governance, _INCREMENTAL_FINALITY_KEY)
    if governance.get(_LEGACY_CANONICAL_FINALITY_KEY) is True:
        return False
    raise RuntimeError(
        "product runtime contract requires explicit non-incremental finality evidence; "
        f"expected {_INCREMENTAL_FINALITY_KEY}=False or "
        f"{_LEGACY_CANONICAL_FINALITY_KEY}=True"
    )


def build_product_runtime_contract(
    *,
    transport: str,
    capabilities: ProductCapabilities,
    governance: Mapping[str, Any],
) -> ProductRuntimeContract:
    """Build and validate the schema-1 runtime contract for one runtime instance."""

    if not isinstance(capabilities, ProductCapabilities):
        raise TypeError("capabilities must be ProductCapabilities")
    if not isinstance(governance, Mapping):
        raise TypeError("governance must be a mapping")
    if not isinstance(transport, str) or not transport.strip():
        raise ValueError("runtime transport identity is required")

    normalized_transport = transport.strip().lower()
    expected_support_tier = product_transport_support_tier(normalized_transport)

    if capabilities.transport != normalized_transport:
        raise RuntimeError(
            "runtime contract capability transport mismatch: "
            f"{capabilities.transport!r} != {normalized_transport!r}"
        )
    if capabilities.runtime_contract_schema != PRODUCT_RUNTIME_CONTRACT_SCHEMA:
        raise RuntimeError(
            "runtime contract capability schema mismatch: "
            f"{capabilities.runtime_contract_schema!r} != "
            f"{PRODUCT_RUNTIME_CONTRACT_SCHEMA!r}"
        )
    if capabilities.transport_support_tier != expected_support_tier:
        raise RuntimeError(
            "runtime contract capability support-tier mismatch: "
            f"{capabilities.transport_support_tier!r} != {expected_support_tier!r}"
        )
    if capabilities.product_semantics != ORDINARY_CHATGPT_PRODUCT_SEMANTICS:
        raise RuntimeError(
            "ChatGPTProductRuntime contract requires ordinary ChatGPT product semantics"
        )

    _require_value(governance, "transport", normalized_transport)
    _require_value(
        governance,
        "product_semantics",
        ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    )
    canonical_interface = _require_value(
        governance,
        "canonical_interface",
        _CANONICAL_INTERFACE,
    )
    write_transport_interface = _require_value(
        governance,
        "write_transport_interface",
        _WRITE_TRANSPORT_INTERFACE,
    )

    automatic_write_retry = _require_false(governance, "automatic_write_retry")
    fallback_transport = _require_none(governance, "fallback_transport")
    _require_false(governance, "legacy_direct_write_fallback")
    ambiguous_write_requires_reconciliation = _require_true(
        governance,
        "ambiguous_write_requires_reconciliation",
    )
    incremental_observation_is_canonical_finality = (
        _require_incremental_observation_not_final(governance)
    )
    browser_implementation_required_by_caller = _require_false(
        governance,
        "runtime_depends_on_concrete_browser_transport",
    )

    return ProductRuntimeContract(
        schema=PRODUCT_RUNTIME_CONTRACT_SCHEMA,
        product_semantics=capabilities.product_semantics,
        transport=normalized_transport,
        transport_support_tier=expected_support_tier,
        canonical_interface=canonical_interface,
        write_transport_interface=write_transport_interface,
        operations=STABLE_PRODUCT_RUNTIME_OPERATIONS,
        capability_states=tuple(state.value for state in CapabilityState),
        automatic_write_retry=automatic_write_retry,
        fallback_transport=fallback_transport,
        ambiguous_write_requires_reconciliation=(
            ambiguous_write_requires_reconciliation
        ),
        incremental_observation_is_canonical_finality=(
            incremental_observation_is_canonical_finality
        ),
        browser_implementation_required_by_caller=(
            browser_implementation_required_by_caller
        ),
    )


def product_runtime_contract(runtime: Any) -> ProductRuntimeContract:
    """Inspect the frozen public contract of a ChatGPTProductRuntime-like object.

    The inspector intentionally lives outside the runtime class so PR9.0 can add
    a versioned contract without changing the already-released 0.2 runtime method
    surface. Future transports are validated against the same upper contract.
    """

    transport = getattr(runtime, "transport", None)
    capabilities = getattr(runtime, "capabilities", None)
    governance = getattr(runtime, "governance", None)
    if not isinstance(transport, str) or not transport.strip():
        raise TypeError("runtime must expose a non-empty transport identity")
    if not callable(capabilities) or not callable(governance):
        raise TypeError("runtime must expose callable capabilities() and governance()")

    missing_operations = tuple(
        name
        for name in STABLE_PRODUCT_RUNTIME_OPERATIONS
        if not callable(getattr(runtime, name, None))
    )
    if missing_operations:
        missing = ", ".join(missing_operations)
        raise TypeError(
            "runtime does not implement the frozen schema-1 operation surface: "
            f"{missing}"
        )

    governance_payload = governance()
    if not isinstance(governance_payload, Mapping):
        raise TypeError("runtime governance() must return a mapping")

    return build_product_runtime_contract(
        transport=transport,
        capabilities=capabilities(),
        governance=governance_payload,
    )
