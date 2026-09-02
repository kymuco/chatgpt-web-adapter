from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from .browser_authority_lease import (
    BrowserAuthorityLease,
    BrowserAuthorityLeaseState,
    BrowserAuthorityPolicy,
    TurnLifecycle,
    TurnLifecycleState,
)
from .browser_native_client import (
    BrowserNativeSubmission,
    await_browser_native_final,
    submit_browser_native,
)
from .browser_owned_write_runtime import (
    BROWSER_AUTHORITY_RELEASE_UNSUPPORTED,
    CANONICAL_READ_UNAVAILABLE,
    CONVERSATION_NOT_COMPLETED,
    WRITE_ACCEPTED_READBACK_INCOMPLETE,
    WRITE_OUTCOME_UNKNOWN,
    BrowserOwnedWriteObservation,
    BrowserOwnedWriteRuntimeError,
    _canonical_status_value,
    _conversation_id,
    _optional_int,
    _optional_text,
)
from .exceptions import ConversationTimeoutError, RequestError, WebChatAdapterError
from .types import ChatConversation, ChatResponse, ConversationRef

SUBMISSION_FINALITY_PENDING = "BROWSER_OWNED_SUBMISSION_FINALITY_PENDING"
SUBMISSION_HANDLE_INVALID = "BROWSER_OWNED_SUBMISSION_HANDLE_INVALID"


@dataclass(frozen=True)
class BrowserOwnedSubmissionAck:
    submission_id: str
    conversation_id: str | None
    turn_exchange_id: str | None
    accepted_at_ms: int
    observation: BrowserOwnedWriteObservation


@dataclass
class _PendingSubmission:
    submission_id: str
    lease: BrowserAuthorityLease
    turn: TurnLifecycle
    native: BrowserNativeSubmission | None
    write_event_observed: bool
    delegated_conversation_id: str | None
    runtime_tab_id: int | None
    readback_ack_attempted: bool = False
    readback_acknowledged: bool = False


