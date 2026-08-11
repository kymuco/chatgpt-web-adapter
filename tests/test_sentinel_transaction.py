from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.sentinel_transaction import (
    FinalizedSentinelBundle,
    SentinelChallengeContext,
    SentinelChallengeEvidence,
    acquire_finalized_sentinel_bundle,
    set_sentinel_bundle_provider,
    set_sentinel_challenge_provider,
)


class TransactionClient:
    def __init__(self) -> None:
        self.auth = SimpleNamespace(
            proof_token=None,
            turnstile_token="legacy-persisted-turnstile",
        )
        self.debug_trace_dir = object()
        self.calls: list[str] = []
        self.events: list[dict] = []
        self.traces: list[tuple[str, dict]] = []
        self.finalize_payload = None
        self.provider_contexts: list[SentinelChallengeContext] = []
        self.prepare_response = {
            "persona": "chatgpt-paid",
            "prepare_token": "secret-prepare-token",
            "turnstile": {"required": True, "dx": "secret-turnstile-dx"},
            "proofofwork": {
                "required": True,
                "seed": "secret-pow-seed",
                "difficulty": "06eb35",
            },
            "so": {
                "required": True,
                "collector_dx": "secret-collector-dx",
                "snapshot_dx": "secret-snapshot-dx",
            },
        }
        self.prepare_status = 200
        self.finalize_status = 200
        self.finalize_response = {
            "persona": "chatgpt-paid",
            "token": "secret-requirements",
            "expire_after": 540,
            "expire_at": time.time() + 540,
        }
        self.expected_prepare_input = None

    @staticmethod
    def _build_headers(extra):
        return {key: value for key, value in extra.items() if value is not None}

    @staticmethod
    def _build_proof_header(requirements):
        assert requirements["proofofwork"]["seed"] == "secret-pow-seed"
        return "secret-proof"

    def _json_request(self, method, url, payload, headers):
        assert method == "POST"
        if url.endswith("/sentinel/chat-requirements/prepare"):
            self.calls.append("prepare")
            assert payload == {"p": self.expected_prepare_input}
            return self.prepare_status, self.prepare_response
        if url.endswith("/sentinel/chat-requirements/finalize"):
            self.calls.append("finalize")
            self.finalize_payload = dict(payload)
            return self.finalize_status, self.finalize_response
        raise AssertionError(url)

    def _write_debug_trace(self, kind, payload):
        self.traces.append((kind, payload))

    def _emit_event(self, callback, event_type, **payload):
        event = {"type": event_type, **payload}
        self.events.append(event)
        if callback is not None:
            callback(event)

    def install_current_provider(
        self,
        *,
        prepare_token: str | None = None,
        turnstile_dx: str | None = None,
        turnstile_token: str = "current-turnstile-token",
    ) -> None:
        def provider(context: SentinelChallengeContext) -> SentinelChallengeEvidence:
            self.provider_contexts.append(context)
            return SentinelChallengeEvidence(
                prepare_token=(
                    context.prepare_token if prepare_token is None else prepare_token
                ),
                turnstile_dx=(
                    context.turnstile_dx if turnstile_dx is None else turnstile_dx
                ),
                turnstile_token=turnstile_token,
            )

        set_sentinel_challenge_provider(self, provider)


def test_two_phase_finalize_uses_current_prepare_provider_bundle_only() -> None:
    client = TransactionClient()
    client.install_current_provider()
    bundle = acquire_finalized_sentinel_bundle(client)

    assert client.calls == ["prepare", "finalize"]
    assert len(client.provider_contexts) == 1
    context = client.provider_contexts[0]
    assert context.prepare_input is None
    assert context.prepare_token == "secret-prepare-token"
    assert context.persona == "chatgpt-paid"
    assert context.turnstile_dx == "secret-turnstile-dx"
    assert context.so_collector_dx == "secret-collector-dx"
    assert context.so_snapshot_dx == "secret-snapshot-dx"
    assert client.finalize_payload == {
        "prepare_token": "secret-prepare-token",
        "proofofwork": "secret-proof",
        "turnstile": "current-turnstile-token",
    }
    assert "so" not in client.finalize_payload
    # Persisted legacy compatibility material is not consumed or trusted by the
    # two-phase transaction and therefore cannot be mistaken for current evidence.
    assert client.auth.turnstile_token == "legacy-persisted-turnstile"
    assert bundle.requirements_token == "secret-requirements"
    assert bundle.proof_token == "secret-proof"
    assert bundle.turnstile_token == "current-turnstile-token"
    assert bundle.expires_monotonic > bundle.acquired_monotonic

    rendered = (
        repr(bundle)
        + repr(context)
        + repr(client.traces)
        + repr(client.events)
    )
    for secret in (
        "secret-prepare-token",
        "secret-turnstile-dx",
        "secret-pow-seed",
        "secret-collector-dx",
        "secret-snapshot-dx",
        "secret-requirements",
        "secret-proof",
        "current-turnstile-token",
    ):
        assert secret not in rendered
    assert {kind for kind, _payload in client.traces} == {
        "sentinel-prepare-live",
        "sentinel-finalize",
    }


