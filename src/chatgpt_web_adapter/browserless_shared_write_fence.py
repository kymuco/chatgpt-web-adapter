from __future__ import annotations

from functools import wraps
from typing import Any, Callable


_FENCE_MARKER = "_cwa_browserless_shared_write_fence_lock"
_FENCE_ORIGINAL = "_cwa_browserless_shared_write_fence_original"
_ATOMIC_MUTATION_SURFACES = (
    "send",
    "_send_existing_text_prepared",
    "approve_pending_action",
    "send_payload",
    "send_to_conversation",
    "send_browser_native",
)


def _valid_lock(lock: Any) -> bool:
    return callable(getattr(lock, "acquire", None)) and callable(
        getattr(lock, "release", None)
    )


def _install_atomic_mutation_fences(client: Any, lock: Any) -> None:
    """Serialize known client mutation entrypoints with the browserless client lock.

    Browserless holds this same re-entrant lock across canonical attach, Sentinel
    preflight, prepared mutation, and canonical reconciliation. Fencing the
    shared client's ordinary mutation entrypoints prevents a same-client writer
    from advancing a continuation parent after browserless attach but before the
    browserless final request.
    """

    if not _valid_lock(lock):
        raise TypeError("browserless shared-client mutation fence requires a lock")

    instance_dict = getattr(client, "__dict__", None)
    if not isinstance(instance_dict, dict):
        raise TypeError(
            "browserless request transport requires mutable client instance state "
            "for shared-client write serialization"
        )

    for name in _ATOMIC_MUTATION_SURFACES:
        current = getattr(client, name, None)
        if not callable(current):
            continue

        installed_lock = getattr(current, _FENCE_MARKER, None)
        if installed_lock is lock:
            continue
        if installed_lock is not None:
            raise TypeError(
                f"browserless shared-client mutation fence for {name} uses a different lock"
            )

        @wraps(current)
        def fenced(*args: Any, __current: Callable[..., Any] = current, **kwargs: Any) -> Any:
            with lock:
                return __current(*args, **kwargs)

        setattr(fenced, _FENCE_MARKER, lock)
        setattr(fenced, _FENCE_ORIGINAL, current)
        setattr(client, name, fenced)


def gate_browserless_transport_init(
    original_init: Callable[..., Any],
) -> Callable[..., Any]:
    """Install a same-client mutation fence after browserless captures raw send.

    ``BrowserlessRequestTransport.__init__`` first captures its direct-send
    callable and creates/recovers the per-client RLock. Installing the public
    client fences afterwards therefore leaves the browserless direct path
    unchanged while making ordinary writes through that same client participate
    in the same serialization domain.
    """

    @wraps(original_init)
    def init(self: Any, canonical_client: Any) -> None:
        original_init(self, canonical_client)
        lock = getattr(self, "_write_lock", None)
        client = getattr(self, "client", canonical_client)
        _install_atomic_mutation_fences(client, lock)

    return init
