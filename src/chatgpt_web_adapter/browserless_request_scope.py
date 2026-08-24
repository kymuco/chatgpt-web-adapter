from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import monotonic
from typing import Any, Callable, Iterator, Mapping

from .exceptions import RequestError


_BROWSERLESS_REQUEST_SCOPE_OWNER: ContextVar[object | None] = ContextVar(
    "browserless_request_scope_owner",
    default=None,
)


def _browserless_timeout_error(*, request_stage: str) -> RequestError:
    return RequestError(
        "browserless total invocation deadline expired",
        request_stage=request_stage,
    )


def _remaining(deadline: float, *, request_stage: str) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise _browserless_timeout_error(request_stage=request_stage)
    return remaining


def _bound_curl_command(command: Any, *, remaining: float) -> list[str]:
    if not isinstance(command, list):
        raise RequestError(
            "browserless direct-request curl command is not a list",
            request_stage="browserless_request_scope",
        )
    patched = list(command)
    try:
        max_time_index = patched.index("--max-time")
    except ValueError as error:
        raise RequestError(
            "browserless direct-request curl command is missing --max-time",
            request_stage="browserless_request_scope",
        ) from error
    if max_time_index + 1 >= len(patched):
        raise RequestError(
            "browserless direct-request curl command has no --max-time value",
            request_stage="browserless_request_scope",
        )
    patched[max_time_index + 1] = str(max(0.001, remaining))
    return patched


def _restore_instance_callable(
    client: Any,
    *,
    name: str,
    previous: Any,
    marker: object,
    installed: Any,
) -> None:
    instance_dict = getattr(client, "__dict__", None)
    if not isinstance(instance_dict, dict):
        return
    if instance_dict.get(name, marker) is not installed:
        # Preserve a concurrent explicit caller update rather than overwriting it.
        return
    if previous is marker:
        try:
            delattr(client, name)
        except AttributeError:
            pass
    else:
        setattr(client, name, previous)


@contextmanager
def _bind_browserless_request_scope(
    client: Any,
    *,
    deadline: float,
) -> Iterator[None]:
    """Bind browserless header hygiene and total deadline to one execution context.

    The instance dispatchers remain visible while the scope is active, but only the
    owner ContextVar receives browserless behavior. Ordinary concurrent callers on
    the shared canonical client delegate to the exact methods that were present
    before this scope.
    """

    instance_dict = getattr(client, "__dict__", None)
    if not isinstance(instance_dict, dict):
        from .browserless_request_transport import BrowserlessProtocolDriftError

        raise BrowserlessProtocolDriftError(
            "direct-request client does not expose instance state for request scope",
            request_stage="browserless_request_scope",
        )

    delegate_headers = getattr(client, "_build_headers", None)
    delegate_curl = getattr(client, "_build_curl_command", None)
    if not callable(delegate_headers):
        from .browserless_request_transport import BrowserlessProtocolDriftError

        raise BrowserlessProtocolDriftError(
            "direct-request client is missing header builder for request scope",
            request_stage="browserless_request_scope",
        )

    marker = object()
    previous_headers = instance_dict.get("_build_headers", marker)
    previous_curl = instance_dict.get("_build_curl_command", marker)
    owner = object()

    def owns_scope() -> bool:
        return _BROWSERLESS_REQUEST_SCOPE_OWNER.get() is owner

    def build_headers(
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        headers = delegate_headers(extra)
        if not owns_scope():
            return headers
        from .browserless_request_transport import _strip_ephemeral_write_headers

        return _strip_ephemeral_write_headers(headers)

    def build_curl_command(*args: Any, **kwargs: Any) -> Any:
        if not callable(delegate_curl):
            raise RequestError(
                "browserless direct-request client is missing curl-command builder",
                request_stage="browserless_request_scope",
            )
        command = delegate_curl(*args, **kwargs)
        if not owns_scope():
            return command
        remaining = _remaining(
            deadline,
            request_stage="browserless_request_deadline",
        )
        return _bound_curl_command(command, remaining=remaining)

    client._build_headers = build_headers
    if callable(delegate_curl):
        client._build_curl_command = build_curl_command
    owner_token = _BROWSERLESS_REQUEST_SCOPE_OWNER.set(owner)
    try:
        yield
    finally:
        _BROWSERLESS_REQUEST_SCOPE_OWNER.reset(owner_token)
        _restore_instance_callable(
            client,
            name="_build_headers",
            previous=previous_headers,
            marker=marker,
            installed=build_headers,
        )
        if callable(delegate_curl):
            _restore_instance_callable(
                client,
                name="_build_curl_command",
                previous=previous_curl,
                marker=marker,
                installed=build_curl_command,
            )


def gate_browserless_request_execute(
    original_execute: Callable[..., Any],
) -> Callable[..., Any]:
    """Give the whole browserless invocation one scoped deadline and header policy."""

    @wraps(original_execute)
    def execute(
        self: Any,
        text: str,
        *,
        conversation: Any,
        timeout: float,
        poll_interval: float,
        on_token: Any,
        on_event: Any,
    ) -> Any:
        # Preserve the original validation order and side-effect-free failures.
        if (
            not isinstance(text, str)
            or not text.strip()
            or timeout <= 0
            or poll_interval <= 0
        ):
            return original_execute(
                self,
                text,
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                on_token=on_token,
                on_event=on_event,
            )

        deadline = monotonic() + float(timeout)
        lock = getattr(self, "_write_lock", None)
        acquire = getattr(lock, "acquire", None)
        release = getattr(lock, "release", None)
        if not callable(acquire) or not callable(release):
            # Compatibility with focused synthetic locks; real browserless
            # transports always receive the guarded per-client RLock.
            return original_execute(
                self,
                text,
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                on_token=on_token,
                on_event=on_event,
            )

        remaining = deadline - monotonic()
        if remaining <= 0:
            acquired = False
        else:
            try:
                acquired = bool(acquire(timeout=remaining))
            except OverflowError:
                acquired = bool(acquire())
        if not acquired:
            from .browserless_request_transport import BrowserlessRequestTransportError

            raise BrowserlessRequestTransportError(
                "browserless request deadline expired while waiting for shared-client write authority",
                request_stage="browserless_write_queue",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
            )

        try:
            remaining = deadline - monotonic()
            if remaining <= 0:
                from .browserless_request_transport import BrowserlessRequestTransportError

                raise BrowserlessRequestTransportError(
                    "browserless request deadline expired before request execution",
                    request_stage="browserless_write_queue",
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                )

            with _bind_browserless_request_scope(
                self.client,
                deadline=deadline,
            ):
                # The original execution re-enters the same RLock. Passing only
                # the remaining budget makes its internal deadline coincide with
                # this outer invocation deadline, including time spent queued.
                remaining = _remaining(
                    deadline,
                    request_stage="browserless_request_deadline",
                )
                return original_execute(
                    self,
                    text,
                    conversation=conversation,
                    timeout=remaining,
                    poll_interval=poll_interval,
                    on_token=on_token,
                    on_event=on_event,
                )
        finally:
            release()

    return execute
