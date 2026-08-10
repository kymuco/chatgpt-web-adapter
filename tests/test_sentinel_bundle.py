from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.sentinel_bundle import (
    CONVERSATION_PATH,
    CONVERSATION_PREPARE_PATH,
    SentinelBundleStore,
    gate_prepared_build_headers,
    gate_prepared_get_ready_requirements,
    gate_prepared_text_send,
    get_prepared_sentinel_bundle,
    prefetch_finalized_sentinel_bundle,
    redact_ephemeral_write_headers,
)
from chatgpt_web_adapter.sentinel_transaction import FinalizedSentinelBundle


def _bundle(*, acquired: float = 100.0, expires: float = 200.0) -> FinalizedSentinelBundle:
    return FinalizedSentinelBundle(
        "secret-requirements",
        "secret-proof",
        "secret-turnstile",
        acquired,
        expires,
    )


class PrefetchClient:
    def __init__(self) -> None:
        self.auth = SimpleNamespace(proof_token=None, turnstile_token="secret-turnstile")
        self.debug_trace_dir = None
        self.calls: list[str] = []

    @staticmethod
    def _build_headers(extra):
        return {key: value for key, value in extra.items() if value is not None}

    @staticmethod
    def _build_proof_header(requirements):
        return "secret-proof"

    def _json_request(self, method, url, payload, headers):
        if url.endswith("/prepare"):
            self.calls.append("prepare")
            return 200, {
                "persona": "chatgpt-paid",
                "prepare_token": "prepare",
                "turnstile": {"required": True, "dx": "dx"},
                "proofofwork": {"required": True, "seed": "seed", "difficulty": "01"},
                "so": {"required": True, "collector_dx": "c", "snapshot_dx": "s"},
            }
        self.calls.append("finalize")
        return 200, {
            "persona": "chatgpt-paid",
            "token": "secret-requirements",
            "expire_after": 540,
            "expire_at": 1_800_000_000,
        }

    @staticmethod
    def _emit_event(callback, event_type, **payload):
        if callback is not None:
            callback({"type": event_type, **payload})


def test_store_release_then_consume_is_one_shot() -> None:
    store = SentinelBundleStore()
    store.install(_bundle())
    first = store.reserve(now=110.0)
    assert first is not None and first.release() is True
    second = store.reserve(now=120.0)
    assert second is not None
    assert second.consume(now=120.0).requirements_token == "secret-requirements"
    assert second.release() is False
    assert store.reserve(now=120.0) is None


def test_store_rejects_second_reservation() -> None:
    store = SentinelBundleStore()
    store.install(_bundle())
    first = store.reserve(now=110.0)
    assert first is not None
    with pytest.raises(RequestError, match="SENTINEL_BUNDLE_BUSY"):
        store.reserve(now=110.0)
    assert first.release() is True


def test_expiry_is_enforced_before_and_after_reservation() -> None:
    store = SentinelBundleStore()
    store.install(_bundle(acquired=10.0, expires=20.0))
    assert store.reserve(now=20.0) is None

    store.install(_bundle(acquired=10.0, expires=20.0))
    reservation = store.reserve(now=19.0)
    assert reservation is not None
    with pytest.raises(RequestError, match="SENTINEL_BUNDLE_EXPIRED"):
        reservation.consume(now=20.0)
    assert store.reserve(now=20.0) is None


def test_get_prepared_bundle_prefers_valid_prefetch() -> None:
    client = PrefetchClient()
    store = SentinelBundleStore()
    store.install(_bundle(acquired=0.0, expires=10**12))
    client._sentinel_bundle_store = store
    reservation = get_prepared_sentinel_bundle(client)
    assert client.calls == []
    assert reservation.consume().proof_token == "secret-proof"


def test_explicit_prefetch_caches_for_later_write() -> None:
    client = PrefetchClient()
    assert prefetch_finalized_sentinel_bundle(client) is True
    assert client.calls == ["prepare", "finalize"]
    assert client.auth.turnstile_token is None
    reservation = get_prepared_sentinel_bundle(client)
    assert client.calls == ["prepare", "finalize"]
    assert reservation.consume().requirements_token == "secret-requirements"


