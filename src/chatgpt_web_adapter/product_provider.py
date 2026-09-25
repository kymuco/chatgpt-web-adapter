from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from .product_capabilities import ProductCapabilities

PRODUCT_PROVIDER_BOUNDARY_SCHEMA = 1
CHATGPT_PRODUCT_PROVIDER_ID = "chatgpt"

_CANONICAL_INTERFACE = "CanonicalConversationClient"
_WRITE_TRANSPORT_INTERFACE = "ProductWriteTransport"


def _required_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip().lower()


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True)
class ProductProviderBoundary:
    """Provider-neutral runtime boundary proven independently of wire shape."""

    provider_id: str
    product_semantics: str
    transport: str
    canonical_interface: str
    write_transport_interface: str
    capability_model: str
    provenance_model: str
    automatic_write_retry: bool
    fallback_transport: str | None
    ambiguous_write_requires_reconciliation: bool
    incremental_observation_is_canonical_finality: bool
    schema: int = field(init=False, default=PRODUCT_PROVIDER_BOUNDARY_SCHEMA)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_id",
            _required_text(self.provider_id, name="provider_id"),
        )
        object.__setattr__(
            self,
            "product_semantics",
            _required_text(self.product_semantics, name="product_semantics"),
        )
        object.__setattr__(
            self,
            "transport",
            _required_text(self.transport, name="transport"),
        )
        if self.canonical_interface != _CANONICAL_INTERFACE:
            raise RuntimeError(
                "provider boundary requires canonical_interface="
                f"{_CANONICAL_INTERFACE!r}"
            )
        if self.write_transport_interface != _WRITE_TRANSPORT_INTERFACE:
            raise RuntimeError(
                "provider boundary requires write_transport_interface="
                f"{_WRITE_TRANSPORT_INTERFACE!r}"
            )
        if self.capability_model != "ProductCapabilities":
            raise RuntimeError("provider boundary requires ProductCapabilities")
        if self.provenance_model != "ProductExecutionProvenance":
            raise RuntimeError("provider boundary requires ProductExecutionProvenance")
        if self.automatic_write_retry is not False:
            raise RuntimeError("provider boundary requires automatic_write_retry=False")
        if self.fallback_transport is not None:
            raise RuntimeError("provider boundary requires fallback_transport=None")
        if self.ambiguous_write_requires_reconciliation is not True:
            raise RuntimeError(
                "provider boundary requires ambiguous_write_requires_reconciliation=True"
            )
        if self.incremental_observation_is_canonical_finality is not False:
            raise RuntimeError(
                "provider boundary requires "
                "incremental_observation_is_canonical_finality=False"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def product_provider_boundary(runtime: Any) -> ProductProviderBoundary:
    """Inspect provider-neutral invariants without assuming a provider wire shape."""

    provider_id = _required_text(
        getattr(runtime, "provider_id", None),
        name="provider_id",
    )
    transport = _required_text(
        getattr(runtime, "transport", None),
        name="transport",
    )

    capabilities_method = getattr(runtime, "capabilities", None)
    governance_method = getattr(runtime, "governance", None)
    if not callable(capabilities_method) or not callable(governance_method):
        raise TypeError("runtime must expose callable capabilities() and governance()")

    capabilities = capabilities_method()
    if not isinstance(capabilities, ProductCapabilities):
        raise TypeError("runtime capabilities() must return ProductCapabilities")
    if capabilities.transport != transport:
        raise RuntimeError(
            "provider boundary capability transport mismatch: "
            f"{capabilities.transport!r} != {transport!r}"
        )

    governance = _require_mapping(governance_method(), name="runtime governance")
    product_semantics = _required_text(
        governance.get("product_semantics"),
        name="product_semantics",
    )
    if capabilities.product_semantics != product_semantics:
        raise RuntimeError(
            "provider boundary product semantics mismatch: "
            f"{capabilities.product_semantics!r} != {product_semantics!r}"
        )

    if governance.get("provider_id") != provider_id:
        raise RuntimeError(
            "provider boundary provider identity mismatch: "
            f"{governance.get('provider_id')!r} != {provider_id!r}"
        )
    if governance.get("transport") != transport:
        raise RuntimeError(
            "provider boundary runtime transport mismatch: "
            f"{governance.get('transport')!r} != {transport!r}"
        )

    write_transport = getattr(runtime, "write_transport", None)
    raw_governance_method = getattr(write_transport, "governance", None)
    if not callable(raw_governance_method):
        raise TypeError(
            "runtime must expose write_transport.governance() for provider validation"
        )
    raw_governance = _require_mapping(
        raw_governance_method(),
        name="write transport governance",
    )
    if raw_governance.get("product_semantics") != product_semantics:
        raise RuntimeError(
            "provider boundary raw transport semantics mismatch: "
            f"{raw_governance.get('product_semantics')!r} != {product_semantics!r}"
        )
    if raw_governance.get("automatic_write_retry") is not False:
        raise RuntimeError("provider boundary requires raw automatic_write_retry=False")
    if "fallback_transport" not in raw_governance:
        raise RuntimeError("provider boundary requires explicit raw fallback_transport=None")
    if raw_governance.get("fallback_transport") is not None:
        raise RuntimeError("provider boundary requires raw fallback_transport=None")

    return ProductProviderBoundary(
        provider_id=provider_id,
        product_semantics=product_semantics,
        transport=transport,
        canonical_interface=governance.get("canonical_interface"),
        write_transport_interface=governance.get("write_transport_interface"),
        capability_model=governance.get("capability_model"),
        provenance_model=governance.get("provenance_model"),
        automatic_write_retry=governance.get("automatic_write_retry"),
        fallback_transport=governance.get("fallback_transport"),
        ambiguous_write_requires_reconciliation=governance.get(
            "ambiguous_write_requires_reconciliation"
        ),
        incremental_observation_is_canonical_finality=governance.get(
            "incremental_observation_is_canonical_finality"
        ),
    )
