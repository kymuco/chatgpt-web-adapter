from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .client import ChatGPTWebClient, DEFAULT_TIMEOUT_SECONDS
from .product_capabilities import ProductCapabilities
from .product_provenance import (
    ConversationMode,
    ConversationModeEvidenceSource,
    ProductConversationModeProvenance,
    ProductExecutionProvenance,
    build_product_execution_provenance,
)
from .product_transport import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    DEFAULT_PRODUCT_TRANSPORT,
    SUPPORTED_PRODUCT_TRANSPORTS,
    CanonicalConversationClient,
    CanonicalSessionClient,
    ConversationInput,
    EventCallback,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    ProductWriteTransport,
    TokenCallback,
    normalize_product_transport,
    require_canonical_conversation_client,
    require_product_write_transport,
)
from .types import ChatMessage, ChatResponse, ConversationStatus


_NORMAL_CONVERSATION_MODE = "normal"
_TEMPORARY_CONVERSATION_MODE = "temporary"
_SUPPORTED_CONVERSATION_MODES: tuple[str, ...] = (
    _NORMAL_CONVERSATION_MODE,
    _TEMPORARY_CONVERSATION_MODE,
)


def _normalize_conversation_mode(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("conversation_mode must be a string")
    normalized = value.strip().lower()
    if normalized not in _SUPPORTED_CONVERSATION_MODES:
        supported = ", ".join(_SUPPORTED_CONVERSATION_MODES)
        raise ValueError(
            f"unsupported conversation_mode {value!r}; expected one of: {supported}"
        )
    return normalized


def _normal_conversation_mode_provenance() -> ProductConversationModeProvenance:
    return ProductConversationModeProvenance(
        requested_conversation_mode=ConversationMode.NORMAL,
        observed_conversation_mode=ConversationMode.NORMAL,
        observed_mode_evidence_source=(
            ConversationModeEvidenceSource.TRANSPORT_SEMANTICS_CONTRACT
        ),
        observed_mode_proven=True,
        proof_detail=(
            "normal request dispatched through ordinary-mode-only ProductWriteTransport"
        ),
    )


class ProductConversationModeUnavailableError(RuntimeError):
    """Fail-closed refusal before any product write for an unavailable mode."""

    def __init__(self, requested_mode: str) -> None:
        normalized = _normalize_conversation_mode(requested_mode)
        requested = ConversationMode(normalized.upper())
        self.conversation_mode_provenance = ProductConversationModeProvenance(
            requested_conversation_mode=requested,
            observed_conversation_mode=ConversationMode.UNKNOWN,
            observed_mode_evidence_source=ConversationModeEvidenceSource.NONE,
            observed_mode_proven=False,
            proof_detail="request blocked before ProductWriteTransport dispatch",
        )
        super().__init__(
            "PRODUCT_CONVERSATION_MODE_UNAVAILABLE: "
            f"requested={requested.value} observed=UNKNOWN "
            f"conversation_mode={normalized!r} is disabled in production until "
            "mode-aware Temporary write routing is implemented; fallback=none"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": str(self),
            "conversation_mode": self.conversation_mode_provenance.to_dict(),
        }


def _require_production_write_mode(value: str) -> str:
    mode = _normalize_conversation_mode(value)
    if mode == _TEMPORARY_CONVERSATION_MODE:
        raise ProductConversationModeUnavailableError(mode)
    return mode


def _validate_or_attach_normal_mode_provenance(
    provenance: ProductExecutionProvenance,
) -> ProductExecutionProvenance:
    mode = provenance.conversation_mode
    if mode is None:
        return replace(
            provenance,
            conversation_mode=_normal_conversation_mode_provenance(),
        )
    if mode.requested_conversation_mode is not ConversationMode.NORMAL:
        raise RuntimeError(
            "write transport returned conversation-mode provenance for unexpected "
            f"requested mode {mode.requested_conversation_mode.value!r}"
        )
    if (
        mode.observed_conversation_mode is not ConversationMode.NORMAL
        or not mode.observed_mode_proven
    ):
        raise RuntimeError(
            "write transport did not prove NORMAL observed conversation mode for "
            "a successful normal production execution"
        )
    return provenance


def _assemble_default_write_transport(
    client: CanonicalConversationClient,
    *,
    transport: str,
    provider: Any | None,
) -> ProductWriteTransport:
    if transport != BROWSER_OWNED_PRODUCT_TRANSPORT:
        # normalize_product_transport() makes this unreachable for the current
        # production registry. Keep the branch explicit so future transports
        # cannot accidentally fall through to browser-owned.
        raise ValueError(f"no production transport assembler registered for {transport!r}")

    from .browser_owned_product_transport import BrowserOwnedProductTransport

    return BrowserOwnedProductTransport(client, provider=provider)


class ChatGPTProductRuntime:
    """Implementation-independent ordinary-ChatGPT product runtime.

    PR8.4 separates canonical observation from product mutation. PR8.5 adds a
    machine-readable capability surface and provenance-aware observed execution
    without making browser-specific metadata mandatory for future transports.

    ``provider=`` remains as a compatibility assembly shortcut for PR8.3
    callers. New composition code should inject ``write_transport=`` or use
    ``assemble_product_runtime()``.
    """

    def __init__(
        self,
        client: Any,
        *,
        transport: str = DEFAULT_PRODUCT_TRANSPORT,
        provider: Any | None = None,
        write_transport: ProductWriteTransport | None = None,
    ) -> None:
        self.transport = normalize_product_transport(transport)
        self.client = require_canonical_conversation_client(client)
        self.canonical = self.client

        if write_transport is not None and provider is not None:
            raise ValueError("provider and write_transport are mutually exclusive")

        if write_transport is None:
            write_transport = _assemble_default_write_transport(
                self.canonical,
                transport=self.transport,
                provider=provider,
            )
        else:
            write_transport = require_product_write_transport(write_transport)
            injected_id = write_transport.transport_id.strip().lower()
            if injected_id != self.transport:
                raise ValueError(
                    "write transport identity does not match selected transport: "
                    f"{injected_id!r} != {self.transport!r}"
                )

        self.write_transport = write_transport
        self._transport = write_transport
        # Private PR8.3 compatibility alias for existing tests/diagnostics. The
        # runtime itself never dispatches through this attribute.
        self._writer = getattr(write_transport, "_runtime", write_transport)

    def health(
        self,
        conversation: ConversationInput = None,
    ) -> ProductRuntimeHealth:
        return self.write_transport.health(conversation)

    readiness = health

    def capabilities(self) -> ProductCapabilities:
        capabilities = self.write_transport.capabilities()
        if not isinstance(capabilities, ProductCapabilities):
            raise TypeError("write transport capabilities() must return ProductCapabilities")
        if capabilities.transport != self.transport:
            raise RuntimeError(
                "write transport returned capabilities for unexpected transport "
                f"{capabilities.transport!r}"
            )
        return capabilities

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
        conversation_mode: str = _NORMAL_CONVERSATION_MODE,
    ) -> ChatResponse:
        _require_production_write_mode(conversation_mode)
        return self.write_transport.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )

    def send(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
        conversation_mode: str = _NORMAL_CONVERSATION_MODE,
    ) -> ChatResponse:
        return self.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
            conversation_mode=conversation_mode,
        )

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationInput = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: TokenCallback = None,
        on_event: EventCallback = None,
        conversation_mode: str = _NORMAL_CONVERSATION_MODE,
    ) -> ProductRuntimeExecution:
        mode = _require_production_write_mode(conversation_mode)
        execution = self.write_transport.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
        )
        if execution.transport != self.transport:
            raise RuntimeError(
                "write transport returned execution for unexpected transport "
                f"{execution.transport!r}"
            )

        if mode != _NORMAL_CONVERSATION_MODE:
            raise RuntimeError("unexpected enabled production conversation mode")
        expected_mode = _normal_conversation_mode_provenance()

        provenance = execution.provenance
        if provenance is None:
            provenance = build_product_execution_provenance(
                transport=self.transport,
                response=execution.response,
                observation=execution.observation,
                governance=self.write_transport.governance(),
                conversation_mode=expected_mode,
            )
        elif not isinstance(provenance, ProductExecutionProvenance):
            raise TypeError(
                "write transport execution provenance must be ProductExecutionProvenance or None"
            )
        elif provenance.transport != self.transport:
            raise RuntimeError(
                "write transport returned provenance for unexpected transport "
                f"{provenance.transport!r}"
            )
        else:
            provenance = _validate_or_attach_normal_mode_provenance(provenance)

        return ProductRuntimeExecution(
            transport=execution.transport,
            response=execution.response,
            observation=execution.observation,
            provenance=provenance,
        )

    def get_status(self, conversation: Any) -> ConversationStatus:
        return self.canonical.get_status(conversation)

    def get_messages(self, conversation: Any, **kwargs: Any) -> list[ChatMessage]:
        return self.canonical.get_messages(conversation, **kwargs)

    def attach_conversation(self, conversation: Any) -> Any:
        return self.canonical.attach_conversation(conversation)

    def governance(self) -> dict[str, Any]:
        transport_governance = dict(self.write_transport.governance())
        transport_governance.update(
            {
                "transport": self.transport,
                "transport_selection_explicit": True,
                "supported_product_transports": list(SUPPORTED_PRODUCT_TRANSPORTS),
                "fallback_transport": None,
                "legacy_direct_write_fallback": False,
                "conversation_mode_request_values": list(_SUPPORTED_CONVERSATION_MODES),
                "default_conversation_mode": _NORMAL_CONVERSATION_MODE,
                "conversation_mode_fallback": None,
                "silent_conversation_mode_fallback": False,
                "temporary_mode_production_enabled": False,
                "temporary_mode_fail_closed_before_write": True,
                "temporary_mode_requires_mode_aware_write_routing": True,
                "conversation_mode_provenance_model": "ProductConversationModeProvenance",
                "requested_conversation_mode_is_caller_input": True,
                "normal_observed_mode_evidence_source": (
                    ConversationModeEvidenceSource.TRANSPORT_SEMANTICS_CONTRACT.value
                ),
                "blocked_temporary_observed_mode": ConversationMode.UNKNOWN.value,
                "temporary_mode_observation_required_before_write": True,
                "conversation_mode_state_scope": "REQUEST",
                "conversation_mode_state_persisted": False,
                "temporary_mode_denial_mutates_runtime_mode_state": False,
                "normal_mode_requires_fresh_request_resolution": True,
                "normal_mode_inherits_temporary_identity": False,
                "normal_mode_inherits_temporary_lifecycle": False,
                "normal_mode_inherits_temporary_provenance": False,
                "new_chat_supported": True,
                "continuation_supported": True,
                "daily_use_entrypoint": "ChatGPTProductRuntime.send",
                "canonical_lifecycle_access": True,
                "canonical_interface": "CanonicalConversationClient",
                "write_transport_interface": "ProductWriteTransport",
                "runtime_depends_on_concrete_browser_transport": False,
                "capability_model": "ProductCapabilities",
                "capability_states": [
                    "AVAILABLE",
                    "UNSUPPORTED",
                    "UNKNOWN",
                    "UNIMPLEMENTED",
                ],
                "provenance_model": "ProductExecutionProvenance",
                "finish_reason_is_optional_observed_metadata": True,
            }
        )
        return transport_governance


