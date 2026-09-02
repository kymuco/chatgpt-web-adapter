from __future__ import annotations

from dataclasses import asdict, dataclass
import threading
import time
from typing import Any, Callable

from .browser_authority_lease import (
    BrowserAuthorityLease,
    BrowserAuthorityLeaseState,
    BrowserAuthorityPolicy,
    BrowserAuthorityPolicyResolution,
    TurnLifecycle,
    TurnLifecycleState,
    resolve_browser_authority_policy,
)
from .browser_context_canonical import BROWSER_CONTEXT_CANONICAL_READ_PLANE
from .browser_native_client import send_browser_native, set_browser_native_turn_provider
from .browser_native_provider import BrowserNativeBridgeStatus, BrowserNativeTurnProvider
from .exceptions import ConversationTimeoutError, RequestError, WebChatAdapterError
from .types import ChatConversation, ChatResponse, ConversationRef

READY = "READY_FOR_BROWSER_OWNED_WRITE"
BRIDGE_UNAVAILABLE = "BROWSER_NATIVE_BRIDGE_UNAVAILABLE"
EXTENSION_DISCONNECTED = "BROWSER_NATIVE_EXTENSION_DISCONNECTED"
CANONICAL_READ_UNAVAILABLE = "CANONICAL_READ_UNAVAILABLE"
CONVERSATION_NOT_COMPLETED = "CANONICAL_CONVERSATION_NOT_COMPLETED"
WRITE_OUTCOME_UNKNOWN = "BROWSER_OWNED_WRITE_OUTCOME_UNKNOWN"
WRITE_ACCEPTED_READBACK_INCOMPLETE = "BROWSER_OWNED_WRITE_ACCEPTED_READBACK_INCOMPLETE"
BROWSER_AUTHORITY_RELEASE_UNSUPPORTED = "BROWSER_AUTHORITY_RELEASE_UNSUPPORTED"
BROWSER_AUTHORITY_NOT_FRESH = "BROWSER_AUTHORITY_NOT_FRESH"

LEGACY_READ_PLANE = "BROWSERLESS_CANONICAL_HTTP"
# Historical module-level compatibility constant. Production instances select
# BROWSER_CONTEXT_CANONICAL_READ_PLANE only when their canonical client owns that
# read transport; injected/custom clients retain the legacy read plane.
READ_PLANE = LEGACY_READ_PLANE
SESSION_PLANE = "BROWSERLESS_SESSION_HTTP"
WRITE_PLANE = "BROWSER_NATIVE_PAGE_OWNED_WRITE"

TRANSPORT_DEFAULT_BROWSER_AUTHORITY_POLICY = BrowserAuthorityPolicy.PERSISTENT


def _monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