def test_complete_browser_bundle_provider_skips_sdk_prepare_and_finalize() -> None:
    client = TransactionClient()
    captured_bundle = FinalizedSentinelBundle(
        requirements_token="browser-requirements",
        proof_token="browser-proof",
        turnstile_token="browser-turnstile",
        acquired_monotonic=time.monotonic(),
        expires_monotonic=time.monotonic() + 60,
        source="browser_finalize_capture",
    )
    seen_clients = []
    set_sentinel_bundle_provider(
        client,
        lambda provider_client: seen_clients.append(provider_client) or captured_bundle,
    )

    assert acquire_finalized_sentinel_bundle(client) is captured_bundle
    assert seen_clients == [client]
    assert client.calls == []


def test_complete_browser_bundle_provider_rejects_expired_bundle() -> None:
    client = TransactionClient()
    set_sentinel_bundle_provider(
        client,
        lambda _client: FinalizedSentinelBundle(
            "requirements",
            "proof",
            "turnstile",
            time.monotonic() - 20,
            time.monotonic() - 10,
        ),
    )

    with pytest.raises(RequestError, match="PROVIDER_EXPIRED"):
        acquire_finalized_sentinel_bundle(client)


def test_provider_receives_exact_prepare_input(monkeypatch) -> None:
    client = TransactionClient()
    client.auth.proof_token = ["browser-proof-material"]
    client.expected_prepare_input = "current-prepare-input"
    monkeypatch.setattr(
        "chatgpt_web_adapter.sentinel_transaction.client_mod._get_requirements_token",
        lambda proof: "current-prepare-input",
    )
    client.install_current_provider()

    acquire_finalized_sentinel_bundle(client)

    assert client.provider_contexts[0].prepare_input == "current-prepare-input"