class BrowserOwnedSubmissionLifecycle:
    """Split submit/finality facade over the existing browser-owned runtime.

    Browser Authority remains owned by the lower browser-owned runtime. This class
    turns the already-existing write/readback event boundary into a first-class
    synchronous API and allows at most one pending or in-flight split submission
    per product transport instance.
    """

    def __init__(self, runtime: Any) -> None:
        # Keep the long-standing BrowserOwnedProductTransport constructor seam
        # structural. Tests and downstream integrations may substitute a compatible
        # lower runtime; split operations validate the methods they actually use.
        self.runtime = runtime
        self._lock = threading.RLock()
        self._pending: _PendingSubmission | None = None
        self._dispatch_reserved = False

    @property
    def pending_submission_id(self) -> str | None:
        with self._lock:
            return self._pending.submission_id if self._pending is not None else None

    def _pending_or_reserved_label(self) -> str | None:
        with self._lock:
            if self._pending is not None:
                return self._pending.submission_id
            if self._dispatch_reserved:
                return "DISPATCH_IN_PROGRESS"
            return None

    def ensure_no_pending_submission(self) -> None:
        pending = self._pending_or_reserved_label()
        if pending is None:
            return
        raise BrowserOwnedWriteRuntimeError(
            f"browser-owned submission {pending} is awaiting canonical finality",
            failure_kind=SUBMISSION_FINALITY_PENDING,
            automatic_retry_allowed=False,
            manual_retry_safe_after_repair=True,
            write_may_have_been_submitted=False,
            reconciliation_required=False,
            request_stage="browser_owned_submission_preflight",
        )

    def _reserve_dispatch(self) -> None:
        with self._lock:
            if self._pending is not None or self._dispatch_reserved:
                pending = (
                    self._pending.submission_id
                    if self._pending is not None
                    else "DISPATCH_IN_PROGRESS"
                )
                raise BrowserOwnedWriteRuntimeError(
                    f"browser-owned submission {pending} is awaiting canonical finality",
                    failure_kind=SUBMISSION_FINALITY_PENDING,
                    automatic_retry_allowed=False,
                    manual_retry_safe_after_repair=True,
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    request_stage="browser_owned_submission_preflight",
                )
            # Reservation is published before health/authority checks and before
            # the provider call. Competing compatibility/Temporary writes call
            # ensure_no_pending_submission() and therefore fail before delegation.
            self._dispatch_reserved = True

    def _clear_dispatch_reservation(self) -> None:
        with self._lock:
            self._dispatch_reserved = False

    def _validate_inputs(self, text: str, *, timeout: float, poll_interval: float) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

    def _prepare_authority(
        self,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None,
        browser_authority_policy: BrowserAuthorityPolicy | str | None,
        browser_authority_ttl_ms: int | None,
    ) -> tuple[BrowserAuthorityLease, TurnLifecycle]:
        resolution = self.runtime._resolve_authority_policy(
            browser_authority_policy=browser_authority_policy,
            browser_authority_ttl_ms=browser_authority_ttl_ms,
        )
        provider = self.runtime.provider
        set_lease = getattr(provider, "set_browser_authority_lease", None)
        clear_lease = getattr(provider, "clear_browser_authority_lease", None)
        if resolution.policy is not BrowserAuthorityPolicy.PERSISTENT and (
            not callable(getattr(provider, "release_runtime_tab", None))
            or not callable(set_lease)
            or not callable(clear_lease)
        ):
            raise BrowserOwnedWriteRuntimeError(
                "disposable browser authority requires provider release + lease fencing",
                failure_kind=BROWSER_AUTHORITY_RELEASE_UNSUPPORTED,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=True,
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="browser_authority_policy",
            )

        preflight = self.runtime.health(conversation)
        if not preflight.ready:
            raise BrowserOwnedWriteRuntimeError(
                f"browser-owned write preflight failed: {preflight.reason}",
                failure_kind=preflight.reason,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=True,
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="browser_owned_write_preflight",
            )

        if conversation is not None:
            try:
                commit_status = _canonical_status_value(self.runtime.client, conversation)
            except Exception as error:
                raise BrowserOwnedWriteRuntimeError(
                    "browser-owned write commit check failed: canonical read unavailable",
                    failure_kind=CANONICAL_READ_UNAVAILABLE,
                    automatic_retry_allowed=False,
                    manual_retry_safe_after_repair=True,
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    cause=error,
                    request_stage="browser_owned_write_preflight",
                ) from error
            if commit_status != "completed":
                raise BrowserOwnedWriteRuntimeError(
                    f"browser-owned write commit check failed: canonical status={commit_status}",
                    failure_kind=CONVERSATION_NOT_COMPLETED,
                    automatic_retry_allowed=False,
                    manual_retry_safe_after_repair=True,
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    request_stage="browser_owned_write_preflight",
                )

        fresh_authority = self.runtime._fresh_browser_authority_status()
        return self.runtime._issue_authority(
            resolution=resolution,
            status=fresh_authority,
        )

    def _acknowledge_readback(self, state: _PendingSubmission) -> bool:
        complete_readback = getattr(self.runtime.client, "complete_canonical_readback", None)
        if not callable(complete_readback):
            return True
        if state.readback_ack_attempted:
            return state.readback_acknowledged
        state.readback_ack_attempted = True
        state.readback_acknowledged = complete_readback() is True
        return state.readback_acknowledged

    def _runtime_event(
        self,
        state: _PendingSubmission,
        external_on_event: Callable[[dict[str, Any]], None] | None,
        event: dict[str, Any],
    ) -> None:
        forwarded = event
        browser_context_readback = callable(
            getattr(self.runtime.client, "complete_canonical_readback", None)
        )
        if isinstance(event, dict) and event.get("type") == "browser_native_write_completed":
            state.write_event_observed = True
            state.delegated_conversation_id = (
                _optional_text(event.get("conversation_id"))
                or state.delegated_conversation_id
            )
            state.runtime_tab_id = _optional_int(event.get("runtime_tab_id"))
            if browser_context_readback:
                state.lease, state.turn, forwarded = self.runtime._record_write_completion(
                    state.lease,
                    state.turn,
                    event,
                )
            else:
                state.lease, state.turn, forwarded = self.runtime._release_authority_from_write_event(
                    state.lease,
                    state.turn,
                    event,
                )
        elif isinstance(event, dict) and event.get("type") == "browser_native_readback_completed":
            if browser_context_readback and state.write_event_observed:
                if not self._acknowledge_readback(state):
                    raise RequestError(
                        "BROWSER_NATIVE_READBACK_ACKNOWLEDGEMENT_FAILED",
                        request_stage="browser_native_canonical_read",
                    )
                state.lease = self.runtime._release_authority_after_readback(
                    state.lease,
                    runtime_tab_id=state.runtime_tab_id,
                )
            state.turn = self.runtime._finalize_turn(state.turn)
            forwarded = dict(event)
            forwarded.update(
                {
                    "browser_authority_lease_id": state.lease.lease_id,
                    "browser_authority_released_at_ms": state.lease.released_at_ms,
                    "browser_authority_disposal_due_at_ms": state.lease.disposal_due_at_ms,
                    "browser_authority_release_proven": state.lease.authority_release_proven,
                    "browser_authority_disposal_action": (
                        "CLOSE" if state.lease.disposal_allowed else "KEEP"
                    ),
                    "turn_lifecycle_id": state.turn.lifecycle_id,
                    "turn_lifecycle_state": state.turn.state.value,
                }
            )
        if external_on_event is not None:
            try:
                external_on_event(forwarded)
            except Exception:
                pass

    def _mark_submit_failure(
        self,
        state: _PendingSubmission,
        error: WebChatAdapterError,
    ) -> BrowserOwnedWriteRuntimeError:
        state.turn = self.runtime._fail_turn(
            state.turn,
            state=TurnLifecycleState.AMBIGUOUS,
        )
        if state.lease.state is BrowserAuthorityLeaseState.ACTIVE:
            state.lease = self.runtime._mark_release_unknown(state.lease)
        return BrowserOwnedWriteRuntimeError(
            str(error),
            failure_kind=WRITE_OUTCOME_UNKNOWN,
            automatic_retry_allowed=False,
            manual_retry_safe_after_repair=False,
            write_may_have_been_submitted=True,
            reconciliation_required=True,
            cause=error,
            request_stage="browser_owned_write",
            conversation_id=(
                getattr(error, "conversation_id", None)
                or state.delegated_conversation_id
            ),
            reason_code=getattr(error, "reason_code", None),
            status_code=getattr(error, "status_code", None),
            content_type=getattr(error, "content_type", None),
            browser_authority_lease=state.lease,
            turn_lifecycle=state.turn,
        )

    def submit_text(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> BrowserOwnedSubmissionAck:
        self._validate_inputs(text, timeout=timeout, poll_interval=poll_interval)
        self._reserve_dispatch()
        try:
            lease, turn = self._prepare_authority(
                conversation=conversation,
                browser_authority_policy=browser_authority_policy,
                browser_authority_ttl_ms=browser_authority_ttl_ms,
            )
            state = _PendingSubmission(
                submission_id="pending",
                lease=lease,
                turn=turn,
                native=None,
                write_event_observed=False,
                delegated_conversation_id=_conversation_id(conversation),
                runtime_tab_id=None,
            )
            provider = self.runtime.provider
            set_lease = getattr(provider, "set_browser_authority_lease", None)
            clear_lease = getattr(provider, "clear_browser_authority_lease", None)

            def runtime_event(event: dict[str, Any]) -> None:
                self._runtime_event(state, on_event, event)

            if callable(set_lease):
                set_lease(lease.lease_id)
            try:
                native = submit_browser_native(
                    self.runtime.client,
                    text,
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    on_token=on_token,
                    on_event=runtime_event,
                )
            except WebChatAdapterError as error:
                raise self._mark_submit_failure(state, error) from error
            finally:
                if callable(clear_lease):
                    clear_lease()

            state.native = native
            state.submission_id = native.submission_id
            state.delegated_conversation_id = native.turn.conversation_id
            state.runtime_tab_id = _optional_int(getattr(native.turn, "tab_id", None))
            if not state.write_event_observed:
                synthetic_event = {
                    "type": "browser_native_write_completed",
                    "submission_id": native.submission_id,
                    "accepted_at_ms": native.accepted_at_ms,
                    "conversation_id": native.turn.conversation_id,
                    "turn_exchange_id": native.turn.turn_exchange_id,
                    "runtime_tab_id": native.turn.tab_id,
                }
                self._runtime_event(state, None, synthetic_event)

            with self._lock:
                # _dispatch_reserved remains true until after this assignment, so
                # no competing split/compatibility/Temporary operation can pass
                # its prewrite pending check between provider return and ack publish.
                if self._pending is not None:
                    if state.lease.state is BrowserAuthorityLeaseState.ACTIVE:
                        state.lease = self.runtime._mark_release_unknown(state.lease)
                    raise BrowserOwnedWriteRuntimeError(
                        "browser-owned submission slot changed during dispatch",
                        failure_kind=SUBMISSION_FINALITY_PENDING,
                        automatic_retry_allowed=False,
                        manual_retry_safe_after_repair=False,
                        write_may_have_been_submitted=True,
                        reconciliation_required=True,
                        request_stage="browser_owned_submission_commit",
                        conversation_id=state.delegated_conversation_id,
                        browser_authority_lease=state.lease,
                        turn_lifecycle=state.turn,
                    )
                self._pending = state

            observation = BrowserOwnedWriteObservation.from_event(
                {
                    "runtime_tab_id": state.runtime_tab_id,
                    "browser_authority_lease_id": state.lease.lease_id,
                    "browser_authority_generation": state.lease.generation,
                    "browser_authority_policy": state.lease.policy.value,
                    "browser_authority_ttl_ms": state.lease.ttl_ms,
                    "browser_authority_issued_at_ms": state.lease.issued_at_ms,
                    "browser_authority_released_at_ms": state.lease.released_at_ms,
                    "browser_authority_disposal_due_at_ms": state.lease.disposal_due_at_ms,
                    "browser_authority_release_proven": state.lease.authority_release_proven,
                    "browser_authority_disposal_action": (
                        "PENDING_CANONICAL_READBACK"
                        if state.lease.state is BrowserAuthorityLeaseState.ACTIVE
                        else ("CLOSE" if state.lease.disposal_allowed else "KEEP")
                    ),
                    "turn_lifecycle_id": state.turn.lifecycle_id,
                    "turn_lifecycle_state": state.turn.state.value,
                }
            )
            return BrowserOwnedSubmissionAck(
                submission_id=native.submission_id,
                conversation_id=native.turn.conversation_id,
                turn_exchange_id=native.turn.turn_exchange_id,
                accepted_at_ms=native.accepted_at_ms,
                observation=observation,
            )
        finally:
            self._clear_dispatch_reservation()

    def _require_pending(self, submission_id: str) -> _PendingSubmission:
        if not isinstance(submission_id, str) or not submission_id.strip():
            raise ValueError("submission_id is required")
        with self._lock:
            state = self._pending
            if state is None or state.submission_id != submission_id.strip():
                raise BrowserOwnedWriteRuntimeError(
                    "submission handle is not pending on this runtime",
                    failure_kind=SUBMISSION_HANDLE_INVALID,
                    automatic_retry_allowed=False,
                    manual_retry_safe_after_repair=True,
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    request_stage="browser_owned_submission_await",
                )
            return state

    def await_final(self, submission_id: str) -> ChatResponse:
        state = self._require_pending(submission_id)
        if state.native is None:
            raise RuntimeError("pending submission is missing native state")

        provider = self.runtime.provider
        set_lease = getattr(provider, "set_browser_authority_lease", None)
        clear_lease = getattr(provider, "clear_browser_authority_lease", None)
        browser_context_readback = callable(
            getattr(self.runtime.client, "complete_canonical_readback", None)
        )
        if callable(set_lease):
            set_lease(state.lease.lease_id)
        try:
            response = await_browser_native_final(self.runtime.client, state.native)
            state.turn = self.runtime._finalize_turn(state.turn)
            if state.lease.state is BrowserAuthorityLeaseState.ACTIVE:
                state.lease = self.runtime._mark_release_unknown(state.lease)
            return response
        except ConversationTimeoutError as error:
            state.turn = self.runtime._fail_turn(
                state.turn,
                state=TurnLifecycleState.READBACK_INCOMPLETE,
            )
            if (
                browser_context_readback
                and state.write_event_observed
                and self._acknowledge_readback(state)
            ):
                state.lease = self.runtime._release_authority_after_readback(
                    state.lease,
                    runtime_tab_id=state.runtime_tab_id,
                )
            elif state.lease.state is BrowserAuthorityLeaseState.ACTIVE:
                state.lease = self.runtime._mark_release_unknown(state.lease)
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=WRITE_ACCEPTED_READBACK_INCOMPLETE,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage="browser_owned_write_readback",
                conversation_id=state.delegated_conversation_id,
                reason_code="CANONICAL_READ_TIMEOUT",
                browser_authority_lease=state.lease,
                turn_lifecycle=state.turn,
            ) from error
        except WebChatAdapterError as error:
            state.turn = self.runtime._fail_turn(
                state.turn,
                state=TurnLifecycleState.READBACK_INCOMPLETE,
            )
            if (
                browser_context_readback
                and state.write_event_observed
                and self._acknowledge_readback(state)
            ):
                state.lease = self.runtime._release_authority_after_readback(
                    state.lease,
                    runtime_tab_id=state.runtime_tab_id,
                )
            elif state.lease.state is BrowserAuthorityLeaseState.ACTIVE:
                state.lease = self.runtime._mark_release_unknown(state.lease)
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=WRITE_ACCEPTED_READBACK_INCOMPLETE,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage="browser_owned_write_readback",
                conversation_id=(
                    getattr(error, "conversation_id", None)
                    or state.delegated_conversation_id
                ),
                reason_code=getattr(error, "reason_code", None),
                status_code=getattr(error, "status_code", None),
                content_type=getattr(error, "content_type", None),
                browser_authority_lease=state.lease,
                turn_lifecycle=state.turn,
            ) from error
        finally:
            try:
                if browser_context_readback:
                    self._acknowledge_readback(state)
            finally:
                if callable(clear_lease):
                    clear_lease()
                with self._lock:
                    if self._pending is state:
                        self._pending = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self._pending
            if state is None:
                return {
                    "pending": False,
                    "dispatch_reserved": self._dispatch_reserved,
                    "submission_id": None,
                    "conversation_id": None,
                    "turn_lifecycle_id": None,
                }
            return {
                "pending": True,
                "dispatch_reserved": self._dispatch_reserved,
                "submission_id": state.submission_id,
                "conversation_id": state.delegated_conversation_id,
                "turn_lifecycle_id": state.turn.lifecycle_id,
                "turn_lifecycle_state": state.turn.state.value,
                "browser_authority_state": state.lease.state.value,
                "canonical_finality_proven": False,
            }