def test_ephemeral_headers_are_always_redacted() -> None:
    sanitize = redact_ephemeral_write_headers(lambda self, key, value: value)
    client = SimpleNamespace(debug_trace_sanitize=False)
    for header in (
        "x-conduit-token",
        "openai-sentinel-chat-requirements-token",
        "openai-sentinel-proof-token",
        "openai-sentinel-turnstile-token",
    ):
        assert sanitize(client, header, "secret") == "<redacted>"
    assert sanitize(client, "x-debug-visible", "visible") == "visible"


def test_prepared_context_uses_bundle_without_legacy_requirements() -> None:
    client = SimpleNamespace(events=[])
    store = SentinelBundleStore()
    store.install(_bundle(acquired=0.0, expires=10**12))
    client._sentinel_bundle_store = store
    legacy_calls: list[str] = []

    def emit_event(callback, event_type, **payload):
        event = {"type": event_type, **payload}
        client.events.append(event)
        if callback is not None:
            callback(event)

    client._emit_event = emit_event

    def legacy_requirements(self):
        legacy_calls.append("legacy")
        return {"token": "legacy", "turnstile": {"required": False}}, "legacy-proof"

    def raw_headers(self, extra):
        return {key: value for key, value in (extra or {}).items() if value is not None}

    gated_requirements = gate_prepared_get_ready_requirements(legacy_requirements)
    gated_headers = gate_prepared_build_headers(raw_headers)
    captured = {}

    def prepared_body(self, *, on_event=None):
        prepare_headers = gated_headers(
            self,
            {"x-openai-target-path": CONVERSATION_PREPARE_PATH, "x-oai-turn-trace-id": "wrong-1"},
        )
        requirements, proof = gated_requirements(self)
        final_headers = gated_headers(
            self,
            {
                "x-openai-target-path": CONVERSATION_PATH,
                "x-oai-turn-trace-id": "wrong-2",
                "openai-sentinel-chat-requirements-token": "stale",
                "openai-sentinel-proof-token": "stale",
            },
        )
        captured.update(prepare=prepare_headers, final=final_headers, req=requirements, proof=proof)
        return "ok"

    events: list[dict] = []
    assert gate_prepared_text_send(prepared_body)(client, on_event=events.append) == "ok"
    assert legacy_calls == []
    assert captured["req"]["token"] == "secret-requirements"
    assert captured["proof"] == "secret-proof"
    assert captured["prepare"]["x-oai-turn-trace-id"] == captured["final"]["x-oai-turn-trace-id"]
    assert captured["final"]["openai-sentinel-chat-requirements-token"] == "secret-requirements"
    assert captured["final"]["openai-sentinel-proof-token"] == "secret-proof"
    assert captured["final"]["openai-sentinel-turnstile-token"] == "secret-turnstile"
    assert store.reserve(now=120.0) is None
    assert "secret-requirements" not in repr(events)
    assert gated_requirements(client)[0]["token"] == "legacy"
    assert legacy_calls == ["legacy"]


def test_prepared_context_rejects_double_consumption() -> None:
    client = SimpleNamespace(_emit_event=lambda *args, **kwargs: None)
    store = SentinelBundleStore()
    store.install(_bundle(acquired=0.0, expires=10**12))
    client._sentinel_bundle_store = store
    gated = gate_prepared_get_ready_requirements(
        lambda self: (_ for _ in ()).throw(AssertionError("legacy must not run"))
    )

    def prepared_body(self):
        gated(self)
        gated(self)

    with pytest.raises(RequestError, match="SENTINEL_BUNDLE_ALREADY_CONSUMED"):
        gate_prepared_text_send(prepared_body)(client)


def test_final_headers_require_consumed_bundle_and_context_resets() -> None:
    client = SimpleNamespace()
    gated_headers = gate_prepared_build_headers(lambda self, extra: dict(extra or {}))

    def prepared_body(self):
        gated_headers(self, {"x-openai-target-path": CONVERSATION_PATH})

    with pytest.raises(RequestError, match="SENTINEL_BUNDLE_NOT_CONSUMED"):
        gate_prepared_text_send(prepared_body)(client)

    legacy_calls: list[str] = []
    gated_requirements = gate_prepared_get_ready_requirements(
        lambda self: (legacy_calls.append("legacy") or ({"token": "legacy"}, None))
    )
    assert gated_requirements(client)[0]["token"] == "legacy"
    assert legacy_calls == ["legacy"]