def test_persisted_turnstile_never_authorizes_two_phase_finalize() -> None:
    client = TransactionClient()
    with pytest.raises(
        RequestError,
        match="SENTINEL_BROWSER_CHALLENGE_PROVIDER_REQUIRED",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_challenge_provider"
    assert client.calls == ["prepare"]
    assert client.auth.turnstile_token == "legacy-persisted-turnstile"


def test_provider_evidence_must_match_current_prepare_token() -> None:
    client = TransactionClient()
    client.install_current_provider(prepare_token="stale-prepare-token")
    with pytest.raises(RequestError, match="SENTINEL_CHALLENGE_BINDING_MISMATCH"):
        acquire_finalized_sentinel_bundle(client)
    assert client.calls == ["prepare"]


def test_provider_turnstile_must_match_current_descriptor() -> None:
    client = TransactionClient()
    client.install_current_provider(turnstile_dx="stale-turnstile-dx")
    with pytest.raises(RequestError, match="SENTINEL_CHALLENGE_BINDING_MISMATCH"):
        acquire_finalized_sentinel_bundle(client)
    assert client.calls == ["prepare"]


def test_required_so_does_not_block_browser_observed_finalize() -> None:
    client = TransactionClient()
    client.install_current_provider()
    bundle = acquire_finalized_sentinel_bundle(client)
    assert bundle.requirements_token == "secret-requirements"
    assert client.calls == ["prepare", "finalize"]
    assert client.provider_contexts[0].so_required is True


def test_provider_must_return_turnstile_evidence() -> None:
    client = TransactionClient()
    client.install_current_provider(turnstile_token="")
    with pytest.raises(
        RequestError,
        match="SENTINEL_TURNSTILE_EVIDENCE_REQUIRED",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_turnstile_gate"
    assert client.calls == ["prepare"]


@pytest.mark.parametrize("block", ["turnstile", "proofofwork", "so"])
def test_unobserved_required_false_policy_fails_closed(block: str) -> None:
    client = TransactionClient()
    client.prepare_response[block]["required"] = False
    client.install_current_provider()
    with pytest.raises(
        RequestError,
        match="SENTINEL_FINALIZE_POLICY_UNOBSERVED",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize_policy"
    assert client.calls == ["prepare"]
    assert client.provider_contexts == []


@pytest.mark.parametrize("block", ["turnstile", "proofofwork", "so"])
@pytest.mark.parametrize("value", ["false", 1, None, [], {}])
def test_required_policy_type_drift_fails_before_provider(block: str, value) -> None:
    client = TransactionClient()
    client.prepare_response[block]["required"] = value
    client.install_current_provider()
    with pytest.raises(
        RequestError,
        match="SENTINEL_PREPARE_CONTRACT_DRIFT",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_prepare"
    assert client.calls == ["prepare"]
    assert client.provider_contexts == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seed", None),
        ("seed", ""),
        ("seed", "   "),
        ("seed", 1),
        ("seed", []),
        ("seed", {}),
        ("difficulty", None),
        ("difficulty", ""),
        ("difficulty", "   "),
        ("difficulty", 1),
        ("difficulty", []),
        ("difficulty", {}),
        ("difficulty", "not-hex"),
        ("difficulty", "0x123"),
        ("difficulty", "06eb35 "),
    ],
)
def test_pow_descriptor_drift_fails_before_provider(field: str, value) -> None:
    client = TransactionClient()
    client.prepare_response["proofofwork"][field] = value
    client.install_current_provider()
    with pytest.raises(
        RequestError,
        match="SENTINEL_PREPARE_CONTRACT_DRIFT",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_prepare"
    assert client.calls == ["prepare"]
    assert client.provider_contexts == []


@pytest.mark.parametrize(
    "expire_after",
    [float("inf"), float("-inf"), float("nan"), 1e309],
)
def test_non_finite_finalize_ttl_fails_closed(expire_after: float) -> None:
    client = TransactionClient()
    client.install_current_provider()
    client.finalize_response["expire_after"] = expire_after
    with pytest.raises(
        RequestError,
        match="expire_after is not finite",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize"
    assert client.calls == ["prepare", "finalize"]


@pytest.mark.parametrize(
    "expire_at",
    [None, True, "1800000000", float("inf"), float("-inf"), float("nan")],
)
def test_invalid_absolute_finalize_expiry_fails_closed(expire_at) -> None:
    client = TransactionClient()
    client.install_current_provider()
    client.finalize_response["expire_at"] = expire_at
    with pytest.raises(
        RequestError,
        match="expire_at",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize"
    assert client.calls == ["prepare", "finalize"]


def test_absolute_finalize_expiry_clamps_relative_ttl() -> None:
    client = TransactionClient()
    client.install_current_provider()
    client.finalize_response["expire_after"] = 540
    client.finalize_response["expire_at"] = time.time() + 30

    bundle = acquire_finalized_sentinel_bundle(client)

    assert 20 <= bundle.expires_monotonic - bundle.acquired_monotonic <= 25


def test_finalize_failure_does_not_cache_or_restore_provider_evidence() -> None:
    client = TransactionClient()
    client.install_current_provider()
    client.finalize_status = 403
    client.finalize_response = {"detail": "rejected"}
    with pytest.raises(RequestError, match="Sentinel finalize rejected") as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize"
    assert client.calls == ["prepare", "finalize"]
    assert len(client.provider_contexts) == 1
    assert client.auth.turnstile_token == "legacy-persisted-turnstile"


def test_challenge_objects_and_bundle_hide_secret_values() -> None:
    context = SentinelChallengeContext(
        "UNIQUE_PREPARE_INPUT_SECRET_z0",
        "UNIQUE_PREPARE_SECRET_a1",
        "chatgpt-paid",
        "UNIQUE_DX_SECRET_b2",
        "UNIQUE_COLLECTOR_SECRET_c3",
        "UNIQUE_SNAPSHOT_SECRET_d4",
        True,
        True,
        True,
    )
    evidence = SentinelChallengeEvidence(
        "UNIQUE_PREPARE_SECRET_a1",
        "UNIQUE_DX_SECRET_b2",
        "UNIQUE_TURNSTILE_SECRET_e5",
    )
    bundle = FinalizedSentinelBundle(
        "UNIQUE_REQUIREMENTS_SECRET_f6",
        "UNIQUE_PROOF_SECRET_g7",
        "UNIQUE_TURNSTILE_SECRET_e5",
        1.0,
        2.0,
    )
    rendered = repr(context) + repr(evidence) + repr(bundle)
    for secret in (
        "UNIQUE_PREPARE_INPUT_SECRET_z0",
        "UNIQUE_PREPARE_SECRET_a1",
        "UNIQUE_DX_SECRET_b2",
        "UNIQUE_COLLECTOR_SECRET_c3",
        "UNIQUE_SNAPSHOT_SECRET_d4",
        "UNIQUE_TURNSTILE_SECRET_e5",
        "UNIQUE_REQUIREMENTS_SECRET_f6",
        "UNIQUE_PROOF_SECRET_g7",
    ):
        assert secret not in rendered
