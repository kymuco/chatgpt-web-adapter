from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import threading
from typing import Any, Callable, Iterator

from .exceptions import RequestError
from .types import ChatConversation


_FENCE_MARKER = "_cwa_browserless_shared_write_fence_lock"
_FENCE_ORIGINAL = "_cwa_browserless_shared_write_fence_original"
_FENCE_SELF = "_cwa_browserless_shared_write_fence_wrapper"
_FENCE_PREDECESSORS = "_cwa_browserless_shared_write_fence_predecessors"
_FENCE_DIRECT = "_cwa_browserless_shared_write_fence_direct_callable"
_INSTANCE_LOCK_ATTR = "_cwa_browserless_shared_write_fence_lock_state"
_CLASS_SETATTR_MARKER = "_cwa_browserless_shared_write_fence_setattr_guard"
_CLASS_DELATTR_MARKER = "_cwa_browserless_shared_write_fence_delattr_guard"
_BROWSERLESS_EXECUTE_MARKER = "_cwa_browserless_shared_write_fence_execute_guard"
_CLASS_GUARD_LOCK = threading.Lock()
_MUTATION_AUTHORITY_STATE = threading.local()
_FENCE_PREDECESSOR_STATE = threading.local()

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


def _is_actual_fence_wrapper(value: Any, lock: Any | None = None) -> bool:
    """Distinguish our real wrapper from decorators that copied wrapper metadata."""

    if not callable(value) or getattr(value, _FENCE_SELF, None) is not value:
        return False
    installed_lock = getattr(value, _FENCE_MARKER, None)
    if lock is not None and installed_lock is not lock:
        return False
    return _valid_lock(installed_lock)


def _declared_slot_names(cls: type[Any]) -> Iterator[str]:
    """Yield concrete slot attributes declared anywhere in one callable's MRO."""

    for owner in getattr(cls, "__mro__", (cls,)):
        slots = vars(owner).get("__slots__", ())
        if isinstance(slots, str):
            slot_names = (slots,)
        else:
            try:
                slot_names = tuple(slots)
            except TypeError:
                continue

        for raw_slot in slot_names:
            if not isinstance(raw_slot, str):
                continue
            slot = raw_slot.strip()
            if not slot or slot in {"__dict__", "__weakref__"}:
                continue
            # Private slots are name-mangled by the class that declared them.
            if slot.startswith("__") and not slot.endswith("__"):
                owner_name = getattr(owner, "__name__", "").lstrip("_")
                if owner_name:
                    slot = f"_{owner_name}{slot}"
            yield slot


def _callable_directly_captures(value: Any, target: Any) -> bool:
    """Return whether a replacement directly retains one exact predecessor callable.

    Only shallow composition links count. This covers normal functions and callable
    decorator instances without recursively trusting arbitrary object graphs.
    """

    if not callable(value) or not callable(target):
        return False
    if value is target:
        return True
    if getattr(value, "__wrapped__", None) is target:
        return True

    closure = getattr(value, "__closure__", None)
    if isinstance(closure, tuple):
        for cell in closure:
            try:
                if cell.cell_contents is target:
                    return True
            except ValueError:
                continue

    defaults = getattr(value, "__defaults__", None)
    if isinstance(defaults, tuple) and any(candidate is target for candidate in defaults):
        return True

    kwdefaults = getattr(value, "__kwdefaults__", None)
    if isinstance(kwdefaults, dict) and any(
        candidate is target for candidate in kwdefaults.values()
    ):
        return True

    instance_dict = getattr(value, "__dict__", None)
    if isinstance(instance_dict, dict) and any(
        candidate is target for candidate in instance_dict.values()
    ):
        return True

    for slot in _declared_slot_names(type(value)):
        try:
            if getattr(value, slot) is target:
                return True
        except (AttributeError, TypeError):
            continue

    return False


