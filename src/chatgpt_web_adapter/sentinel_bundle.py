from __future__ import annotations

import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

from .exceptions import RequestError
from .sentinel_transaction import FinalizedSentinelBundle, acquire_finalized_sentinel_bundle

CONVERSATION_PREPARE_PATH = "/backend-api/f/conversation/prepare"
CONVERSATION_PATH = "/backend-api/f/conversation"
ALWAYS_REDACT_WRITE_HEADERS = frozenset(
    {
        "x-conduit-token",
        "openai-sentinel-chat-requirements-token",
        "openai-sentinel-proof-token",
        "openai-sentinel-turnstile-token",
    }
)
_CLIENT_STATE_LOCK = threading.Lock()
_PREPARED_SEND_ACTIVE: ContextVar[bool] = ContextVar(
    "chatgpt_web_adapter_prepared_sentinel_active",
    default=False,
)
_PREPARED_TURN_TRACE_ID: ContextVar[str | None] = ContextVar(
    "chatgpt_web_adapter_prepared_turn_trace_id",
    default=None,
)
_PREPARED_ON_EVENT: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "chatgpt_web_adapter_prepared_on_event",
    default=None,
)
_PREPARED_CONSUMED_BUNDLE: ContextVar[FinalizedSentinelBundle | None] = ContextVar(
    "chatgpt_web_adapter_prepared_consumed_bundle",
    default=None,
)


@dataclass
class SentinelBundleReservation:
    _store: "SentinelBundleStore" = field(repr=False)
    _bundle: FinalizedSentinelBundle = field(repr=False)
    _active: bool = field(default=True, repr=False)

    @property
    def bundle(self) -> FinalizedSentinelBundle:
        return self._bundle

    @property
    def active(self) -> bool:
        return self._active

    def release(self) -> bool:
        return self._store._release(self)

    def consume(self, *, now: float | None = None) -> FinalizedSentinelBundle:
        return self._store._consume(self, now=now)


