from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import time as _stdlib_time
from typing import Any, Callable

from .browserless_request_scope import _BROWSERLESS_REQUEST_SCOPE_OWNER


_POLL_SLEEP_DEADLINE: ContextVar[float | None] = ContextVar(
    "browserless_poll_sleep_deadline",
    default=None,
)


class _DeadlineAwareClientTime:
    """Proxy the client module's time API while clamping scoped poll sleeps.

    The proxy is permanently installed only in ``chatgpt_web_adapter.client``.
    Outside a browserless poll context every attribute and every sleep delegates
    unchanged to the original time module. This avoids mutating global
    ``time.sleep`` and keeps ordinary/public callers outside browserless policy.
    """

    _cwa_browserless_poll_time_proxy = True

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def sleep(self, seconds: float) -> None:
        deadline = _POLL_SLEEP_DEADLINE.get()
        if deadline is None:
            self._delegate.sleep(seconds)
            return

        remaining = deadline - self._delegate.monotonic()
        if remaining <= 0:
            return
        requested = max(0.0, float(seconds))
        self._delegate.sleep(min(requested, remaining))


def install_browserless_poll_deadline_guard(
    client_module: Any,
    client_class: type[Any],
) -> None:
    """Make browserless recovery polling honor its already-bounded timeout.

    PR9.1 already passes the remaining total invocation budget into
    ``_poll_conversation_after_prepare(timeout=...)``. The legacy poller enforces
    a 0.5 second minimum sleep, which can overrun a shorter remaining budget.
    This guard leaves ordinary polling untouched and only clamps sleeps while the
    call executes inside the browserless request ContextVar.
    """

    current_time = getattr(client_module, "time", None)
    if current_time is None:
        raise RuntimeError("client module does not expose time")
    if not getattr(current_time, "_cwa_browserless_poll_time_proxy", False):
        client_module.time = _DeadlineAwareClientTime(current_time)

    original = getattr(client_class, "_poll_conversation_after_prepare", None)
    if not callable(original):
        raise RuntimeError("ChatGPTWebClient is missing conversation recovery polling")
    if getattr(original, "_cwa_browserless_poll_deadline_guard", False):
        return

    @wraps(original)
    def poll(
        self: Any,
        conversation_id: str,
        *,
        previous_message_id: str | None,
        timeout: float,
        interval: float,
        on_token: Any = None,
        on_event: Any = None,
        reason: str = "approval_poll",
        allow_global_fallback: bool = True,
    ) -> Any:
        if _BROWSERLESS_REQUEST_SCOPE_OWNER.get() is None:
            return original(
                self,
                conversation_id,
                previous_message_id=previous_message_id,
                timeout=timeout,
                interval=interval,
                on_token=on_token,
                on_event=on_event,
                reason=reason,
                allow_global_fallback=allow_global_fallback,
            )

        deadline = _stdlib_time.monotonic() + max(0.0, float(timeout))
        token = _POLL_SLEEP_DEADLINE.set(deadline)
        try:
            return original(
                self,
                conversation_id,
                previous_message_id=previous_message_id,
                timeout=timeout,
                interval=interval,
                on_token=on_token,
                on_event=on_event,
                reason=reason,
                allow_global_fallback=allow_global_fallback,
            )
        finally:
            _POLL_SLEEP_DEADLINE.reset(token)

    poll._cwa_browserless_poll_deadline_guard = True  # type: ignore[attr-defined]
    client_class._poll_conversation_after_prepare = poll


def _normalized_message_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def gate_browserless_canonical_finalize(
    original: Callable[..., Any],
) -> Callable[..., Any]:
    """Require completion and readback to identify the submitted assistant."""

    @wraps(original)
    def canonical_finalize(
        self: Any,
        response: Any,
        *,
        previous_message_id: str | None,
        timeout: float,
        poll_interval: float,
    ) -> Any:
        conversation = getattr(response, "conversation", None)
        submitted_message_id = _normalized_message_id(
            getattr(conversation, "message_id", None)
        )
        if submitted_message_id is None:
            from .browserless_request_transport import BrowserlessRequestTransportError

            raise BrowserlessRequestTransportError(
                "submitted browserless assistant identity is missing; canonical "
                "finality cannot be correlated to this turn",
                request_stage="canonical_reconciliation",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )

        result = original(
            self,
            response,
            previous_message_id=previous_message_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        status, canonical_assistant, _text = result
        status_message_id = _normalized_message_id(
            getattr(status, "message_id", None)
        )
        canonical_message_id = _normalized_message_id(
            getattr(canonical_assistant, "message_id", None)
        )

        if status_message_id != submitted_message_id:
            from .browserless_request_transport import BrowserlessRequestTransportError

            raise BrowserlessRequestTransportError(
                "canonical completion status identity does not match the submitted "
                "browserless turn",
                request_stage="canonical_reconciliation",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )

        if canonical_message_id != submitted_message_id:
            from .browserless_request_transport import BrowserlessRequestTransportError

            raise BrowserlessRequestTransportError(
                "canonical readback assistant identity does not match the submitted "
                "browserless turn",
                request_stage="canonical_reconciliation",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        return result

    return canonical_finalize
