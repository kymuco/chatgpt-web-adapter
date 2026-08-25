from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import threading
from typing import Any, Callable, Iterator

from .exceptions import RequestError
from .types import ChatConversation


_FENCE_MARKER = "_cwa_browserless_shared_write_fence_lock"
_FENCE_ORIGINAL = "_cwa_browserless_shared_write_fence_original"
_INSTANCE_LOCK_ATTR = "_cwa_browserless_shared_write_fence_lock_state"
_CLASS_SETATTR_MARKER = "_cwa_browserless_shared_write_fence_setattr_guard"
_CLASS_DELATTR_MARKER = "_cwa_browserless_shared_write_fence_delattr_guard"
_BROWSERLESS_EXECUTE_MARKER = "_cwa_browserless_shared_write_fence_execute_guard"
_CLASS_GUARD_LOCK = threading.Lock()
_MUTATION_AUTHORITY_STATE = threading.local()

_ATOMIC_MUTATION_SURFACES = (
    "send",
    "_send_existing_text_prepared",
    "approve_pending_action",
    "send_payload",
    "send_to_conversation",
    "send_browser_native",
)
_CONVERSATION_REFRESH_POSITION = {
    "send": 1,
    "_send_existing_text_prepared": 1,
    "approve_pending_action": 0,
    "send_browser_native": 1,
}
_ALLOWED_SAME_CLIENT_DELEGATIONS = frozenset(
    {
        ("send_to_conversation", "send"),
        ("send_to_conversation", "_send_existing_text_prepared"),
    }
)


def _valid_lock(lock: Any) -> bool:
    return callable(getattr(lock, "acquire", None)) and callable(
        getattr(lock, "release", None)
    )


def _instance_fence_lock(client: Any) -> Any:
    instance_dict = getattr(client, "__dict__", None)
    if not isinstance(instance_dict, dict):
        return None
    return instance_dict.get(_INSTANCE_LOCK_ATTR)


def _authority_stack() -> list[tuple[Any, str]]:
    stack = getattr(_MUTATION_AUTHORITY_STATE, "stack", None)
    if stack is None:
        stack = []
        _MUTATION_AUTHORITY_STATE.stack = stack
    return stack


def _authority_conflict(client: Any, name: str) -> tuple[Any, str] | None:
    stack = _authority_stack()
    if not stack:
        return None
    active_client, active_name = stack[-1]
    if (
        active_client is client
        and (active_name, name) in _ALLOWED_SAME_CLIENT_DELEGATIONS
    ):
        return None
    return active_client, active_name


def _nested_mutation_error(
    *,
    active_client: Any,
    active_name: str,
    client: Any,
    name: str,
) -> RequestError:
    relation = "same-client" if active_client is client else "cross-client"
    return RequestError(
        "shared-client mutation fence rejected "
        f"{relation} nested mutation {name} while {active_name} owns mutation authority; "
        "defer the nested mutation until the outer mutation returns",
        request_stage="shared_client_write_fence",
    )


@contextmanager
def _mutation_authority(client: Any, name: str) -> Iterator[None]:
    conflict = _authority_conflict(client, name)
    if conflict is not None:
        active_client, active_name = conflict
        raise _nested_mutation_error(
            active_client=active_client,
            active_name=active_name,
            client=client,
            name=name,
        )

    stack = _authority_stack()
    stack.append((client, name))
    try:
        yield
    finally:
        stack.pop()
        if not stack:
            try:
                delattr(_MUTATION_AUTHORITY_STATE, "stack")
            except AttributeError:
                pass


def _normalize_attached_conversation(
    attached: Any,
) -> ChatConversation | dict[str, Any] | None:
    if isinstance(attached, ChatConversation):
        return attached

    nested = getattr(attached, "conversation", None)
    if isinstance(nested, ChatConversation):
        return nested
    if isinstance(nested, dict):
        return dict(nested)

    if isinstance(attached, dict):
        nested = attached.get("conversation")
        if isinstance(nested, ChatConversation):
            return nested
        if isinstance(nested, dict):
            return dict(nested)
    return None


