from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .product_support import (
    PRODUCT_RUNTIME_CONTRACT_SCHEMA,
    ProductTransportSupportTier,
    normalize_product_transport_support_tier,
    product_transport_support_tier,
)

ORDINARY_CHATGPT_PRODUCT_SEMANTICS = "ordinary-chatgpt"

TEXT_TURNS = "text_turns"
NEW_CHAT = "new_chat"
CONTINUATION = "continuation"
CANONICAL_READBACK = "canonical_readback"
CONVERSATION_ATTACH = "conversation_attach"
CONVERSATION_READ = "conversation_read"
CONVERSATION_STATUS = "conversation_status"
STREAMING = "streaming"
IMAGES = "images"
FILES = "files"
WEB_SEARCH = "web_search"
TEMPORARY_CHAT = "temporary_chat"
MODEL_SELECTION = "model_selection"
MODEL_PRESERVATION = "model_preservation"
REASONING_SELECTION = "reasoning_selection"
REASONING_PRESERVATION = "reasoning_preservation"
PRODUCT_MEMORY_PERSONALIZATION = "product_memory_personalization"
TOOLS_CONNECTORS = "tools_connectors"
APPROVALS = "approvals"
CONVERSATION_BRANCHING = "conversation_branching"
MULTIMODAL_CONTINUATION = "multimodal_continuation"

PRODUCT_CAPABILITY_NAMES: tuple[str, ...] = (
    TEXT_TURNS,
    NEW_CHAT,
    CONTINUATION,
    CANONICAL_READBACK,
    CONVERSATION_ATTACH,
    CONVERSATION_READ,
    CONVERSATION_STATUS,
    STREAMING,
    IMAGES,
    FILES,
    WEB_SEARCH,
    TEMPORARY_CHAT,
    MODEL_SELECTION,
    MODEL_PRESERVATION,
    REASONING_SELECTION,
    REASONING_PRESERVATION,
    PRODUCT_MEMORY_PERSONALIZATION,
    TOOLS_CONNECTORS,
    APPROVALS,
    CONVERSATION_BRANCHING,
    MULTIMODAL_CONTINUATION,
)


class CapabilityState(str, Enum):
    """Evidence state for one runtime capability.

    AVAILABLE means implemented and evidence-backed on the declared runtime.
    UNSUPPORTED means the relevant contract is known not to provide it.
    UNKNOWN means the capability has not been characterized strongly enough.
    UNIMPLEMENTED means the product/transport may expose the concept, but this
    runtime does not currently implement it.
    """

    AVAILABLE = "AVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    UNIMPLEMENTED = "UNIMPLEMENTED"


class CapabilityOwner(str, Enum):
    """Layer that owns or constrains the declared capability."""

    TRANSPORT = "TRANSPORT"
    CANONICAL = "CANONICAL"
    PRODUCT = "PRODUCT"


def _required_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("capability name is required")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class ProductCapability:
    name: str
    state: CapabilityState
    owner: CapabilityOwner
    evidence: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_name(self.name))
        if not isinstance(self.state, CapabilityState):
            object.__setattr__(self, "state", CapabilityState(self.state))
        if not isinstance(self.owner, CapabilityOwner):
            object.__setattr__(self, "owner", CapabilityOwner(self.owner))
        object.__setattr__(self, "evidence", _optional_text(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "owner": self.owner.value,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ProductCapabilities:
    transport: str
    product_semantics: str
    entries: tuple[ProductCapability, ...]
    runtime_contract_schema: int = PRODUCT_RUNTIME_CONTRACT_SCHEMA
    transport_support_tier: ProductTransportSupportTier | str | None = None

    def __post_init__(self) -> None:
        transport = _required_name(self.transport).lower()
        semantics = _required_name(self.product_semantics).lower()
        entries = tuple(self.entries)
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, ProductCapability):
                raise TypeError("capability entries must be ProductCapability instances")
            if entry.name in seen:
                raise ValueError(f"duplicate capability declaration: {entry.name}")
            seen.add(entry.name)

        schema = int(self.runtime_contract_schema)
        if schema != PRODUCT_RUNTIME_CONTRACT_SCHEMA:
            raise ValueError(
                "unsupported product runtime contract schema "
                f"{schema}; expected {PRODUCT_RUNTIME_CONTRACT_SCHEMA}"
            )
        support_tier = (
            product_transport_support_tier(transport)
            if self.transport_support_tier is None
            else normalize_product_transport_support_tier(self.transport_support_tier)
        )

        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "product_semantics", semantics)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "runtime_contract_schema", schema)
        object.__setattr__(self, "transport_support_tier", support_tier)

    @classmethod
    def from_entries(
        cls,
        *,
        transport: str,
        entries: Iterable[ProductCapability],
        product_semantics: str = ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
        transport_support_tier: ProductTransportSupportTier | str | None = None,
    ) -> "ProductCapabilities":
        return cls(
            transport=transport,
            product_semantics=product_semantics,
            entries=tuple(entries),
            transport_support_tier=transport_support_tier,
        )

    def get(self, name: str) -> ProductCapability | None:
        name = _required_name(name)
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None

    def state(self, name: str) -> CapabilityState:
        entry = self.get(name)
        if entry is None:
            raise KeyError(name)
        return entry.state

    def to_dict(self) -> dict[str, Any]:
        support_tier = self.transport_support_tier
        assert isinstance(support_tier, ProductTransportSupportTier)
        return {
            "runtime_contract_schema": self.runtime_contract_schema,
            "transport": self.transport,
            "transport_support_tier": support_tier.value,
            "product_semantics": self.product_semantics,
            "capabilities": {
                entry.name: entry.to_dict()
                for entry in self.entries
            },
        }