def assemble_product_runtime(
    *,
    transport: str = DEFAULT_PRODUCT_TRANSPORT,
    client: Any | None = None,
    provider: Any | None = None,
    write_transport: ProductWriteTransport | None = None,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    client_timeout: int = DEFAULT_TIMEOUT_SECONDS,
    auto_refresh_auth: bool = True,
    persist_refreshed_auth: bool = True,
) -> ChatGPTProductRuntime:
    """Assemble the production ordinary-ChatGPT runtime.

    Assembly never performs interactive browser login and never enables the
    legacy Sentinel/direct-write machinery. Unknown production transports fail
    closed. A custom protocol-conforming transport can be injected explicitly
    for composition/testing, but its identity must still match the selected
    production transport.
    """

    normalized = normalize_product_transport(transport)
    if client is None:
        client = ChatGPTWebClient(
            auth_file=auth_file,
            timeout=client_timeout,
            auto_refresh_auth=auto_refresh_auth,
            persist_refreshed_auth=persist_refreshed_auth,
            auto_login=False,
            auto_sentinel=False,
        )

    canonical = require_canonical_conversation_client(client)

    if write_transport is None:
        write_transport = _assemble_default_write_transport(
            canonical,
            transport=normalized,
            provider=provider,
        )
        provider = None

    return ChatGPTProductRuntime(
        canonical,
        transport=normalized,
        provider=provider,
        write_transport=write_transport,
    )