def _refresh_conversation(client: Any, conversation: Any) -> Any:
    if conversation is None:
        return None
    attach = getattr(client, "attach_conversation", None)
    if not callable(attach):
        raise RequestError(
            "shared-client mutation fence cannot refresh continuation without attach_conversation()",
            request_stage="shared_client_write_fence",
        )
    attached = attach(conversation)
    refreshed = _normalize_attached_conversation(attached)
    if refreshed is None:
        raise RequestError(
            "shared-client mutation fence canonical attach returned no conversation",
            request_stage="shared_client_write_fence",
        )
    return refreshed


def _refresh_conversation_argument(
    client: Any,
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    if "conversation" in kwargs:
        conversation = kwargs.get("conversation")
        if conversation is None:
            return args, kwargs
        patched_kwargs = dict(kwargs)
        patched_kwargs["conversation"] = _refresh_conversation(client, conversation)
        return args, patched_kwargs

    position = _CONVERSATION_REFRESH_POSITION.get(name)
    if position is None or len(args) <= position or args[position] is None:
        return args, kwargs
    patched_args = list(args)
    patched_args[position] = _refresh_conversation(client, patched_args[position])
    return tuple(patched_args), kwargs


def _conversation_parent_id(conversation: Any) -> str | None:
    if isinstance(conversation, dict):
        value = conversation.get("parent_message_id") or conversation.get("message_id")
    else:
        value = getattr(conversation, "parent_message_id", None) or getattr(
            conversation,
            "message_id",
            None,
        )
    return value.strip() if isinstance(value, str) and value.strip() else None


def _validate_raw_payload_parent(client: Any, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    conversation_id = payload.get("conversation_id")
    parent_message_id = payload.get("parent_message_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return
    if not isinstance(parent_message_id, str) or not parent_message_id.strip():
        return

    refreshed = _refresh_conversation(client, conversation_id.strip())
    current_parent = _conversation_parent_id(refreshed)
    if current_parent is None:
        raise RequestError(
            "shared-client mutation fence could not resolve the current raw-payload parent",
            request_stage="shared_client_write_fence",
        )
    if current_parent != parent_message_id.strip():
        raise RequestError(
            "shared-client mutation fence rejected a stale raw-payload parent; "
            "refresh the payload explicitly before retrying",
            request_stage="shared_client_write_fence",
        )


def _refresh_mutation_call(
    client: Any,
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    if name in _CONVERSATION_REFRESH_POSITION:
        return _refresh_conversation_argument(client, name, args, kwargs)

    # send_to_conversation() performs canonical attach inside its own fenced call.
    # Its known internal send/prepared-send delegation is the only nested mutation
    # authority permitted by this module.
    if name == "send_to_conversation":
        return args, kwargs

    # Raw payload is deliberately not rewritten: that would silently change the
    # caller's explicit payload semantics. Instead, reject a stale existing-chat
    # parent after queueing so it cannot create an accidental sibling branch.
    if name == "send_payload":
        payload = kwargs.get("payload") if "payload" in kwargs else (args[0] if args else None)
        _validate_raw_payload_parent(client, payload)
    return args, kwargs


def _fence_callable(client: Any, name: str, current: Callable[..., Any], lock: Any) -> Any:
    installed_lock = getattr(current, _FENCE_MARKER, None)
    if installed_lock is lock:
        return current
    if installed_lock is not None:
        raise TypeError(
            f"browserless shared-client mutation fence for {name} uses a different lock"
        )

    @wraps(current)
    def fenced(*args: Any, **kwargs: Any) -> Any:
        # Enter mutation authority before attempting lock acquisition. This makes
        # callback reentrancy fail closed and prevents opposite-order cross-client
        # lock acquisition from forming an AB/BA deadlock.
        with _mutation_authority(client, name):
            with lock:
                call_args, call_kwargs = _refresh_mutation_call(
                    client,
                    name,
                    args,
                    kwargs,
                )
                return current(*call_args, **call_kwargs)

    setattr(fenced, _FENCE_MARKER, lock)
    setattr(fenced, _FENCE_ORIGINAL, current)
    return fenced


def unfenced_mutation_callable(value: Any) -> Any:
    """Return the callable underneath this module's instance mutation wrappers."""

    current = value
    seen: set[int] = set()
    while callable(current) and getattr(current, _FENCE_MARKER, None) is not None:
        identity = id(current)
        if identity in seen:
            break
        seen.add(identity)
        original = getattr(current, _FENCE_ORIGINAL, None)
        if not callable(original):
            break
        current = original
    return current


def _install_assignment_guards(client: Any) -> None:
    cls = type(client)
    with _CLASS_GUARD_LOCK:
        current_setattr = getattr(cls, "__setattr__", None)
        if not getattr(current_setattr, _CLASS_SETATTR_MARKER, False):
            original_setattr = current_setattr
            if not callable(original_setattr):
                raise TypeError(
                    "browserless shared-client mutation fence requires class __setattr__ support"
                )

            @wraps(original_setattr)
            def guarded_setattr(instance: Any, name: str, value: Any) -> Any:
                lock = _instance_fence_lock(instance)
                if name in _ATOMIC_MUTATION_SURFACES and _valid_lock(lock):
                    if not callable(value):
                        raise TypeError(
                            f"cannot replace fenced mutation entrypoint {name} with a non-callable value"
                        )
                    value = _fence_callable(instance, name, value, lock)
                return original_setattr(instance, name, value)

            setattr(guarded_setattr, _CLASS_SETATTR_MARKER, True)
            try:
                setattr(cls, "__setattr__", guarded_setattr)
            except (AttributeError, TypeError) as error:
                raise TypeError(
                    "browserless request transport cannot guard mutation-method replacement "
                    f"for compatible client class {cls.__name__}"
                ) from error

        current_delattr = getattr(cls, "__delattr__", None)
        if not getattr(current_delattr, _CLASS_DELATTR_MARKER, False):
            original_delattr = current_delattr
            if not callable(original_delattr):
                raise TypeError(
                    "browserless shared-client mutation fence requires class __delattr__ support"
                )

            @wraps(original_delattr)
            def guarded_delattr(instance: Any, name: str) -> Any:
                lock = _instance_fence_lock(instance)
                if name in _ATOMIC_MUTATION_SURFACES and _valid_lock(lock):
                    raise TypeError(
                        f"cannot delete fenced mutation entrypoint {name} while browserless transport is active"
                    )
                return original_delattr(instance, name)

            setattr(guarded_delattr, _CLASS_DELATTR_MARKER, True)
            try:
                setattr(cls, "__delattr__", guarded_delattr)
            except (AttributeError, TypeError) as error:
                raise TypeError(
                    "browserless request transport cannot guard mutation-method deletion "
                    f"for compatible client class {cls.__name__}"
                ) from error


def _install_atomic_mutation_fences(client: Any, lock: Any) -> None:
    """Serialize, refresh, and guard mutation authority on one canonical client.

    Browserless owns the same re-entrant lock across canonical attach, Sentinel
    preflight, prepared mutation, and canonical reconciliation. Ordinary writes
    acquire that lock too. Every top-level continuation mutation refreshes after
    lock acquisition. Arbitrary callback/replacement nesting fails closed before a
    second lock or write can be entered; only the known send_to_conversation()
    delegation to send()/prepared-send remains re-entrant.

    The compatible-client assignment/deletion guards keep later instance-level
    mutation-method replacement inside the same lock domain instead of letting a
    decorator silently remove the fence.
    """

    if not _valid_lock(lock):
        raise TypeError("browserless shared-client mutation fence requires a lock")

    instance_dict = getattr(client, "__dict__", None)
    if not isinstance(instance_dict, dict):
        raise TypeError(
            "browserless request transport requires mutable client instance state "
            "for shared-client write serialization"
        )

    _install_assignment_guards(client)
    existing_lock = instance_dict.get(_INSTANCE_LOCK_ATTR)
    if existing_lock is not None and existing_lock is not lock:
        raise TypeError("browserless shared-client mutation fence lock state is inconsistent")
    setattr(client, _INSTANCE_LOCK_ATTR, lock)

    for name in _ATOMIC_MUTATION_SURFACES:
        current = getattr(client, name, None)
        if not callable(current):
            continue
        setattr(client, name, current)


def assert_atomic_mutation_fence(client: Any, lock: Any) -> None:
    """Fail closed if a compatible client bypassed the installed mutation fence."""

    if _instance_fence_lock(client) is not lock:
        from .browserless_request_transport import BrowserlessProtocolDriftError

        raise BrowserlessProtocolDriftError(
            "shared-client mutation-fence lock state changed after transport construction",
            request_stage="browserless_mutation_fence",
        )

    if not getattr(getattr(type(client), "__setattr__", None), _CLASS_SETATTR_MARKER, False):
        from .browserless_request_transport import BrowserlessProtocolDriftError

        raise BrowserlessProtocolDriftError(
            "shared-client mutation replacement guard is no longer installed",
            request_stage="browserless_mutation_fence",
        )
    if not getattr(getattr(type(client), "__delattr__", None), _CLASS_DELATTR_MARKER, False):
        from .browserless_request_transport import BrowserlessProtocolDriftError

        raise BrowserlessProtocolDriftError(
            "shared-client mutation deletion guard is no longer installed",
            request_stage="browserless_mutation_fence",
        )

    for name in _ATOMIC_MUTATION_SURFACES:
        current = getattr(client, name, None)
        if callable(current) and getattr(current, _FENCE_MARKER, None) is not lock:
            from .browserless_request_transport import BrowserlessProtocolDriftError

            raise BrowserlessProtocolDriftError(
                f"shared-client mutation entrypoint {name} escaped its browserless fence",
                request_stage="browserless_mutation_fence",
            )


def _guard_browserless_execute(self: Any, current: Callable[..., Any], client: Any) -> Any:
    if getattr(current, _BROWSERLESS_EXECUTE_MARKER, False):
        return current

    @wraps(current)
    def execute(*args: Any, **kwargs: Any) -> Any:
        conflict = _authority_conflict(client, "browserless_request")
        if conflict is not None:
            active_client, active_name = conflict
            error = _nested_mutation_error(
                active_client=active_client,
                active_name=active_name,
                client=client,
                name="browserless_request",
            )
            from .browserless_request_transport import BrowserlessRequestTransportError

            raise BrowserlessRequestTransportError(
                str(error),
                request_stage="browserless_mutation_fence",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
            ) from error

        with _mutation_authority(client, "browserless_request"):
            return current(*args, **kwargs)

    setattr(execute, _BROWSERLESS_EXECUTE_MARKER, True)
    return execute


def gate_browserless_transport_init(
    original_init: Callable[..., Any],
) -> Callable[..., Any]:
    """Install same-client mutation authority after browserless captures raw send."""

    @wraps(original_init)
    def init(self: Any, canonical_client: Any) -> None:
        original_init(self, canonical_client)
        lock = getattr(self, "_write_lock", None)
        client = getattr(self, "client", canonical_client)
        _install_atomic_mutation_fences(client, lock)
        assert_atomic_mutation_fence(client, lock)

        current_execute = getattr(self, "_execute", None)
        if not callable(current_execute):
            raise TypeError("browserless request transport requires callable _execute()")
        self._execute = _guard_browserless_execute(self, current_execute, client)

    return init
