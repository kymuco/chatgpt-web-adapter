from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
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
    ProductCompletionProvenance,
    ProductExecutionProvenance,
    ProductIdentityProvenance,
)
from .product_transport import ProductRuntimeExecution, ProductRuntimeHealth
from .qwen_http import QwenHttpCredentials
from .types import (
    ChatConversation,
    ChatMetrics,
    ChatRequestDiagnostics,
    ChatResponse,
)

QWEN_PROVIDER_ID = "qwen"
QWEN_WEB_TRANSPORT = "qwen-web"
ORDINARY_QWEN_PRODUCT_SEMANTICS = "ordinary-qwen"

_QWEN_CAPABILITY_STATES: dict[str, CapabilityState] = {
    TEXT_TURNS: CapabilityState.UNKNOWN,
    NEW_CHAT: CapabilityState.UNKNOWN,
    CONTINUATION: CapabilityState.UNKNOWN,
    CANONICAL_READBACK: CapabilityState.UNIMPLEMENTED,
    CONVERSATION_ATTACH: CapabilityState.UNIMPLEMENTED,
    CONVERSATION_READ: CapabilityState.UNIMPLEMENTED,
    CONVERSATION_STATUS: CapabilityState.UNIMPLEMENTED,
    STREAMING: CapabilityState.UNIMPLEMENTED,
    IMAGES: CapabilityState.UNIMPLEMENTED,
    FILES: CapabilityState.UNIMPLEMENTED,
    WEB_SEARCH: CapabilityState.UNKNOWN,
    TEMPORARY_CHAT: CapabilityState.UNIMPLEMENTED,
    MODEL_SELECTION: CapabilityState.UNKNOWN,
    MODEL_PRESERVATION: CapabilityState.UNKNOWN,
    REASONING_SELECTION: CapabilityState.UNKNOWN,
    REASONING_PRESERVATION: CapabilityState.UNKNOWN,
    PRODUCT_MEMORY_PERSONALIZATION: CapabilityState.UNKNOWN,
    TOOLS_CONNECTORS: CapabilityState.UNIMPLEMENTED,
    APPROVALS: CapabilityState.UNIMPLEMENTED,
    CONVERSATION_BRANCHING: CapabilityState.UNIMPLEMENTED,
    MULTIMODAL_CONTINUATION: CapabilityState.UNIMPLEMENTED,
}


@dataclass(frozen=True)
class QwenBrowserTurnResult:
    conversation_id: str
    response_text: str
    final_url: str
    tab_id: int | None
    elapsed_ms: int | None
    finality_evidence: str
    canonical_completion_proven: bool
    route_identity_proven: bool
    automatic_write_retry: bool


class QwenWebWriteOutcomeAmbiguousError(RequestError):
    """Post-submit Qwen outcome that must never authorize automatic replay."""

    reconciliation_required = True
    automatic_retry_allowed = False


