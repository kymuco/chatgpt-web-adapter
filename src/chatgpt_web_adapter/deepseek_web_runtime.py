from __future__ import annotations

from typing import Any

from .deepseek_web_provider import (
    DEEPSEEK_WEB_PROVIDER_ID,
    DeepSeekWebTurnProvider,
    DeepSeekWebTurnResult,
)
from .product_capabilities import (
    APPROVALS,
    CANONICAL_READBACK,
    CONTINUATION,
    CONVERSATION_ATTACH,
    CONVERSATION_BRANCHING,
    CONVERSATION_READ,
    CONVERSATION_STATUS,
    FILES,
    IMAGES,
    MODEL_PRESERVATION,
    MODEL_SELECTION,
    MULTIMODAL_CONTINUATION,
    NEW_CHAT,
    PRODUCT_CAPABILITY_NAMES,
    PRODUCT_MEMORY_PERSONALIZATION,
    REASONING_PRESERVATION,
    REASONING_SELECTION,
    STREAMING,
    TEMPORARY_CHAT,
    TEXT_TURNS,
    TOOLS_CONNECTORS,
    WEB_SEARCH,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from .product_provenance import (
    CompletionSource,
    ConversationMode,
    ConversationModeEvidenceSource,
    ProductCompletionProvenance,
    ProductConversationModeProvenance,
    ProductExecutionProvenance,
    ProductIdentityProvenance,
)
from .product_transport import (
    ConversationInput,
    EventCallback,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    TokenCallback,
)
from .types import (
    ChatConversation,
    ChatMetrics,
    ChatRequestDiagnostics,
    ChatResponse,
    ConversationRef,
)

DEEPSEEK_WEB_PRODUCT_TRANSPORT = "deepseek-web"
ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS = "ordinary-deepseek"

_DEEPSEEK_CAPABILITY_STATES: dict[str, CapabilityState] = {
    name: CapabilityState.UNIMPLEMENTED for name in PRODUCT_CAPABILITY_NAMES
}
_DEEPSEEK_CAPABILITY_STATES.update(
    {
        TEXT_TURNS: CapabilityState.AVAILABLE,
        NEW_CHAT: CapabilityState.AVAILABLE,
        CONTINUATION: CapabilityState.AVAILABLE,
        CANONICAL_READBACK: CapabilityState.UNIMPLEMENTED,
        CONVERSATION_ATTACH: CapabilityState.UNIMPLEMENTED,
        CONVERSATION_READ: CapabilityState.UNIMPLEMENTED,
        CONVERSATION_STATUS: CapabilityState.UNIMPLEMENTED,
        STREAMING: CapabilityState.UNIMPLEMENTED,
        IMAGES: CapabilityState.UNIMPLEMENTED,
        FILES: CapabilityState.UNIMPLEMENTED,
        WEB_SEARCH: CapabilityState.UNIMPLEMENTED,
        TEMPORARY_CHAT: CapabilityState.UNIMPLEMENTED,
        MODEL_SELECTION: CapabilityState.UNIMPLEMENTED,
        MODEL_PRESERVATION: CapabilityState.UNIMPLEMENTED,
        REASONING_SELECTION: CapabilityState.UNIMPLEMENTED,
        REASONING_PRESERVATION: CapabilityState.UNIMPLEMENTED,
        PRODUCT_MEMORY_PERSONALIZATION: CapabilityState.UNIMPLEMENTED,
        TOOLS_CONNECTORS: CapabilityState.UNIMPLEMENTED,
        APPROVALS: CapabilityState.UNIMPLEMENTED,
        CONVERSATION_BRANCHING: CapabilityState.UNIMPLEMENTED,
        MULTIMODAL_CONTINUATION: CapabilityState.UNIMPLEMENTED,
    }
)

_DEEPSEEK_CAPABILITY_EVIDENCE: dict[str, str] = {
    TEXT_TURNS: (
        "PR15.53 browser-page proof: text is entered and submitted through the "
        "logged-in DeepSeek Web page; completion is a stable assistant DOM observation"
    ),
    NEW_CHAT: (
        "PR15.53 DeepSeek Web provider creates a fresh hidden chat.deepseek.com tab "
        "and records the exact final conversation URL under a local opaque id"
    ),
    CONTINUATION: (
        "PR15.53 continuation reopens the exact DeepSeek URL stored after the "
        "previous completed turn; unknown ids fail before write"
    ),
    CANONICAL_READBACK: (
        "minimal provider #2 proof has no independent DeepSeek server-canonical read plane"
    ),
    STREAMING: "minimal provider #2 proof returns final assistant text only",
}


def _deepseek_capabilities() -> ProductCapabilities:
    return ProductCapabilities.from_entries(
        transport=DEEPSEEK_WEB_PRODUCT_TRANSPORT,
        product_semantics=ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS,
        entries=(
            ProductCapability(
                name=name,
                state=_DEEPSEEK_CAPABILITY_STATES[name],
                owner=CapabilityOwner.TRANSPORT,
                evidence=_DEEPSEEK_CAPABILITY_EVIDENCE.get(
                    name,
                    "outside the bounded PR15.53 DeepSeek text-turn proof",
                ),
            )
            for name in PRODUCT_CAPABILITY_NAMES
        ),
    )


_DEEPSEEK_CAPABILITIES = _deepseek_capabilities()


def _conversation_id(conversation: ConversationInput) -> str | None:
    if conversation is None:
        return None
    return ConversationRef.from_any(conversation).conversation_id


def _normal_mode_provenance() -> ProductConversationModeProvenance:
    return ProductConversationModeProvenance(
        requested_conversation_mode=ConversationMode.NORMAL,
        observed_conversation_mode=ConversationMode.NORMAL,
        observed_mode_evidence_source=(
            ConversationModeEvidenceSource.TRANSPORT_SEMANTICS_CONTRACT
        ),
        observed_mode_proven=True,
        proof_detail="DeepSeekWebProductTransport exposes ordinary text turns only",
    )


def _response_from_turn(
    turn: DeepSeekWebTurnResult,
    *,
    is_continuation: bool,
) -> ChatResponse:
    return ChatResponse(
        text=turn.assistant_text,
        conversation=ChatConversation(
            conversation_id=turn.conversation_id,
        ),
        metrics=ChatMetrics(
            total=(turn.elapsed_ms / 1000.0) if turn.elapsed_ms is not None else None,
        ),
        request=ChatRequestDiagnostics(
            conversation_id=turn.conversation_id,
            is_continuation=is_continuation,
        ),
    )


def _provenance_from_turn(turn: DeepSeekWebTurnResult) -> ProductExecutionProvenance:
    return ProductExecutionProvenance(
        product_semantics=ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS,
        transport=DEEPSEEK_WEB_PRODUCT_TRANSPORT,
        write_plane="DEEPSEEK_WEB_PAGE_CDP",
        readback_plane="DEEPSEEK_WEB_STABLE_ASSISTANT_DOM",
        session_plane="EXISTING_CHROME_DEEPSEEK_SESSION",
        completion=ProductCompletionProvenance(
            completed=True,
            source=CompletionSource.TRANSPORT_RETURN,
            canonical_completion_proven=False,
            finish_reason=None,
            finish_reason_observed=False,
            finality_detail=(
                "assistant DOM remained stable after submission with no visible "
                f"stop control; stable_for_ms={turn.stable_for_ms}"
            ),
        ),
        identity=ProductIdentityProvenance(
            conversation_id=turn.conversation_id,
            message_id=None,
            observed_model=None,
        ),
        transport_metadata={
            "provider_id": DEEPSEEK_WEB_PROVIDER_ID,
            "completion_proof": turn.completion_proof,
            "stable_for_ms": turn.stable_for_ms,
            "submit_strategy": turn.submit_strategy,
            "tab_was_active": turn.tab_was_active,
        },
        conversation_mode=_normal_mode_provenance(),
    )


class DeepSeekWebProductTransport:
    """Experimental ProductWriteTransport for DeepSeek Web text turns only."""

    transport_id = DEEPSEEK_WEB_PRODUCT_TRANSPORT

    def __init__(self, provider: DeepSeekWebTurnProvider | None = None) -> None:
        self.provider = provider or DeepSeekWebTurnProvider()

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth:
        conversation_id = _conversation_id(conversation)
        status = self.provider.status()
        ready = bool(status.available and status.extension_connected)
        reason = (
            "BRIDGE_READY_DEEPSEEK_SESSION_PROBED_ON_WRITE"
            if ready
            else "BROWSER_NATIVE_BRIDGE_UNAVAILABLE"
        )
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=ready,
            reason=reason,
            conversation_id=conversation_id,
            canonical_status=None,
            canonical_read_checked=False,
            read_plane="DEEPSEEK_WEB_STABLE_ASSISTANT_DOM",
            session_plane="EXISTING_CHROME_DEEPSEEK_SESSION",
            write_plane="DEEPSEEK_WEB_PAGE_CDP",
            automatic_write_retry=False,
            fallback_transport=None,
            bridge_available=status.available,
            extension_connected=status.extension_connected,
            runtime_tab_id=None,
            runtime_tab_preexisting=None,
        )

    def capabilities(self) -> ProductCapabilities:
        return _DEEPSEEK_CAPABILITIES

    @staticmethod
    def _reject_unsupported_observation_callbacks(
        *,
        on_token: TokenCallback,
        on_event: EventCallback,
    ) -> None:
        if on_token is not None or on_event is not None:
            raise ValueError(
                "DeepSeek Web PR15.53 proof does not expose incremental streaming"
            )

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
    ) -> ChatResponse:
        return self.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        ).response

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
    ) -> ProductRuntimeExecution:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._reject_unsupported_observation_callbacks(
            on_token=on_token,
            on_event=on_event,
        )
        is_continuation = conversation is not None
        turn = self.provider.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
        )
        response = _response_from_turn(
            turn,
            is_continuation=is_continuation,
        )
        provenance = _provenance_from_turn(turn)
        observation = {
            "provider_id": DEEPSEEK_WEB_PROVIDER_ID,
            "completion_proof": turn.completion_proof,
            "stable_for_ms": turn.stable_for_ms,
            "continuation": is_continuation,
        }
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=response,
            observation=observation,
            provenance=provenance,
        )

    def governance(self) -> dict[str, Any]:
        return {
            "product_semantics": ORDINARY_DEEPSEEK_PRODUCT_SEMANTICS,
            "automatic_write_retry": False,
            "fallback_transport": None,
            "ambiguous_write_requires_reconciliation": True,
            "incremental_observation_is_canonical_finality": False,
            "canonical_readback_required": False,
            "read_plane": "DEEPSEEK_WEB_STABLE_ASSISTANT_DOM",
            "session_plane": "EXISTING_CHROME_DEEPSEEK_SESSION",
            "write_plane": "DEEPSEEK_WEB_PAGE_CDP",
        }