@dataclass(frozen=True)
class BrowserOwnedWriteRuntimeHealth:
    ready: bool
    reason: str
    bridge_available: bool
    extension_connected: bool
    runtime_tab_id: int | None
    runtime_tab_preexisting: bool
    conversation_id: str | None
    canonical_status: str | None
    canonical_read_checked: bool
    canonical_read_reason_code: str | None = None
    canonical_read_status_code: int | None = None
    canonical_read_content_type: str | None = None
    read_plane: str = READ_PLANE
    session_plane: str = SESSION_PLANE
    write_plane: str = WRITE_PLANE
    automatic_write_retry: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class BrowserOwnedWriteObservation:
    write_event_observed: bool
    runtime_tab_id: int | None = None
    runtime_tab_preexisting: bool | None = None
    runtime_tab_created_for_turn: bool | None = None
    tab_was_active_at_write_start: bool | None = None
    tab_active_after_write: bool | None = None
    tab_activated_during_turn: bool | None = None
    foreground_activation_observed: bool | None = None
    browser_authority_lease_id: str | None = None
    browser_authority_generation: int | None = None
    browser_authority_policy: str | None = None
    browser_authority_ttl_ms: int | None = None
    browser_authority_issued_at_ms: int | None = None
    browser_authority_released_at_ms: int | None = None
    browser_authority_disposal_due_at_ms: int | None = None
    browser_authority_release_proven: bool | None = None
    browser_authority_disposal_action: str | None = None
    turn_lifecycle_id: str | None = None
    turn_lifecycle_state_at_write: str | None = None

    @classmethod
    def from_event(cls, event: dict[str, Any] | None) -> "BrowserOwnedWriteObservation":
        if not isinstance(event, dict):
            return cls(write_event_observed=False)
        tab_id = event.get("runtime_tab_id")
        return cls(
            write_event_observed=True,
            runtime_tab_id=tab_id if isinstance(tab_id, int) and not isinstance(tab_id, bool) else None,
            runtime_tab_preexisting=_optional_bool(event.get("runtime_tab_preexisting")),
            runtime_tab_created_for_turn=_optional_bool(event.get("runtime_tab_created_for_turn")),
            tab_was_active_at_write_start=_optional_bool(event.get("tab_was_active_at_write_start")),
            tab_active_after_write=_optional_bool(event.get("tab_active_after_write")),
            tab_activated_during_turn=_optional_bool(event.get("tab_activated_during_turn")),
            foreground_activation_observed=_optional_bool(event.get("foreground_activation_observed")),
            browser_authority_lease_id=_optional_text(event.get("browser_authority_lease_id")),
            browser_authority_generation=_optional_int(event.get("browser_authority_generation")),
            browser_authority_policy=_optional_text(event.get("browser_authority_policy")),
            browser_authority_ttl_ms=_optional_int(event.get("browser_authority_ttl_ms")),
            browser_authority_issued_at_ms=_optional_int(event.get("browser_authority_issued_at_ms")),
            browser_authority_released_at_ms=_optional_int(event.get("browser_authority_released_at_ms")),
            browser_authority_disposal_due_at_ms=_optional_int(
                event.get("browser_authority_disposal_due_at_ms")
            ),
            browser_authority_release_proven=_optional_bool(
                event.get("browser_authority_release_proven")
            ),
            browser_authority_disposal_action=_optional_text(
                event.get("browser_authority_disposal_action")
            ),
            turn_lifecycle_id=_optional_text(event.get("turn_lifecycle_id")),
            turn_lifecycle_state_at_write=_optional_text(
                event.get("turn_lifecycle_state")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserOwnedWriteExecution:
    response: ChatResponse
    observation: BrowserOwnedWriteObservation


class BrowserOwnedWriteRuntimeError(RequestError):
    """Failure from the production browser-owned write facade.

    ``automatic_retry_allowed`` is intentionally false for every failure that
    happens after delegation to the browser-native provider. At that point the
    protected ChatGPT write may already have been submitted and retrying could
    duplicate the user turn.
    """

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str,
        automatic_retry_allowed: bool,
        manual_retry_safe_after_repair: bool,
        write_may_have_been_submitted: bool,
        reconciliation_required: bool,
        cause: BaseException | None = None,
        request_stage: str,
        conversation_id: str | None = None,
        reason_code: str | None = None,
        status_code: int | None = None,
        content_type: str | None = None,
        browser_authority_lease: BrowserAuthorityLease | None = None,
        turn_lifecycle: TurnLifecycle | None = None,
    ) -> None:
        self.failure_kind = failure_kind
        self.automatic_retry_allowed = bool(automatic_retry_allowed)
        self.manual_retry_safe_after_repair = bool(manual_retry_safe_after_repair)
        self.write_may_have_been_submitted = bool(write_may_have_been_submitted)
        self.reconciliation_required = bool(reconciliation_required)
        self.cause = cause
        self.conversation_id = conversation_id
        self.reason_code = reason_code
        self.content_type = content_type
        self.browser_authority_lease = browser_authority_lease
        self.turn_lifecycle = turn_lifecycle
        super().__init__(
            message,
            status_code=status_code,
            endpoint="conversation" if request_stage == "browser_owned_write_readback" else None,
            request_stage=request_stage,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "failure_kind": self.failure_kind,
                "automatic_retry_allowed": self.automatic_retry_allowed,
                "manual_retry_safe_after_repair": self.manual_retry_safe_after_repair,
                "write_may_have_been_submitted": self.write_may_have_been_submitted,
                "reconciliation_required": self.reconciliation_required,
                "conversation_id": self.conversation_id,
                "reason_code": self.reason_code,
                "content_type": self.content_type,
                "browser_authority_lease": (
                    self.browser_authority_lease.to_dict()
                    if self.browser_authority_lease is not None
                    else None
                ),
                "turn_lifecycle": (
                    self.turn_lifecycle.to_dict()
                    if self.turn_lifecycle is not None
                    else None
                ),
            }
        )
        return payload