class SentinelBundleStore:
    """Thread-safe single-slot finalized-bundle store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundle: FinalizedSentinelBundle | None = None
        self._reserved = False

    def install(self, bundle: FinalizedSentinelBundle) -> None:
        if not isinstance(bundle, FinalizedSentinelBundle):
            raise TypeError("bundle must be FinalizedSentinelBundle")
        with self._lock:
            if self._reserved:
                raise RequestError(
                    "SENTINEL_BUNDLE_BUSY: cannot replace a reserved bundle",
                    request_stage="sentinel_bundle_install",
                )
            self._bundle = bundle

    def reserve(self, *, now: float | None = None) -> SentinelBundleReservation | None:
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            if self._reserved:
                raise RequestError(
                    "SENTINEL_BUNDLE_BUSY: finalized bundle is already reserved",
                    request_stage="sentinel_bundle_reserve",
                )
            bundle = self._bundle
            if bundle is None:
                return None
            if bundle.is_expired(now=current):
                self._bundle = None
                return None
            self._reserved = True
            return SentinelBundleReservation(self, bundle)

    def _release(self, reservation: SentinelBundleReservation) -> bool:
        with self._lock:
            if not reservation._active:
                return False
            if self._reserved and self._bundle is reservation._bundle:
                self._reserved = False
            reservation._active = False
            return True

    def _consume(
        self,
        reservation: SentinelBundleReservation,
        *,
        now: float | None = None,
    ) -> FinalizedSentinelBundle:
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            if (
                not reservation._active
                or not self._reserved
                or self._bundle is not reservation._bundle
            ):
                raise RequestError(
                    "SENTINEL_BUNDLE_NOT_RESERVED: bundle cannot be consumed",
                    request_stage="sentinel_bundle_consume",
                )
            bundle = reservation._bundle
            reservation._active = False
            self._reserved = False
            self._bundle = None
            if bundle.is_expired(now=current):
                raise RequestError(
                    "SENTINEL_BUNDLE_EXPIRED: finalized bundle expired before write",
                    request_stage="sentinel_bundle_consume",
                )
            return bundle


def _emit_event(
    client: Any,
    callback: Callable[[dict[str, Any]], None] | None,
    event_type: str,
    **payload: Any,
) -> None:
    emitter = getattr(client, "_emit_event", None)
    if callable(emitter):
        emitter(callback, event_type, **payload)
    elif callback is not None:
        callback({"type": event_type, **payload})


def _client_state(client: Any) -> tuple[SentinelBundleStore, Any]:
    with _CLIENT_STATE_LOCK:
        store = getattr(client, "_sentinel_bundle_store", None)
        if not isinstance(store, SentinelBundleStore):
            store = SentinelBundleStore()
            client._sentinel_bundle_store = store
        acquire_lock = getattr(client, "_sentinel_bundle_acquire_lock", None)
        if not hasattr(acquire_lock, "acquire") or not hasattr(acquire_lock, "release"):
            acquire_lock = threading.Lock()
            client._sentinel_bundle_acquire_lock = acquire_lock
    return store, acquire_lock


def prefetch_finalized_sentinel_bundle(
    client: Any,
    *,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> bool:
    """Synchronously cache one bundle; never starts background refill."""

    store, acquire_lock = _client_state(client)
    with acquire_lock:
        reservation = store.reserve()
        if reservation is not None:
            reservation.release()
            _emit_event(client, on_event, "sentinel_bundle_prefetch_skipped", reason="available")
            return False
        bundle = acquire_finalized_sentinel_bundle(client, on_event=on_event)
        store.install(bundle)
        _emit_event(
            client,
            on_event,
            "sentinel_bundle_prefetched",
            requirements_token_present=True,
            proof_present=True,
            turnstile_present=True,
        )
        return True


def get_prepared_sentinel_bundle(
    client: Any,
    *,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> SentinelBundleReservation:
    """Reserve a valid prefetch or synchronously acquire one."""

    store, acquire_lock = _client_state(client)
    with acquire_lock:
        reservation = store.reserve()
        if reservation is not None:
            return reservation
        bundle = acquire_finalized_sentinel_bundle(client, on_event=on_event)
        store.install(bundle)
        reservation = store.reserve()
        if reservation is None:  # pragma: no cover
            raise RequestError(
                "SENTINEL_BUNDLE_INTERNAL: finalized bundle was not reservable",
                request_stage="sentinel_bundle_reserve",
            )
        return reservation


def gate_prepared_get_ready_requirements(
    original_get_ready_requirements: Callable[..., tuple[dict[str, Any], str | None]],
) -> Callable[..., tuple[dict[str, Any], str | None]]:
    """Route only prepared sends away from the legacy single-step endpoint."""

    @wraps(original_get_ready_requirements)
    def get_ready_requirements(self: Any) -> tuple[dict[str, Any], str | None]:
        if not _PREPARED_SEND_ACTIVE.get():
            return original_get_ready_requirements(self)
        if _PREPARED_CONSUMED_BUNDLE.get() is not None:
            raise RequestError(
                "SENTINEL_BUNDLE_ALREADY_CONSUMED: prepared write requested "
                "requirements more than once",
                request_stage="sentinel_bundle_consume",
            )
        reservation: SentinelBundleReservation | None = None
        try:
            reservation = get_prepared_sentinel_bundle(
                self,
                on_event=_PREPARED_ON_EVENT.get(),
            )
            bundle = reservation.consume()
        finally:
            if reservation is not None:
                reservation.release()
        _PREPARED_CONSUMED_BUNDLE.set(bundle)
        _emit_event(
            self,
            _PREPARED_ON_EVENT.get(),
            "sentinel_bundle_consumed",
            requirements_token_present=True,
            proof_present=True,
            turnstile_present=True,
        )
        return {"token": bundle.requirements_token, "turnstile": {"required": True}}, bundle.proof_token

    return get_ready_requirements


def gate_prepared_build_headers(
    original_build_headers: Callable[..., dict[str, str]],
) -> Callable[..., dict[str, str]]:
    """Bind one turn trace and one consumed bundle to prepared write headers."""

    @wraps(original_build_headers)
    def build_headers(
        self: Any,
        extra: dict[str, str | None] | None = None,
    ) -> dict[str, str]:
        patched = dict(extra or {})
        if _PREPARED_SEND_ACTIVE.get():
            target_path = patched.get("x-openai-target-path")
            turn_trace_id = _PREPARED_TURN_TRACE_ID.get()
            if turn_trace_id and target_path in {CONVERSATION_PREPARE_PATH, CONVERSATION_PATH}:
                patched["x-oai-turn-trace-id"] = turn_trace_id
            if target_path == CONVERSATION_PATH:
                bundle = _PREPARED_CONSUMED_BUNDLE.get()
                if bundle is None:
                    raise RequestError(
                        "SENTINEL_BUNDLE_NOT_CONSUMED: final prepared write cannot "
                        "build headers before bundle consumption",
                        request_stage="sentinel_bundle_headers",
                    )
                patched["openai-sentinel-chat-requirements-token"] = bundle.requirements_token
                patched["openai-sentinel-proof-token"] = bundle.proof_token
                patched["openai-sentinel-turnstile-token"] = bundle.turnstile_token
        return original_build_headers(self, patched)

    return build_headers


def redact_ephemeral_write_headers(
    original_sanitize_header_value: Callable[..., str],
) -> Callable[..., str]:
    """Always redact conduit/Sentinel write credentials, even in raw debug mode."""

    @wraps(original_sanitize_header_value)
    def sanitize_header_value(self: Any, key: str, value: str) -> str:
        if key.strip().lower() in ALWAYS_REDACT_WRITE_HEADERS:
            return "<redacted>"
        return original_sanitize_header_value(self, key, value)

    return sanitize_header_value


def gate_prepared_text_send(original_send: Callable[..., Any]) -> Callable[..., Any]:
    """Establish an execution-local prepared-turn transaction context."""

    @wraps(original_send)
    def send(self: Any, *args: Any, **kwargs: Any) -> Any:
        active_token = _PREPARED_SEND_ACTIVE.set(True)
        trace_token = _PREPARED_TURN_TRACE_ID.set(str(uuid.uuid4()))
        event_token = _PREPARED_ON_EVENT.set(kwargs.get("on_event"))
        bundle_token = _PREPARED_CONSUMED_BUNDLE.set(None)
        try:
            return original_send(self, *args, **kwargs)
        finally:
            _PREPARED_CONSUMED_BUNDLE.reset(bundle_token)
            _PREPARED_ON_EVENT.reset(event_token)
            _PREPARED_TURN_TRACE_ID.reset(trace_token)
            _PREPARED_SEND_ACTIVE.reset(active_token)

    return send
