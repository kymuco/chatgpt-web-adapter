from __future__ import annotations

from dataclasses import asdict, dataclass, field
import threading
import time
import uuid
from typing import Any, Callable

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .product_capabilities import ORDINARY_CHATGPT_PRODUCT_SEMANTICS
from .product_provenance import (
    CompletionSource,
    ConversationMode,
    ConversationModeEvidenceSource,
    ProductCompletionProvenance,
    ProductConversationModeProvenance,
    ProductExecutionProvenance,
    ProductIdentityProvenance,
    ProductTemporaryLifecycleProvenance,
    TemporaryLifecycleEvidenceSource,
    TemporaryLifecycleState,
)
from .product_transport import BROWSER_OWNED_PRODUCT_TRANSPORT, ProductRuntimeExecution
from .revision_safe_streaming_pr8_9 import (
    ACTIVITY_EVENT_TYPES,
    ASSISTANT_TEXT_DELTA,
    ASSISTANT_TEXT_REVISION,
    ASSISTANT_TEXT_SNAPSHOT,
)
from .types import (
    ChatConversation,
    ChatMetrics,
    ChatRequestDiagnostics,
    ChatResponse,
    ConversationRef,
)

TEMPORARY_WRITE_PLANE = "BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_WRITE"
TEMPORARY_READBACK_PLANE = "BROWSER_NATIVE_PAGE_OWNED_TEMPORARY_STREAM"
TEMPORARY_SESSION_PLANE = "LIVE_TEMPORARY_PRODUCT_LIFECYCLE"
TEMPORARY_PREWRITE_PROOF = "FETCH_PAUSED_HISTORY_AND_TRAINING_DISABLED_TRUE"


@dataclass(frozen=True)
class TemporaryProductWriteObservation:
    write_event_observed: bool
    conversation_id: str | None = None
    message_id: str | None = None
    response_status: int | None = None
    temporary_mode_proven: bool = False
    temporary_prewrite_proof: str | None = None
    temporary_continuation_identity_proven: bool = False
    temporary_lifecycle_state: str | None = None
    temporary_live_write_authority_proven: bool = False
    temporary_paused_conversation_write_count: int = 0
    stream_observation_count: int = 0
    stream_delivery_incomplete: bool = False
    browser_authority_lease_id: str | None = None
    runtime_tab_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporaryProductWriteRuntimeError(RequestError):
    """Fail-closed Temporary execution error with no automatic retry."""

    def __init__(
        self,
        message: str,
        *,
        write_may_have_been_submitted: bool,
        reconciliation_required: bool,
        cause: BaseException | None = None,
        request_stage: str = "temporary_product_write",
    ) -> None:
        self.automatic_retry_allowed = False
        self.write_may_have_been_submitted = bool(write_may_have_been_submitted)
        self.reconciliation_required = bool(reconciliation_required)
        self.cause = cause
        super().__init__(message, request_stage=request_stage)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "automatic_retry_allowed": False,
                "write_may_have_been_submitted": self.write_may_have_been_submitted,
                "reconciliation_required": self.reconciliation_required,
            }
        )
        return payload


@dataclass
class _AssistantStreamMessage:
    message_id: str | None
    channel: str | None = None
    text: str = ""
    finish_reason: str | None = None
    sequences: list[int] = field(default_factory=list)