class QwenBrowserTurnProvider(BrowserNativeTurnProvider):
    """Experimental Qwen Web turn provider over the existing local bridge."""

    @staticmethod
    def _conversation_id(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, ChatConversation):
            value = value.conversation_id
        elif isinstance(value, dict):
            value = value.get("conversation_id")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Qwen conversation_id must be a non-empty opaque id")
        return value.strip()

    def export_auth(self) -> "QwenHttpCredentials":
        """Explicit opt-in: import only the Qwen session via existing native bridge."""
        request_id = uuid.uuid4().hex
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "providerId": QWEN_PROVIDER_ID,
                "operation": "export_auth",
                "allowAuthExport": True,
                "timeoutMs": 30_000,
            },
            timeout=35.0,
        )
        if response.get("request_id") != request_id or response.get("ok") is not True:
            raise RequestError(
                "QWEN_AUTH_SNAPSHOT_UNAVAILABLE",
                request_stage="qwen_auth_snapshot",
            )
        if (
            response.get("providerId") != QWEN_PROVIDER_ID
            or response.get("operation") != "auth_snapshot"
        ):
            raise RequestError(
                "QWEN_AUTH_SNAPSHOT_IDENTITY_MISMATCH",
                request_stage="qwen_auth_snapshot",
            )
        token = response.get("accessToken")
        cookies = response.get("cookies")
        expires = response.get("expiresAt")
        if not isinstance(token, str) or not token:
            raise RequestError(
                "QWEN_AUTH_SNAPSHOT_MISSING_TOKEN",
                request_stage="qwen_auth_snapshot",
            )
        if not isinstance(cookies, dict):
            cookies = {}
        return QwenHttpCredentials(
            access_token=token,
            cookies=cookies,
            headers=response.get("headers", {}),
            expires_at=float(expires) if isinstance(expires, (int, float)) else None,
        )

    def send_text(
        self,
        text: str,
        *,
        conversation: Any = None,
        timeout: float | None = None,
        on_text: Any = None,
        auto_confirm_age: bool = False,
        birth_year: int = 2000,
        foreground_tab: bool = False,
        on_token: Any = None,
    ) -> QwenBrowserTurnResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 200_000:
            raise ValueError("text is too large for Qwen Web turn")
        conversation_id = self._conversation_id(conversation)
        total_timeout = self.turn_timeout if timeout is None else float(timeout)
        if total_timeout <= 0:
            raise ValueError("timeout must be positive")

        try:
            response = self._rpc(
                {
                    "type": "turn",
                    "request_id": uuid.uuid4().hex,
                    "providerId": QWEN_PROVIDER_ID,
                    "conversationId": conversation_id,
                    "text": text,
                    "timeoutMs": int(total_timeout * 1000),
                    "streamTextObservations": on_text is not None,
                    "streamNetwork": on_token is not None,
                    "autoConfirmAge": auto_confirm_age,
                    "birthYear": birth_year,
                    "foregroundTab": foreground_tab,
                },
                # Allow the extension to report its own deadline/finality error
                # instead of racing the native bridge at the exact same second.
                timeout=total_timeout + self.connect_timeout + 20.0,
                on_event=lambda event: (
                    on_text(event["text"])
                    if on_text is not None
                    and event.get("providerId") == QWEN_PROVIDER_ID
                    and event.get("type") == "text_snapshot"
                    and isinstance(event.get("text"), str)
                    else on_token(event["text"])
                    if on_token is not None
                    and event.get("providerId") == QWEN_PROVIDER_ID
                    and event.get("type") == "text_delta"
                    and isinstance(event.get("text"), str)
                    else None
                ),
            )
        except RequestError as error:
            if str(error).startswith(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION:"
            ):
                raise QwenWebWriteOutcomeAmbiguousError(
                    f"QWEN_WEB_TURN_FAILED: {error}",
                    request_stage="qwen_web_turn",
                ) from error
            raise
        if response.get("ok") is not True:
            error = str(response.get("error") or "unknown error")
            if error.startswith(
                "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ):
                raise QwenWebWriteOutcomeAmbiguousError(
                    f"QWEN_WEB_TURN_FAILED: {error}",
                    request_stage="qwen_web_turn",
                )
            raise RequestError(
                f"QWEN_WEB_TURN_FAILED: {error}",
                request_stage="qwen_web_turn",
            )
        if on_token is not None and response.get("networkStreamVerified") is not True:
            raise QwenWebWriteOutcomeAmbiguousError(
                "QWEN_NETWORK_STREAM_NOT_VERIFIED: reload the updated CWA extension; do not resend automatically",
                request_stage="qwen_web_turn",
            )
        if response.get("providerId") != QWEN_PROVIDER_ID:
            raise RequestError(
                "QWEN_WEB_PROVIDER_ID_MISMATCH",
                request_stage="qwen_web_turn",
            )
        resolved_id = response.get("conversationId")
        response_text = response.get("responseText")
        final_url = response.get("finalUrl")
        if not isinstance(resolved_id, str) or not resolved_id.strip():
            raise RequestError(
                "QWEN_WEB_CONVERSATION_ID_MISSING",
                request_stage="qwen_web_turn",
            )
        if not isinstance(response_text, str) or not response_text.strip():
            raise RequestError(
                "QWEN_WEB_RESPONSE_TEXT_MISSING",
                request_stage="qwen_web_turn",
            )
        if not isinstance(final_url, str) or not final_url.startswith(
            "https://chat.qwen.ai/"
        ):
            raise RequestError(
                "QWEN_WEB_FINAL_ROUTE_INVALID",
                request_stage="qwen_web_turn",
            )
        if response.get("finalityEvidence") != "PAGE_DOM_STABLE_COMPLETION":
            raise RequestError(
                "QWEN_WEB_FINALITY_UNPROVEN",
                request_stage="qwen_web_turn",
            )
        if response.get("canonicalCompletionProven") is not False:
            raise RequestError(
                "QWEN_WEB_CANONICAL_FINALITY_MUST_REMAIN_UNPROVEN",
                request_stage="qwen_web_turn",
            )
        if response.get("routeIdentityProven") is not True:
            raise RequestError(
                "QWEN_WEB_ROUTE_IDENTITY_UNPROVEN",
                request_stage="qwen_web_turn",
            )
        if response.get("automaticWriteRetry") is not False:
            raise RequestError(
                "QWEN_WEB_AUTOMATIC_RETRY_FORBIDDEN",
                request_stage="qwen_web_turn",
            )

        return QwenBrowserTurnResult(
            conversation_id=resolved_id.strip(),
            response_text=response_text.strip(),
            final_url=final_url,
            tab_id=response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None,
            elapsed_ms=(
                response.get("elapsedMs")
                if isinstance(response.get("elapsedMs"), int)
                else None
            ),
            finality_evidence="PAGE_DOM_STABLE_COMPLETION",
            canonical_completion_proven=False,
            route_identity_proven=True,
            automatic_write_retry=False,
        )


def _qwen_capabilities() -> ProductCapabilities:
    return ProductCapabilities.from_entries(
        transport=QWEN_WEB_TRANSPORT,
        product_semantics=ORDINARY_QWEN_PRODUCT_SEMANTICS,
        entries=tuple(
            ProductCapability(
                name=name,
                state=_QWEN_CAPABILITY_STATES[name],
                owner=CapabilityOwner.TRANSPORT,
                evidence=(
                    "QWEN-PRELIVE minimal Qwen Web text new-chat/continuation proof"
                    if name in {TEXT_TURNS, NEW_CHAT, CONTINUATION}
                    else "outside QWEN-PRELIVE minimal Qwen Web proof"
                ),
            )
            for name in PRODUCT_CAPABILITY_NAMES
        ),
    )


class QwenWebTransport:
    transport_id = QWEN_WEB_TRANSPORT

    def __init__(self, provider: QwenBrowserTurnProvider | None = None) -> None:
        self.provider = provider or QwenBrowserTurnProvider()

    def health(self, conversation: Any = None) -> ProductRuntimeHealth:
        status = self.provider.status()
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=bool(status.available and status.extension_connected),
            reason=(
                "READY"
                if status.available and status.extension_connected
                else "BROWSER_NATIVE_EXTENSION_UNAVAILABLE"
            ),
            conversation_id=(
                QwenBrowserTurnProvider._conversation_id(conversation)
                if conversation is not None
                else None
            ),
            canonical_status=None,
            canonical_read_checked=False,
            read_plane="QWEN_PAGE_DOM",
            session_plane="QWEN_BROWSER_SESSION",
            write_plane="QWEN_PAGE_DOM_WRITE",
            automatic_write_retry=False,
            fallback_transport=None,
            bridge_available=status.available,
            extension_connected=status.extension_connected,
            runtime_tab_id=status.runtime_tab_id,
        )

    def capabilities(self) -> ProductCapabilities:
        return _qwen_capabilities()

    def governance(self) -> dict[str, Any]:
        return {
            "product_semantics": ORDINARY_QWEN_PRODUCT_SEMANTICS,
            "transport": self.transport_id,
            "write_plane": "QWEN_PAGE_DOM_WRITE",
            "read_plane": "QWEN_PAGE_DOM",
            "session_plane": "QWEN_BROWSER_SESSION",
            "canonical_readback_required": False,
            "automatic_write_retry": False,
            "fallback_transport": None,
            "ambiguous_write_requires_reconciliation": True,
            "incremental_observation_is_canonical_finality": False,
            "finality_model": "PAGE_DOM_STABLE_COMPLETION",
            "conversation_identity_model": "LOCAL_OPAQUE_ID_TO_PAGE_ROUTE",
        }

    def send_text(
        self,
        text: str,
        *,
        conversation: Any = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Any = None,
        on_event: Any = None,
        on_text: Any = None,
        auto_confirm_age: bool = False,
        birth_year: int = 2000,
        foreground_tab: bool = False,
    ) -> ChatResponse:
        return self.send_text_observed(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=on_event,
            on_text=on_text,
            auto_confirm_age=auto_confirm_age,
            birth_year=birth_year,
            foreground_tab=foreground_tab,
        ).response

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: Any = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Any = None,
        on_event: Any = None,
        on_text: Any = None,
        auto_confirm_age: bool = False,
        birth_year: int = 2000,
        foreground_tab: bool = False,
    ) -> ProductRuntimeExecution:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if on_event is not None:
            raise ValueError(
                "Qwen Web streaming callbacks are outside QWEN-PRELIVE scope"
            )

        continuation = conversation is not None
        turn = self.provider.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            on_text=on_text,
            on_token=on_token,
            auto_confirm_age=auto_confirm_age,
            birth_year=birth_year,
            foreground_tab=foreground_tab,
        )
        response = ChatResponse(
            text=turn.response_text,
            conversation=ChatConversation(
                conversation_id=turn.conversation_id,
            ),
            metrics=ChatMetrics(
                total=(turn.elapsed_ms / 1000.0)
                if turn.elapsed_ms is not None
                else None
            ),
            request=ChatRequestDiagnostics(
                conversation_id=turn.conversation_id,
                is_continuation=continuation,
            ),
        )
        observation = {
            "provider_id": QWEN_PROVIDER_ID,
            "finality_evidence": turn.finality_evidence,
            "canonical_completion_proven": False,
            "route_identity_proven": turn.route_identity_proven,
            "automatic_write_retry": False,
            "tab_id": turn.tab_id,
            "elapsed_ms": turn.elapsed_ms,
        }
        provenance = ProductExecutionProvenance(
            product_semantics=ORDINARY_QWEN_PRODUCT_SEMANTICS,
            transport=self.transport_id,
            write_plane="QWEN_PAGE_DOM_WRITE",
            readback_plane="QWEN_PAGE_DOM",
            session_plane="QWEN_BROWSER_SESSION",
            completion=ProductCompletionProvenance(
                completed=True,
                source=CompletionSource.TRANSPORT_RETURN,
                canonical_completion_proven=False,
                finish_reason=None,
                finish_reason_observed=False,
                finality_detail=turn.finality_evidence,
            ),
            identity=ProductIdentityProvenance(
                conversation_id=turn.conversation_id,
                message_id=None,
                observed_model=None,
            ),
            transport_metadata=observation,
        )
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=response,
            observation=observation,
            provenance=provenance,
        )


class QwenWebRuntime:
    provider_id = QWEN_PROVIDER_ID
    transport = QWEN_WEB_TRANSPORT

    def __init__(self, write_transport: QwenWebTransport | None = None) -> None:
        self.write_transport = write_transport or QwenWebTransport()

    def health(self, conversation: Any = None) -> ProductRuntimeHealth:
        return self.write_transport.health(conversation)

    def capabilities(self) -> ProductCapabilities:
        return self.write_transport.capabilities()

    def governance(self) -> dict[str, Any]:
        payload = dict(self.write_transport.governance())
        payload.update(
            {
                "provider_id": self.provider_id,
                "transport": self.transport,
                "canonical_interface": None,
                "write_transport_interface": "ProductWriteTransport",
                "capability_model": "ProductCapabilities",
                "provenance_model": "ProductExecutionProvenance",
            }
        )
        return payload

    def send_text(self, text: str, **kwargs: Any) -> ChatResponse:
        return self.write_transport.send_text(text, **kwargs)

    def send_text_observed(self, text: str, **kwargs: Any) -> ProductRuntimeExecution:
        return self.write_transport.send_text_observed(text, **kwargs)