def _conversation_id(
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None,
) -> str | None:
    if conversation is None:
        return None
    return ConversationRef.from_any(conversation).conversation_id


def _canonical_status_value(client: Any, conversation: Any) -> str | None:
    status = client.get_status(conversation)
    value = getattr(status, "status", None)
    return value if isinstance(value, str) else None


class BrowserOwnedProductWriteRuntime:
    """Production facade that confines browser ownership to ChatGPT product writes.

    PR8.8 separates the Browser Authority Lease from the logical Turn Lifecycle.
    The compatibility default is PERSISTENT: no tab disposal behavior changes
    unless IDLE_TTL or TURN_SCOPED is explicitly selected.
    """

    def __init__(
        self,
        client: Any,
        *,
        provider: BrowserNativeTurnProvider | None = None,
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> None:
        self.client = client
        self.provider = provider or BrowserNativeTurnProvider()
        set_browser_native_turn_provider(self.client, self.provider)
        self._browser_context_readback = callable(
            getattr(self.client, "complete_canonical_readback", None)
        )
        self._read_plane = (
            BROWSER_CONTEXT_CANONICAL_READ_PLANE
            if self._browser_context_readback
            else LEGACY_READ_PLANE
        )
        self._browser_authority_runtime_policy = browser_authority_policy
        self._browser_authority_runtime_ttl_ms = browser_authority_ttl_ms
        resolve_browser_authority_policy(
            runtime_policy=browser_authority_policy,
            runtime_ttl_ms=browser_authority_ttl_ms,
        )

        self._authority_lock = threading.RLock()
        self._authority_generation = 0
        self._pending_disposal_timer: threading.Timer | None = None
        self._last_browser_authority_lease: BrowserAuthorityLease | None = None
        self._last_turn_lifecycle: TurnLifecycle | None = None
        self._last_disposal_result: dict[str, Any] | None = None

    def _health(
        self,
        *,
        ready: bool,
        reason: str,
        bridge_available: bool,
        extension_connected: bool,
        runtime_tab_id: int | None,
        conversation_id: str | None,
        canonical_status: str | None,
        canonical_read_checked: bool,
        canonical_read_reason_code: str | None = None,
        canonical_read_status_code: int | None = None,
        canonical_read_content_type: str | None = None,
    ) -> BrowserOwnedWriteRuntimeHealth:
        return BrowserOwnedWriteRuntimeHealth(
            ready=ready,
            reason=reason,
            bridge_available=bridge_available,
            extension_connected=extension_connected,
            runtime_tab_id=runtime_tab_id,
            runtime_tab_preexisting=runtime_tab_id is not None,
            conversation_id=conversation_id,
            canonical_status=canonical_status,
            canonical_read_checked=canonical_read_checked,
            canonical_read_reason_code=canonical_read_reason_code,
            canonical_read_status_code=canonical_read_status_code,
            canonical_read_content_type=canonical_read_content_type,
            read_plane=self._read_plane,
        )

    def health(
        self,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
    ) -> BrowserOwnedWriteRuntimeHealth:
        conversation_id = _conversation_id(conversation)
        bridge: BrowserNativeBridgeStatus = self.provider.status()

        if not bridge.available:
            return self._health(
                ready=False,
                reason=BRIDGE_UNAVAILABLE,
                bridge_available=False,
                extension_connected=False,
                runtime_tab_id=bridge.runtime_tab_id,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=False,
            )
        if not bridge.extension_connected:
            return self._health(
                ready=False,
                reason=EXTENSION_DISCONNECTED,
                bridge_available=True,
                extension_connected=False,
                runtime_tab_id=bridge.runtime_tab_id,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=False,
            )
        if conversation is None:
            return self._health(
                ready=True,
                reason=READY,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                conversation_id=None,
                canonical_status=None,
                canonical_read_checked=False,
            )

        try:
            canonical_status = _canonical_status_value(self.client, conversation)
        except Exception as error:
            return self._health(
                ready=False,
                reason=CANONICAL_READ_UNAVAILABLE,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=True,
                canonical_read_reason_code=getattr(error, "reason_code", type(error).__name__),
                canonical_read_status_code=getattr(error, "status_code", None),
                canonical_read_content_type=getattr(error, "content_type", None),
            )

        if canonical_status != "completed":
            return self._health(
                ready=False,
                reason=CONVERSATION_NOT_COMPLETED,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                conversation_id=conversation_id,
                canonical_status=canonical_status,
                canonical_read_checked=True,
            )

        return self._health(
            ready=True,
            reason=READY,
            bridge_available=True,
            extension_connected=True,
            runtime_tab_id=bridge.runtime_tab_id,
            conversation_id=conversation_id,
            canonical_status=canonical_status,
            canonical_read_checked=True,
        )

    def _resolve_authority_policy(
        self,
        *,
        browser_authority_policy: BrowserAuthorityPolicy | str | None,
        browser_authority_ttl_ms: int | None,
    ) -> BrowserAuthorityPolicyResolution:
        return resolve_browser_authority_policy(
            per_turn_policy=browser_authority_policy,
            per_turn_ttl_ms=browser_authority_ttl_ms,
            runtime_policy=self._browser_authority_runtime_policy,
            runtime_ttl_ms=self._browser_authority_runtime_ttl_ms,
            transport_policy=TRANSPORT_DEFAULT_BROWSER_AUTHORITY_POLICY,
        )

    def _fresh_browser_authority_status(self) -> BrowserNativeBridgeStatus:
        status = self.provider.status()
        if not status.available:
            raise BrowserOwnedWriteRuntimeError(
                "browser authority commit check failed: bridge unavailable",
                failure_kind=BRIDGE_UNAVAILABLE,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=True,
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="browser_authority_commit",
            )
        if not status.extension_connected:
            raise BrowserOwnedWriteRuntimeError(
                "browser authority commit check failed: extension disconnected",
                failure_kind=EXTENSION_DISCONNECTED,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=True,
                write_may_have_been_submitted=False,
                reconciliation_required=False,
                request_stage="browser_authority_commit",
            )
        return status

    def _issue_authority(
        self,
        *,
        resolution: BrowserAuthorityPolicyResolution,
        status: BrowserNativeBridgeStatus,
    ) -> tuple[BrowserAuthorityLease, TurnLifecycle]:
        with self._authority_lock:
            self._authority_generation += 1
            generation = self._authority_generation
            if self._pending_disposal_timer is not None:
                self._pending_disposal_timer.cancel()
                self._pending_disposal_timer = None
            now = _monotonic_ms()
            lease = BrowserAuthorityLease.issue(
                generation=generation,
                resolution=resolution,
                issued_at_ms=now,
                runtime_tab_id=status.runtime_tab_id,
            )
            turn = TurnLifecycle.prepare(
                browser_authority_lease_id=lease.lease_id,
                started_at_ms=now,
            ).dispatched()
            self._last_browser_authority_lease = lease
            self._last_turn_lifecycle = turn
            self._last_disposal_result = None
            return lease, turn

    def _mark_release_unknown(
        self,
        lease: BrowserAuthorityLease,
    ) -> BrowserAuthorityLease:
        with self._authority_lock:
            current = self._last_browser_authority_lease
            if current is not None and current.lease_id == lease.lease_id:
                current = current.release_unknown()
                self._last_browser_authority_lease = current
                return current
        return lease.release_unknown()

    def _schedule_disposal(self, lease: BrowserAuthorityLease) -> None:
        if not lease.disposal_allowed or lease.disposal_due_at_ms is None:
            return

        release_runtime_tab = getattr(self.provider, "release_runtime_tab", None)
        if not callable(release_runtime_tab):
            with self._authority_lock:
                self._last_disposal_result = {
                    "lease_id": lease.lease_id,
                    "status": "UNSUPPORTED",
                    "automatic_retry": False,
                }
            return

        delay_seconds = max(0.0, (lease.disposal_due_at_ms - _monotonic_ms()) / 1000.0)

        def dispose_if_still_current() -> None:
            with self._authority_lock:
                current = self._last_browser_authority_lease
                if (
                    current is None
                    or current.lease_id != lease.lease_id
                    or current.generation != lease.generation
                    or self._authority_generation != lease.generation
                    or current.state is not BrowserAuthorityLeaseState.RELEASED
                ):
                    return
                try:
                    result = release_runtime_tab(
                        expected_runtime_tab_id=lease.runtime_tab_id_at_release,
                        browser_authority_lease_id=lease.lease_id,
                        timeout=10.0,
                    )
                except Exception as error:
                    self._last_disposal_result = {
                        "lease_id": lease.lease_id,
                        "status": "FAILED",
                        "error": str(error),
                        "automatic_retry": False,
                    }
                else:
                    self._last_disposal_result = {
                        "lease_id": lease.lease_id,
                        "status": "CLOSED"
                        if getattr(result, "released", False)
                        else "ALREADY_ABSENT",
                        "runtime_tab_id": getattr(result, "runtime_tab_id", None),
                        "automatic_retry": False,
                    }
                finally:
                    self._pending_disposal_timer = None

        timer = threading.Timer(delay_seconds, dispose_if_still_current)
        timer.daemon = True
        with self._authority_lock:
            self._pending_disposal_timer = timer
        timer.start()

    def _release_authority_from_write_event(
        self,
        lease: BrowserAuthorityLease,
        turn: TurnLifecycle,
        event: dict[str, Any],
    ) -> tuple[BrowserAuthorityLease, TurnLifecycle, dict[str, Any]]:
        """Historical release boundary for legacy/custom canonical clients."""

        with self._authority_lock:
            current = self._last_browser_authority_lease
            current_turn = self._last_turn_lifecycle
            if current is None or current.lease_id != lease.lease_id:
                return lease, turn, dict(event)
            if current.state is BrowserAuthorityLeaseState.ACTIVE:
                released_at = _monotonic_ms()
                current = current.release(
                    released_at_ms=released_at,
                    runtime_tab_id=_optional_int(event.get("runtime_tab_id")),
                )
                self._last_browser_authority_lease = current
            if (
                current_turn is not None
                and current_turn.lifecycle_id == turn.lifecycle_id
                and current_turn.state in {
                    TurnLifecycleState.PREPARED,
                    TurnLifecycleState.DISPATCHED,
                }
            ):
                current_turn = current_turn.write_completed(
                    at_ms=current.released_at_ms or _monotonic_ms()
                )
                self._last_turn_lifecycle = current_turn

            enriched = dict(event)
            enriched.update(
                {
                    "browser_authority_lease_id": current.lease_id,
                    "browser_authority_generation": current.generation,
                    "browser_authority_policy": current.policy.value,
                    "browser_authority_ttl_ms": current.ttl_ms,
                    "browser_authority_issued_at_ms": current.issued_at_ms,
                    "browser_authority_released_at_ms": current.released_at_ms,
                    "browser_authority_disposal_due_at_ms": current.disposal_due_at_ms,
                    "browser_authority_release_proven": current.authority_release_proven,
                    "browser_authority_disposal_action": (
                        "CLOSE" if current.disposal_allowed else "KEEP"
                    ),
                    "turn_lifecycle_id": current_turn.lifecycle_id
                    if current_turn is not None
                    else turn.lifecycle_id,
                    "turn_lifecycle_state": current_turn.state.value
                    if current_turn is not None
                    else turn.state.value,
                }
            )

        self._schedule_disposal(current)
        return current, current_turn or turn, enriched

    def _record_write_completion(
        self,
        lease: BrowserAuthorityLease,
        turn: TurnLifecycle,
        event: dict[str, Any],
    ) -> tuple[BrowserAuthorityLease, TurnLifecycle, dict[str, Any]]:
        """Record accepted write identity while retaining authority for readback."""

        with self._authority_lock:
            current = self._last_browser_authority_lease
            current_turn = self._last_turn_lifecycle
            if current is None or current.lease_id != lease.lease_id:
                return lease, turn, dict(event)

            if (
                current_turn is not None
                and current_turn.lifecycle_id == turn.lifecycle_id
                and current_turn.state in {
                    TurnLifecycleState.PREPARED,
                    TurnLifecycleState.DISPATCHED,
                }
            ):
                current_turn = current_turn.write_completed(at_ms=_monotonic_ms())
                self._last_turn_lifecycle = current_turn

            enriched = dict(event)
            enriched.update(
                {
                    "browser_authority_lease_id": current.lease_id,
                    "browser_authority_generation": current.generation,
                    "browser_authority_policy": current.policy.value,
                    "browser_authority_ttl_ms": current.ttl_ms,
                    "browser_authority_issued_at_ms": current.issued_at_ms,
                    "browser_authority_released_at_ms": None,
                    "browser_authority_disposal_due_at_ms": None,
                    "browser_authority_release_proven": False,
                    "browser_authority_disposal_action": "PENDING_CANONICAL_READBACK",
                    "turn_lifecycle_id": current_turn.lifecycle_id
                    if current_turn is not None
                    else turn.lifecycle_id,
                    "turn_lifecycle_state": current_turn.state.value
                    if current_turn is not None
                    else turn.state.value,
                }
            )
        return current, current_turn or turn, enriched

    def _release_authority_after_readback(
        self,
        lease: BrowserAuthorityLease,
        *,
        runtime_tab_id: int | None,
    ) -> BrowserAuthorityLease:
        """Release and schedule disposal only after canonical read terminality."""

        with self._authority_lock:
            current = self._last_browser_authority_lease
            if current is None or current.lease_id != lease.lease_id:
                return lease
            if current.state is BrowserAuthorityLeaseState.ACTIVE:
                current = current.release(
                    released_at_ms=_monotonic_ms(),
                    runtime_tab_id=runtime_tab_id,
                )
                self._last_browser_authority_lease = current
        self._schedule_disposal(current)
        return current

    def _finalize_turn(
        self,
        turn: TurnLifecycle,
    ) -> TurnLifecycle:
        with self._authority_lock:
            current = self._last_turn_lifecycle
            if current is None or current.lifecycle_id != turn.lifecycle_id:
                current = turn
            if current.state not in {
                TurnLifecycleState.FINALIZED,
                TurnLifecycleState.READBACK_INCOMPLETE,
                TurnLifecycleState.AMBIGUOUS,
            }:
                current = current.finalized(at_ms=_monotonic_ms())
            self._last_turn_lifecycle = current
            return current

    def _fail_turn(
        self,
        turn: TurnLifecycle,
        *,
        state: TurnLifecycleState,
    ) -> TurnLifecycle:
        with self._authority_lock:
            current = self._last_turn_lifecycle
            if current is None or current.lifecycle_id != turn.lifecycle_id:
                current = turn
            if state is TurnLifecycleState.READBACK_INCOMPLETE:
                current = current.readback_incomplete(at_ms=_monotonic_ms())
            elif state is TurnLifecycleState.AMBIGUOUS:
                current = current.ambiguous(at_ms=_monotonic_ms())
            else:
                raise ValueError(f"unsupported terminal failure state: {state.value}")
            self._last_turn_lifecycle = current
            return current

    def send_text(
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
    ) -> ChatResponse:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        resolution = self._resolve_authority_policy(
            browser_authority_policy=browser_authority_policy,
            browser_authority_ttl_ms=browser_authority_ttl_ms,
        )
        set_lease = getattr(self.provider, "set_browser_authority_lease", None)
        complete_readback = getattr(self.client, "complete_canonical_readback", None)
        clear_lease = getattr(self.provider, "clear_browser_authority_lease", None)
        browser_context_readback = callable(complete_readback)
        if resolution.policy is not BrowserAuthorityPolicy.PERSISTENT and (
            not callable(getattr(self.provider, "release_runtime_tab", None))
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

        preflight = self.health(conversation)
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
                commit_status = _canonical_status_value(self.client, conversation)
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

        fresh_authority = self._fresh_browser_authority_status()
        lease, turn = self._issue_authority(
            resolution=resolution,
            status=fresh_authority,
        )

        lease_ref = lease
        turn_ref = turn
        write_event_observed = False
        delegated_conversation_id = _conversation_id(conversation)
        runtime_tab_id: int | None = None
        readback_ack_attempted = False
        readback_acknowledged = False

        def acknowledge_readback() -> bool:
            nonlocal readback_ack_attempted, readback_acknowledged
            if not browser_context_readback:
                return True
            if readback_ack_attempted:
                return readback_acknowledged
            readback_ack_attempted = True
            readback_acknowledged = complete_readback() is True
            return readback_acknowledged

        def runtime_event(event: dict[str, Any]) -> None:
            nonlocal lease_ref, turn_ref, write_event_observed, delegated_conversation_id, runtime_tab_id
            forwarded = event
            if isinstance(event, dict) and event.get("type") == "browser_native_write_completed":
                write_event_observed = True
                delegated_conversation_id = _optional_text(event.get("conversation_id")) or delegated_conversation_id
                runtime_tab_id = _optional_int(event.get("runtime_tab_id"))
                if browser_context_readback:
                    lease_ref, turn_ref, forwarded = self._record_write_completion(
                        lease_ref,
                        turn_ref,
                        event,
                    )
                else:
                    lease_ref, turn_ref, forwarded = self._release_authority_from_write_event(
                        lease_ref,
                        turn_ref,
                        event,
                    )
            elif isinstance(event, dict) and event.get("type") == "browser_native_readback_completed":
                if browser_context_readback and write_event_observed:
                    if not acknowledge_readback():
                        raise RequestError(
                            "BROWSER_NATIVE_READBACK_ACKNOWLEDGEMENT_FAILED",
                            request_stage="browser_native_canonical_read",
                        )
                    lease_ref = self._release_authority_after_readback(
                        lease_ref,
                        runtime_tab_id=runtime_tab_id,
                    )
                turn_ref = self._finalize_turn(turn_ref)
                forwarded = dict(event)
                forwarded.update(
                    {
                        "browser_authority_lease_id": lease_ref.lease_id,
                        "browser_authority_released_at_ms": lease_ref.released_at_ms,
                        "browser_authority_disposal_due_at_ms": lease_ref.disposal_due_at_ms,
                        "browser_authority_release_proven": lease_ref.authority_release_proven,
                        "browser_authority_disposal_action": (
                            "CLOSE" if lease_ref.disposal_allowed else "KEEP"
                        ),
                        "turn_lifecycle_id": turn_ref.lifecycle_id,
                        "turn_lifecycle_state": turn_ref.state.value,
                    }
                )
            if on_event is not None:
                try:
                    on_event(forwarded)
                except Exception:
                    pass

        if callable(set_lease):
            set_lease(lease.lease_id)
        try:
            response = send_browser_native(
                self.client,
                text,
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                on_token=on_token,
                on_event=runtime_event,
            )
            turn_ref = self._finalize_turn(turn_ref)
            if lease_ref.state is BrowserAuthorityLeaseState.ACTIVE:
                lease_ref = self._mark_release_unknown(lease_ref)
            return response
        except ConversationTimeoutError as error:
            turn_ref = self._fail_turn(
                turn_ref,
                state=TurnLifecycleState.READBACK_INCOMPLETE,
            )
            if browser_context_readback and write_event_observed and acknowledge_readback():
                lease_ref = self._release_authority_after_readback(
                    lease_ref,
                    runtime_tab_id=runtime_tab_id,
                )
            elif lease_ref.state is BrowserAuthorityLeaseState.ACTIVE:
                lease_ref = self._mark_release_unknown(lease_ref)
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=WRITE_ACCEPTED_READBACK_INCOMPLETE,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage="browser_owned_write_readback",
                conversation_id=delegated_conversation_id,
                reason_code="CANONICAL_READ_TIMEOUT",
                browser_authority_lease=lease_ref,
                turn_lifecycle=turn_ref,
            ) from error
        except WebChatAdapterError as error:
            readback_failure = write_event_observed
            turn_ref = self._fail_turn(
                turn_ref,
                state=(
                    TurnLifecycleState.READBACK_INCOMPLETE
                    if readback_failure
                    else TurnLifecycleState.AMBIGUOUS
                ),
            )
            if browser_context_readback and readback_failure and acknowledge_readback():
                lease_ref = self._release_authority_after_readback(
                    lease_ref,
                    runtime_tab_id=runtime_tab_id,
                )
            elif lease_ref.state is BrowserAuthorityLeaseState.ACTIVE:
                lease_ref = self._mark_release_unknown(lease_ref)
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=(
                    WRITE_ACCEPTED_READBACK_INCOMPLETE
                    if readback_failure
                    else WRITE_OUTCOME_UNKNOWN
                ),
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage=(
                    "browser_owned_write_readback"
                    if readback_failure
                    else "browser_owned_write"
                ),
                conversation_id=(
                    getattr(error, "conversation_id", None)
                    or delegated_conversation_id
                ),
                reason_code=getattr(error, "reason_code", None),
                status_code=getattr(error, "status_code", None),
                content_type=getattr(error, "content_type", None),
                browser_authority_lease=lease_ref,
                turn_lifecycle=turn_ref,
            ) from error
        finally:
            try:
                if browser_context_readback:
                    acknowledge_readback()
            finally:
                if callable(clear_lease):
                    clear_lease()

    def send_text_observed(
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
    ) -> BrowserOwnedWriteExecution:
        write_event: dict[str, Any] | None = None

        def capture_event(event: dict[str, Any]) -> None:
            nonlocal write_event
            if isinstance(event, dict) and event.get("type") == "browser_native_write_completed":
                write_event = dict(event)
            elif (
                isinstance(event, dict)
                and event.get("type") == "browser_native_readback_completed"
                and write_event is not None
            ):
                for key in (
                    "browser_authority_released_at_ms",
                    "browser_authority_disposal_due_at_ms",
                    "browser_authority_release_proven",
                    "browser_authority_disposal_action",
                ):
                    if key in event:
                        write_event[key] = event[key]
            if on_event is not None:
                on_event(event)

        response = self.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=capture_event,
            browser_authority_policy=browser_authority_policy,
            browser_authority_ttl_ms=browser_authority_ttl_ms,
        )
        return BrowserOwnedWriteExecution(
            response=response,
            observation=BrowserOwnedWriteObservation.from_event(write_event),
        )

    def lifecycle_snapshot(self) -> dict[str, Any]:
        with self._authority_lock:
            return {
                "browser_authority_lease": (
                    self._last_browser_authority_lease.to_dict()
                    if self._last_browser_authority_lease is not None
                    else None
                ),
                "turn_lifecycle": (
                    self._last_turn_lifecycle.to_dict()
                    if self._last_turn_lifecycle is not None
                    else None
                ),
                "pending_disposal": self._pending_disposal_timer is not None,
                "last_disposal_result": (
                    dict(self._last_disposal_result)
                    if isinstance(self._last_disposal_result, dict)
                    else None
                ),
            }

    def governance(self) -> dict[str, Any]:
        return {
            "read_plane": self._read_plane,
            "session_plane": SESSION_PLANE,
            "write_plane": WRITE_PLANE,
            "browser_launch_owned_by_runtime": False,
            "browser_process_launch_owned_by_runtime": False,
            "runtime_tab_creation_owned_by_extension": True,
            "runtime_tab_creation_on_demand": True,
            "runtime_tab_foreground_activation_requested": False,
            "runtime_tab_required_before_turn": False,
            "direct_private_product_write": False,
            "challenge_solver_expansion": False,
            "browser_protection_emulation": False,
            "credential_extraction": False,
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "ambiguous_write_requires_reconciliation": True,
            "browser_authority_lease_model": "BrowserAuthorityLease",
            "turn_lifecycle_model": "TurnLifecycle",
            "browser_authority_lease_distinct_from_turn_lifecycle": True,
            "browser_authority_release_event": (
                "browser_native_readback_completed"
                if self._browser_context_readback
                else "browser_native_write_completed"
            ),
            "turn_finality_event": "browser_native_readback_completed",
            "browser_authority_default_policy": (
                TRANSPORT_DEFAULT_BROWSER_AUTHORITY_POLICY.value
            ),
            "browser_authority_supported_policies": [
                policy.value for policy in BrowserAuthorityPolicy
            ],
            "browser_authority_policy_precedence": [
                "PER_TURN",
                "RUNTIME_DEFAULT",
                "TRANSPORT_DEFAULT",
            ],
            "browser_authority_ttl_starts_after_release": True,
            "browser_authority_disposal_action_v1": "CLOSE",
            "browser_authority_discard_supported": False,
            "browser_authority_disposal_requires_release_proof": True,
            "browser_authority_disposal_automatic_retry": False,
            "browser_authority_fresh_commit_recheck": True,
            "browser_authority_release_fenced_by_lease_id": True,
            "browser_authority_release_fenced_by_runtime_tab_id": True,
            "turn_scoped_zero_ttl_allowed": True,
            "persistent_policy_schedules_disposal": False,
            "nonpersistent_policies_opt_in": True,
        }