class TemporaryFinalTextCollector:
    """Collect the terminal visible assistant message without canonical GET.

    PR8.9 already excludes hidden/tool-directed assistant content. PR8.12 adds an
    optional `channel=commentary|final` marker. Explicit final evidence wins;
    otherwise the latest non-commentary visible assistant message is used. This
    supports ordinary one-message answers and commentary->final product turns.
    """

    def __init__(self) -> None:
        self._messages: dict[str, _AssistantStreamMessage] = {}
        self._order: list[str] = []
        self._anonymous_key: str | None = None
        self._last_sequence = 0
        self.observation_count = 0
        self.delivery_incomplete = False
        self.activity_observed = False

    @staticmethod
    def _channel(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized in {"commentary", "final"} else None

    def _message_key(self, event: dict[str, Any], sequence: int) -> str:
        message_id = event.get("message_id")
        if isinstance(message_id, str) and message_id:
            return message_id
        if self._anonymous_key is None:
            self._anonymous_key = f"anonymous:{sequence}"
        return self._anonymous_key

    def apply(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        event_type = event.get("type")
        if event_type in ACTIVITY_EVENT_TYPES:
            self.activity_observed = True
            return
        if event_type not in {
            ASSISTANT_TEXT_SNAPSHOT,
            ASSISTANT_TEXT_DELTA,
            ASSISTANT_TEXT_REVISION,
        }:
            return

        sequence = event.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            self.delivery_incomplete = True
            return
        if sequence <= self._last_sequence:
            return
        if self._last_sequence and sequence != self._last_sequence + 1:
            self.delivery_incomplete = True
        self._last_sequence = sequence

        key = self._message_key(event, sequence)
        state = self._messages.get(key)
        if state is None:
            message_id = event.get("message_id")
            state = _AssistantStreamMessage(
                message_id=message_id if isinstance(message_id, str) and message_id else None
            )
            self._messages[key] = state
            self._order.append(key)

        channel = self._channel(event.get("channel"))
        if channel is not None:
            if state.channel is not None and state.channel != channel:
                self.delivery_incomplete = True
            state.channel = channel

        if event_type == ASSISTANT_TEXT_DELTA:
            delta = event.get("delta")
            if not isinstance(delta, str):
                self.delivery_incomplete = True
                return
            state.text += delta
        else:
            text = event.get("text")
            if not isinstance(text, str):
                self.delivery_incomplete = True
                return
            state.text = text

        finish_reason = event.get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason.strip():
            state.finish_reason = finish_reason.strip()
        state.sequences.append(sequence)
        self.observation_count += 1

    def final_message(self) -> _AssistantStreamMessage | None:
        explicit_final = [
            self._messages[key]
            for key in self._order
            if self._messages[key].channel == "final" and self._messages[key].text
        ]
        if explicit_final:
            return explicit_final[-1]

        visible_candidates = [
            self._messages[key]
            for key in self._order
            if self._messages[key].channel != "commentary" and self._messages[key].text
        ]
        return visible_candidates[-1] if visible_candidates else None


class TemporaryProductWriteRuntime:
    """Browser-owned Temporary product runtime with live-lifecycle authority.

    The lifecycle token is deliberately process-local and never exposed in public
    execution provenance. A process/runtime restart therefore cannot recreate
    continuation authority from a Temporary conversation id or tab id alone.
    """

    def __init__(self, provider: BrowserNativeTurnProvider) -> None:
        self.provider = provider
        self._lock = threading.RLock()
        self._lifecycle_token: str | None = None
        self._conversation_id: str | None = None

    def _bridge_preflight(self) -> None:
        status = self.provider.status()
        if not status.available or not status.extension_connected:
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_BRIDGE_NOT_READY",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="temporary_product_preflight",
            )

    def _binding_for_turn(self, conversation: Any) -> tuple[str, str | None, bool]:
        continuation_id = (
            ConversationRef.from_any(conversation).conversation_id
            if conversation is not None
            else None
        )
        with self._lock:
            if continuation_id is None:
                if self._lifecycle_token is not None:
                    self.close(suppress_errors=True)
                token = str(uuid.uuid4())
                self._lifecycle_token = token
                self._conversation_id = None
                return token, None, False

            if (
                self._lifecycle_token is None
                or self._conversation_id is None
                or continuation_id != self._conversation_id
            ):
                raise TemporaryProductWriteRuntimeError(
                    "PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE: conversation id alone does not grant continuation authority",
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    request_stage="temporary_lifecycle_preflight",
                )
            return self._lifecycle_token, continuation_id, True

    def _turn_rpc(
        self,
        text: str,
        *,
        conversation_id: str | None,
        lifecycle_token: str,
        timeout: float,
        on_event: Callable[[dict[str, Any]], None],
        browser_authority_lease_id: str,
    ) -> dict[str, Any]:
        rpc = getattr(self.provider, "_rpc", None)
        if not callable(rpc):
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_PROVIDER_RPC_UNAVAILABLE",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="temporary_provider_contract",
            )
        request_id = str(uuid.uuid4())
        response = rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "conversationId": conversation_id,
                "text": text,
                "timeoutMs": int(timeout * 1000),
                "canonicalCompleted": False,
                "canonicalCompletedAtMs": None,
                "browserAuthorityLeaseId": browser_authority_lease_id,
                "streamTextObservations": True,
                "conversationMode": "temporary",
                "temporaryLifecycleToken": lifecycle_token,
            },
            timeout=timeout + float(getattr(self.provider, "connect_timeout", 3.0)),
            on_event=on_event,
        )
        if response.get("request_id") != request_id:
            raise TemporaryProductWriteRuntimeError(
                "BROWSER_NATIVE_RESPONSE_MISMATCH",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if response.get("ok") is not True:
            raise TemporaryProductWriteRuntimeError(
                str(response.get("error") or "PR8_13_TEMPORARY_TURN_FAILED"),
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        return response

    @staticmethod
    def _validate_temporary_result(
        response: dict[str, Any],
        *,
        lifecycle_token: str,
        expected_conversation_id: str | None,
    ) -> tuple[str, int]:
        conversation_id = response.get("conversationId")
        status = response.get("responseStatus")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_CONVERSATION_ID_MISSING",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        conversation_id = conversation_id.strip()
        if expected_conversation_id and conversation_id != expected_conversation_id:
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_RETURN_CONVERSATION_MISMATCH",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if not isinstance(status, int) or status != 200:
            raise TemporaryProductWriteRuntimeError(
                f"PR8_13_TEMPORARY_HTTP_STATUS:{status}",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if response.get("conversationMode") != "temporary":
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_MODE_RESULT_MISSING",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if response.get("temporaryModeProven") is not True:
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_MODE_NOT_PROVEN",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if response.get("temporaryPrewriteProof") != TEMPORARY_PREWRITE_PROOF:
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_PREWRITE_PROOF_MISMATCH",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if response.get("temporaryLifecycleToken") != lifecycle_token:
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_LIFECYCLE_TOKEN_MISMATCH",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        if (
            response.get("temporaryLifecycleState") != "LIVE"
            or response.get("temporaryLiveWriteAuthorityProven") is not True
        ):
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_LIVE_AUTHORITY_NOT_PROVEN",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        return conversation_id, status

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: Any = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ProductRuntimeExecution:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        self._bridge_preflight()
        lifecycle_token, expected_conversation_id, is_continuation = self._binding_for_turn(
            conversation
        )
        collector = TemporaryFinalTextCollector()
        browser_authority_lease_id = str(uuid.uuid4())

        def capture_event(event: dict[str, Any]) -> None:
            collector.apply(event)
            if on_event is not None:
                try:
                    on_event(dict(event))
                except Exception:
                    pass

        set_lease = getattr(self.provider, "set_browser_authority_lease", None)
        clear_lease = getattr(self.provider, "clear_browser_authority_lease", None)
        if not callable(set_lease) or not callable(clear_lease):
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_PROVIDER_LEASE_FENCING_UNAVAILABLE",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="temporary_provider_contract",
            )

        started = time.monotonic()
        set_lease(browser_authority_lease_id)
        try:
            response_payload = self._turn_rpc(
                text,
                conversation_id=expected_conversation_id,
                lifecycle_token=lifecycle_token,
                timeout=timeout,
                on_event=capture_event,
                browser_authority_lease_id=browser_authority_lease_id,
            )
        except Exception:
            with self._lock:
                self._lifecycle_token = None
                self._conversation_id = None
            raise
        finally:
            clear_lease()

        conversation_id, response_status = self._validate_temporary_result(
            response_payload,
            lifecycle_token=lifecycle_token,
            expected_conversation_id=expected_conversation_id,
        )
        final_message = collector.final_message()
        if (
            final_message is None
            or not final_message.text
            or collector.delivery_incomplete
        ):
            with self._lock:
                self._lifecycle_token = None
                self._conversation_id = None
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_PAGE_READBACK_INCOMPLETE",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                request_stage="temporary_page_readback",
            )

        with self._lock:
            self._lifecycle_token = lifecycle_token
            self._conversation_id = conversation_id

        elapsed = max(0.0, time.monotonic() - started)
        response = ChatResponse(
            text=final_message.text,
            conversation=ChatConversation(
                conversation_id=conversation_id,
                message_id=final_message.message_id,
                finish_reason=final_message.finish_reason,
            ),
            metrics=ChatMetrics(
                total=elapsed,
                backend_status=response_status,
            ),
            request=ChatRequestDiagnostics(
                conversation_id=conversation_id,
                is_continuation=is_continuation,
                temporary=True,
                turn_exchange_id=(
                    response_payload.get("turnExchangeId")
                    if isinstance(response_payload.get("turnExchangeId"), str)
                    else None
                ),
            ),
        )
        if on_token is not None:
            try:
                on_token(response.text)
            except Exception:
                pass

        observation = TemporaryProductWriteObservation(
            write_event_observed=True,
            conversation_id=conversation_id,
            message_id=final_message.message_id,
            response_status=response_status,
            temporary_mode_proven=True,
            temporary_prewrite_proof=response_payload.get("temporaryPrewriteProof"),
            temporary_continuation_identity_proven=(
                response_payload.get("temporaryContinuationIdentityProven") is True
            ),
            temporary_lifecycle_state="LIVE",
            temporary_live_write_authority_proven=True,
            temporary_paused_conversation_write_count=(
                int(response_payload.get("temporaryPausedConversationWriteCount", 0))
                if isinstance(response_payload.get("temporaryPausedConversationWriteCount"), int)
                else 0
            ),
            stream_observation_count=collector.observation_count,
            stream_delivery_incomplete=collector.delivery_incomplete,
            browser_authority_lease_id=browser_authority_lease_id,
            runtime_tab_id=(
                response_payload.get("tabId")
                if isinstance(response_payload.get("tabId"), int)
                else None
            ),
        )

        mode_provenance = ProductConversationModeProvenance(
            requested_conversation_mode=ConversationMode.TEMPORARY,
            observed_conversation_mode=ConversationMode.TEMPORARY,
            observed_mode_evidence_source=ConversationModeEvidenceSource.PRODUCT_MODE_OBSERVATION,
            observed_mode_proven=True,
            proof_detail=(
                "page-generated conversation POST was paused before network dispatch and "
                "proved history_and_training_disabled=true"
            ),
        )
        lifecycle_provenance = ProductTemporaryLifecycleProvenance(
            temporary_lifecycle_state=TemporaryLifecycleState.LIVE,
            lifecycle_evidence_source=(
                TemporaryLifecycleEvidenceSource.PRODUCT_LIFECYCLE_OBSERVATION
            ),
            lifecycle_state_proven=True,
            live_write_authority_proven=True,
            proof_detail=(
                "opaque process-local lifecycle token is bound to one CWA-owned Temporary "
                "tab and Temporary product conversation; id alone cannot continue it"
            ),
        )
        provenance = ProductExecutionProvenance(
            product_semantics=ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
            transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
            write_plane=TEMPORARY_WRITE_PLANE,
            readback_plane=TEMPORARY_READBACK_PLANE,
            session_plane=TEMPORARY_SESSION_PLANE,
            completion=ProductCompletionProvenance(
                completed=True,
                source=CompletionSource.TRANSPORT_RETURN,
                canonical_completion_proven=False,
                finish_reason=final_message.finish_reason,
                finish_reason_observed=final_message.finish_reason is not None,
                finality_detail=(
                    "page-owned Temporary terminal assistant stream; ordinary canonical "
                    "conversation GET is intentionally not claimed"
                ),
            ),
            identity=ProductIdentityProvenance(
                conversation_id=conversation_id,
                message_id=final_message.message_id,
                observed_model=None,
            ),
            transport_metadata=observation.to_dict(),
            conversation_mode=mode_provenance,
            temporary_lifecycle=lifecycle_provenance,
        )
        return ProductRuntimeExecution(
            transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
            response=response,
            observation=observation,
            provenance=provenance,
        )

    def send_text(self, text: str, **kwargs: Any) -> ChatResponse:
        return self.send_text_observed(text, **kwargs).response

    def close(self, *, suppress_errors: bool = False) -> bool:
        with self._lock:
            token = self._lifecycle_token
            conversation_id = self._conversation_id
        if token is None:
            return False

        rpc = getattr(self.provider, "_rpc", None)
        if not callable(rpc):
            if suppress_errors:
                with self._lock:
                    self._lifecycle_token = None
                    self._conversation_id = None
                return False
            raise TemporaryProductWriteRuntimeError(
                "PR8_13_TEMPORARY_PROVIDER_RPC_UNAVAILABLE",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="temporary_lifecycle_close",
            )

        request_id = str(uuid.uuid4())
        try:
            result = rpc(
                {
                    "type": "turn",
                    "request_id": request_id,
                    "endTemporaryLifecycle": True,
                    "temporaryLifecycleToken": token,
                    "conversationId": conversation_id,
                },
                timeout=10.0 + float(getattr(self.provider, "connect_timeout", 3.0)),
            )
            if (
                result.get("request_id") != request_id
                or result.get("ok") is not True
                or result.get("temporaryLifecycleState") != "ENDED"
            ):
                raise TemporaryProductWriteRuntimeError(
                    "PR8_13_TEMPORARY_LIFECYCLE_END_NOT_PROVEN",
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    request_stage="temporary_lifecycle_close",
                )
        except Exception:
            if not suppress_errors:
                raise
            return False
        finally:
            with self._lock:
                self._lifecycle_token = None
                self._conversation_id = None
        return True

    def lifecycle_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": "LIVE" if self._lifecycle_token is not None else "NOT_ESTABLISHED",
                "conversation_id": self._conversation_id,
                "token_present": self._lifecycle_token is not None,
                "token_exported": False,
            }
