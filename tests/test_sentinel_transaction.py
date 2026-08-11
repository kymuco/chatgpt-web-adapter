from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.sentinel_transaction import (
    FinalizedSentinelBundle,
    SentinelChallengeContext,
    SentinelChallengeEvidence,
    acquire_finalized_sentinel_bundle,
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
            "expire_at": 1_800_000_000,
        }

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
            assert payload == {"p": None}
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
        so_completed: bool = True,
        so_collector_dx: str | None = None,
        so_snapshot_dx: str | None = None,
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
                so_collector_dx=(
                    context.so_collector_dx
                    if so_collector_dx is None
                    else so_collector_dx
                ),
                so_snapshot_dx=(
                    context.so_snapshot_dx
                    if so_snapshot_dx is None
                    else so_snapshot_dx
                ),
                so_completed=so_completed,
            )

        set_sentinel_challenge_provider(self, provider)


def test_two_phase_finalize_uses_current_prepare_provider_bundle_only() -> None:
    client = TransactionClient()
    client.install_current_provider()
    bundle = acquire_finalized_sentinel_bundle(client)

    assert client.calls == ["prepare", "finalize"]
    assert len(client.provider_contexts) == 1
    context = client.provider_contexts[0]
    assert context.prepare_token == "secret-prepare-token"
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


def test_provider_must_complete_required_so_for_current_prepare() -> None:
    client = TransactionClient()
    client.install_current_provider(so_completed=False)
    with pytest.raises(RequestError, match="SENTINEL_SO_CAPABILITY_REQUIRED") as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_so_gate"
    assert client.calls == ["prepare"]


def test_provider_so_descriptor_must_match_current_prepare() -> None:
    client = TransactionClient()
    client.install_current_provider(so_collector_dx="stale-collector")
    with pytest.raises(RequestError, match="SENTINEL_CHALLENGE_BINDING_MISMATCH"):
        acquire_finalized_sentinel_bundle(client)
    assert client.calls == ["prepare"]


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
        "UNIQUE_PREPARE_SECRET_a1",
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
        "UNIQUE_COLLECTOR_SECRET_c3",
        "UNIQUE_SNAPSHOT_SECRET_d4",
        True,
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
        "UNIQUE_PREPARE_SECRET_a1",
        "UNIQUE_DX_SECRET_b2",
        "UNIQUE_COLLECTOR_SECRET_c3",
        "UNIQUE_SNAPSHOT_SECRET_d4",
        "UNIQUE_TURNSTILE_SECRET_e5",
        "UNIQUE_REQUIREMENTS_SECRET_f6",
        "UNIQUE_PROOF_SECRET_g7",
    ):
        assert secret not in rendered