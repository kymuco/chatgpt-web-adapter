from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

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

READ_PLANE = "BROWSERLESS_CANONICAL_HTTP"
SESSION_PLANE = "BROWSERLESS_SESSION_HTTP"
WRITE_PLANE = "BROWSER_NATIVE_PAGE_OWNED_WRITE"


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
    read_plane: str = READ_PLANE
    session_plane: str = SESSION_PLANE
    write_plane: str = WRITE_PLANE
    automatic_write_retry: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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
    ) -> None:
        self.failure_kind = failure_kind
        self.automatic_retry_allowed = bool(automatic_retry_allowed)
        self.manual_retry_safe_after_repair = bool(manual_retry_safe_after_repair)
        self.write_may_have_been_submitted = bool(write_may_have_been_submitted)
        self.reconciliation_required = bool(reconciliation_required)
        self.cause = cause
        super().__init__(message, request_stage=request_stage)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "failure_kind": self.failure_kind,
                "automatic_retry_allowed": self.automatic_retry_allowed,
                "manual_retry_safe_after_repair": self.manual_retry_safe_after_repair,
                "write_may_have_been_submitted": self.write_may_have_been_submitted,
                "reconciliation_required": self.reconciliation_required,
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

    Reads and session renewal remain in the existing browserless SDK plane. The
    browser-native bridge is used only for one page-owned ordinary ChatGPT turn,
    followed by canonical SDK readback. This facade never launches a browser,
    never calls a private product write endpoint, and never retries a delegated
    write automatically.
    """

    def __init__(
        self,
        client: Any,
        *,
        provider: BrowserNativeTurnProvider | None = None,
    ) -> None:
        self.client = client
        self.provider = provider or BrowserNativeTurnProvider()
        set_browser_native_turn_provider(self.client, self.provider)

    def health(
        self,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
    ) -> BrowserOwnedWriteRuntimeHealth:
        conversation_id = _conversation_id(conversation)
        bridge: BrowserNativeBridgeStatus = self.provider.status()

        if not bridge.available:
            return BrowserOwnedWriteRuntimeHealth(
                ready=False,
                reason=BRIDGE_UNAVAILABLE,
                bridge_available=False,
                extension_connected=False,
                runtime_tab_id=bridge.runtime_tab_id,
                runtime_tab_preexisting=bridge.runtime_tab_id is not None,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=False,
            )
        if not bridge.extension_connected:
            return BrowserOwnedWriteRuntimeHealth(
                ready=False,
                reason=EXTENSION_DISCONNECTED,
                bridge_available=True,
                extension_connected=False,
                runtime_tab_id=bridge.runtime_tab_id,
                runtime_tab_preexisting=bridge.runtime_tab_id is not None,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=False,
            )

        # A runtime tab is deliberately NOT required here. PR8.1.1 proved that
        # the connected extension can create/recover its dedicated background
        # ChatGPT tab on demand without stealing foreground focus.
        if conversation is None:
            return BrowserOwnedWriteRuntimeHealth(
                ready=True,
                reason=READY,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                runtime_tab_preexisting=bridge.runtime_tab_id is not None,
                conversation_id=None,
                canonical_status=None,
                canonical_read_checked=False,
            )

        try:
            canonical_status = _canonical_status_value(self.client, conversation)
        except Exception:
            return BrowserOwnedWriteRuntimeHealth(
                ready=False,
                reason=CANONICAL_READ_UNAVAILABLE,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                runtime_tab_preexisting=bridge.runtime_tab_id is not None,
                conversation_id=conversation_id,
                canonical_status=None,
                canonical_read_checked=True,
            )

        if canonical_status != "completed":
            return BrowserOwnedWriteRuntimeHealth(
                ready=False,
                reason=CONVERSATION_NOT_COMPLETED,
                bridge_available=True,
                extension_connected=True,
                runtime_tab_id=bridge.runtime_tab_id,
                runtime_tab_preexisting=bridge.runtime_tab_id is not None,
                conversation_id=conversation_id,
                canonical_status=canonical_status,
                canonical_read_checked=True,
            )

        return BrowserOwnedWriteRuntimeHealth(
            ready=True,
            reason=READY,
            bridge_available=True,
            extension_connected=True,
            runtime_tab_id=bridge.runtime_tab_id,
            runtime_tab_preexisting=bridge.runtime_tab_id is not None,
            conversation_id=conversation_id,
            canonical_status=canonical_status,
            canonical_read_checked=True,
        )

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

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

        # Commit-point recheck for continuation turns. Health is advisory and a
        # conversation can transition between the first read and delegation.
        # A second browserless canonical read closes the common completed→busy
        # race before the browser-owned write is allowed to begin.
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

        try:
            return send_browser_native(
                self.client,
                text,
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                on_token=on_token,
                on_event=on_event,
            )
        except ConversationTimeoutError as error:
            # send_browser_native raises this only after the browser-owned write
            # has returned success and canonical assistant readback failed to
            # reach a final message. A second send would risk a duplicate turn.
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=WRITE_ACCEPTED_READBACK_INCOMPLETE,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage="browser_owned_write_readback",
            ) from error
        except WebChatAdapterError as error:
            # Once provider delegation begins, extension/browser races can make
            # the protected-write outcome ambiguous. Never infer retry safety.
            raise BrowserOwnedWriteRuntimeError(
                str(error),
                failure_kind=WRITE_OUTCOME_UNKNOWN,
                automatic_retry_allowed=False,
                manual_retry_safe_after_repair=False,
                write_may_have_been_submitted=True,
                reconciliation_required=True,
                cause=error,
                request_stage="browser_owned_write",
            ) from error

    def send_text_observed(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> BrowserOwnedWriteExecution:
        write_event: dict[str, Any] | None = None

        def capture_event(event: dict[str, Any]) -> None:
            nonlocal write_event
            if isinstance(event, dict) and event.get("type") == "browser_native_write_completed":
                write_event = dict(event)
            if on_event is not None:
                on_event(event)

        response = self.send_text(
            text,
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            on_token=on_token,
            on_event=capture_event,
        )
        return BrowserOwnedWriteExecution(
            response=response,
            observation=BrowserOwnedWriteObservation.from_event(write_event),
        )

    def governance(self) -> dict[str, Any]:
        return {
            "read_plane": READ_PLANE,
            "session_plane": SESSION_PLANE,
            "write_plane": WRITE_PLANE,
            # Compatibility alias retained from PR8.2.4. The split fields below
            # are the authoritative ownership semantics from PR8.2.4a.
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
        }
