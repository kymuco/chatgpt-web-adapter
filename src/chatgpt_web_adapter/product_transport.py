from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Protocol, runtime_checkable

from .product_capabilities import ProductCapabilities
from .product_provenance import ProductExecutionProvenance
from .product_support import (
    PRODUCT_RUNTIME_CONTRACT_SCHEMA,
    ProductTransportSupportTier,
    normalize_product_transport_support_tier,
    product_transport_support_tier,
)
from .types import ChatConversation, ChatMessage, ChatResponse, ConversationRef, ConversationStatus

BROWSER_OWNED_PRODUCT_TRANSPORT = "browser-owned"
DEFAULT_PRODUCT_TRANSPORT = BROWSER_OWNED_PRODUCT_TRANSPORT
SUPPORTED_PRODUCT_TRANSPORTS: tuple[str, ...] = (BROWSER_OWNED_PRODUCT_TRANSPORT,)

ConversationInput = ConversationRef | ChatConversation | dict[str, Any] | str | None
TokenCallback = Callable[[str], None] | None
EventCallback = Callable[[dict[str, Any]], None] | None


def normalize_product_transport(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("transport must be a string")
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_PRODUCT_TRANSPORTS:
        supported = ", ".join(SUPPORTED_PRODUCT_TRANSPORTS)
        raise ValueError(
            f"unsupported product transport {value!r}; expected one of: {supported}"
        )
    return normalized


@dataclass(frozen=True)
class ProductRuntimeHealth:
    """Implementation-independent runtime readiness plus transport metadata."""

    transport: str
    ready: bool
    reason: str
    conversation_id: str | None
    canonical_status: str | None
    canonical_read_checked: bool
    read_plane: str
    session_plane: str
    write_plane: str
    automatic_write_retry: bool = False
    fallback_transport: str | None = None
    # Browser-owned compatibility metadata. Future non-browser transports are not
    # required to synthesize these fields.
    bridge_available: bool | None = None
    extension_connected: bool | None = None
    runtime_tab_id: int | None = None
    runtime_tab_preexisting: bool | None = None
    runtime_contract_schema: int = PRODUCT_RUNTIME_CONTRACT_SCHEMA
    transport_support_tier: ProductTransportSupportTier | str | None = None

    def __post_init__(self) -> None:
        transport = self.transport.strip().lower()
        if not transport:
            raise ValueError("runtime health transport identity is required")
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
        object.__setattr__(self, "runtime_contract_schema", schema)
        object.__setattr__(self, "transport_support_tier", support_tier)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        support_tier = self.transport_support_tier
        assert isinstance(support_tier, ProductTransportSupportTier)
        payload["transport_support_tier"] = support_tier.value
        return payload


@dataclass(frozen=True)
class ProductRuntimeExecution:
    transport: str
    response: ChatResponse
    observation: Any
    provenance: ProductExecutionProvenance | None = None


@runtime_checkable
class CanonicalConversationClient(Protocol):
    """Canonical conversation surface consumed by product-runtime orchestration."""

    def get_status(self, conversation: Any) -> ConversationStatus: ...

    def get_messages(self, conversation: Any, **kwargs: Any) -> list[ChatMessage]: ...

    def attach_conversation(self, conversation: Any) -> Any: ...


@runtime_checkable
class CanonicalSessionClient(Protocol):
    """Optional canonical session/auth lifecycle surface."""

    def refresh_auth(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class ProductWriteTransport(Protocol):
    """Replaceable ordinary-product write contract below ChatGPTProductRuntime.

    Runtime-mediated keyword options are deliberately allowed so new transports
    can implement product features such as conversation mode or model intent
    without changing the application-facing ChatGPTProductRuntime API. Callers
    should invoke those options through ChatGPTProductRuntime rather than relying
    on concrete transport keyword names.
    """

    @property
    def transport_id(self) -> str: ...

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth: ...

    def capabilities(self) -> ProductCapabilities: ...

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
        **kwargs: Any,
    ) -> ChatResponse: ...

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
        **kwargs: Any,
    ) -> ProductRuntimeExecution: ...

    def governance(self) -> dict[str, Any]: ...


def require_canonical_conversation_client(client: Any) -> CanonicalConversationClient:
    for name in ("get_status", "get_messages", "attach_conversation"):
        if not callable(getattr(client, name, None)):
            raise TypeError(
                "canonical client must expose callable get_status(), get_messages(), "
                "and attach_conversation()"
            )
    return client


def require_product_write_transport(transport: Any) -> ProductWriteTransport:
    transport_id = getattr(transport, "transport_id", None)
    if not isinstance(transport_id, str) or not transport_id.strip():
        raise TypeError("write transport must expose a non-empty transport_id")
    for name in ("health", "capabilities", "send_text", "send_text_observed", "governance"):
        if not callable(getattr(transport, name, None)):
            raise TypeError(
                "write transport must expose callable health(), capabilities(), send_text(), "
                "send_text_observed(), and governance()"
            )
    return transport