def _predecessor_stack() -> list[set[int]]:
    stack = getattr(_FENCE_PREDECESSOR_STATE, "stack", None)
    if stack is None:
        stack = []
        _FENCE_PREDECESSOR_STATE.stack = stack
    return stack


@contextmanager
def _allow_fence_predecessors(predecessors: tuple[Any, ...]) -> Iterator[None]:
    if not predecessors:
        yield
        return

    stack = _predecessor_stack()
    stack.append({id(item) for item in predecessors})
    try:
        yield
    finally:
        stack.pop()
        if not stack:
            try:
                delattr(_FENCE_PREDECESSOR_STATE, "stack")
            except AttributeError:
                pass


def _consume_allowed_fence_predecessor(wrapper: Any) -> bool:
    stack = getattr(_FENCE_PREDECESSOR_STATE, "stack", None)
    if not stack:
        return False
    allowed = stack[-1]
    identity = id(wrapper)
    if identity not in allowed:
        return False
    # One structural predecessor edge authorizes one call only. A decorator that
    # invokes a captured old send twice still fails closed on the second attempt.
    allowed.remove(identity)
    return True


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


def _fence_callable(
    client: Any,
    name: str,
    current: Callable[..., Any],
    lock: Any,
    *,
    predecessor: Any = None,
) -> Any:
    if _is_actual_fence_wrapper(current, lock):
        return current
    if _is_actual_fence_wrapper(current):
        raise TypeError(
            f"browserless shared-client mutation fence for {name} uses a different lock"
        )

    predecessors: tuple[Any, ...] = ()
    if (
        _is_actual_fence_wrapper(predecessor, lock)
        and _callable_directly_captures(current, predecessor)
    ):
        predecessors = (predecessor,)

    @wraps(current)
    def fenced(*args: Any, **kwargs: Any) -> Any:
        if _consume_allowed_fence_predecessor(fenced):
            with _allow_fence_predecessors(predecessors):
                return current(*args, **kwargs)

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
                with _allow_fence_predecessors(predecessors):
                    return current(*call_args, **call_kwargs)

    # functools.wraps() deliberately copies the wrapped callable's __dict__. Set
    # our identity metadata afterwards so copied fence attributes on unrelated
    # decorators can never make them look like an actual package fence wrapper.
    setattr(fenced, _FENCE_MARKER, lock)
    setattr(fenced, _FENCE_ORIGINAL, current)
    setattr(fenced, _FENCE_SELF, fenced)
    setattr(fenced, _FENCE_PREDECESSORS, predecessors)
    return fenced


def unfenced_mutation_callable(value: Any) -> Any:
    """Return a direct callable underneath this module's instance fence wrapper.

    If the wrapped callable is a decorator that directly captured the exact prior
    package fence for this same mutation surface, preserve that decorator and grant
    the recorded predecessor edge one single-use bypass while the decorator runs.
    """

    if not _is_actual_fence_wrapper(value):
        return value

    cached = getattr(value, _FENCE_DIRECT, None)
    if callable(cached):
        return cached

    original = getattr(value, _FENCE_ORIGINAL, None)
    if not callable(original):
        return value
    predecessors = getattr(value, _FENCE_PREDECESSORS, ())
    if not isinstance(predecessors, tuple):
        predecessors = ()

    if not predecessors:
        if _is_actual_fence_wrapper(original):
            return unfenced_mutation_callable(original)
        return original

    @wraps(original, updated=())
    def direct(*args: Any, **kwargs: Any) -> Any:
        with _allow_fence_predecessors(predecessors):
            return original(*args, **kwargs)

    setattr(value, _FENCE_DIRECT, direct)
    return direct


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
                    instance_dict = getattr(instance, "__dict__", None)
                    predecessor = (
                        instance_dict.get(name)
                        if isinstance(instance_dict, dict)
                        else None
                    )
                    value = _fence_callable(
                        instance,
                        name,
                        value,
                        lock,
                        predecessor=predecessor,
                    )
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
        if callable(current) and not _is_actual_fence_wrapper(current, lock):
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