class DeepSeekWebRuntime:
    """Minimal provider #2 runtime used to falsify the PR15.52 boundary."""

    provider_id = DEEPSEEK_WEB_PROVIDER_ID
    transport = DEEPSEEK_WEB_PRODUCT_TRANSPORT

    def __init__(
        self,
        *,
        provider: DeepSeekWebTurnProvider | None = None,
        write_transport: DeepSeekWebProductTransport | None = None,
    ) -> None:
        if provider is not None and write_transport is not None:
            raise ValueError("provide either provider or write_transport, not both")
        self.write_transport = write_transport or DeepSeekWebProductTransport(provider)

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth:
        return self.write_transport.health(conversation)

    def capabilities(self) -> ProductCapabilities:
        return self.write_transport.capabilities()

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
    ) -> ChatResponse:
        return self.write_transport.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
    ) -> ProductRuntimeExecution:
        return self.write_transport.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def governance(self) -> dict[str, Any]:
        payload = dict(self.write_transport.governance())
        payload.update(
            {
                "provider_id": self.provider_id,
                "transport": self.transport,
                "canonical_interface": "CanonicalConversationClient",
                "write_transport_interface": "ProductWriteTransport",
                "capability_model": "ProductCapabilities",
                "provenance_model": "ProductExecutionProvenance",
            }
        )
        return payload
