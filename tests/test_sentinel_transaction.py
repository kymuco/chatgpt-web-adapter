from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.sentinel_transaction import (
    FinalizedSentinelBundle,
    acquire_finalized_sentinel_bundle,
)


class TransactionClient:
    def __init__(self) -> None:
        self.auth = SimpleNamespace(proof_token=None, turnstile_token="secret-turnstile")
        self.debug_trace_dir = object()
        self.calls: list[str] = []
        self.events: list[dict] = []
        self.traces: list[tuple[str, dict]] = []
        self.finalize_payload = None
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


def test_two_phase_finalize_builds_one_secret_free_bundle() -> None:
    client = TransactionClient()
    bundle = acquire_finalized_sentinel_bundle(client)

    assert client.calls == ["prepare", "finalize"]
    assert client.finalize_payload == {
        "prepare_token": "secret-prepare-token",
        "proofofwork": "secret-proof",
        "turnstile": "secret-turnstile",
    }
    assert "so" not in client.finalize_payload
    assert client.auth.turnstile_token is None
    assert bundle.requirements_token == "secret-requirements"
    assert bundle.proof_token == "secret-proof"
    assert bundle.turnstile_token == "secret-turnstile"
    assert bundle.expires_monotonic > bundle.acquired_monotonic

    rendered = repr(bundle) + repr(client.traces) + repr(client.events)
    for secret in (
        "secret-prepare-token",
        "secret-turnstile-dx",
        "secret-pow-seed",
        "secret-collector-dx",
        "secret-snapshot-dx",
        "secret-requirements",
        "secret-proof",
        "secret-turnstile",
    ):
        assert secret not in rendered
    assert {kind for kind, _payload in client.traces} == {
        "sentinel-prepare-live",
        "sentinel-finalize",
    }


def test_turnstile_evidence_is_required_before_finalize() -> None:
    client = TransactionClient()
    client.auth.turnstile_token = None
    with pytest.raises(
        RequestError,
        match="SENTINEL_TURNSTILE_EVIDENCE_REQUIRED",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_turnstile_gate"
    assert client.calls == ["prepare"]


@pytest.mark.parametrize("block", ["turnstile", "proofofwork"])
def test_unobserved_required_false_policy_fails_closed(block: str) -> None:
    client = TransactionClient()
    client.prepare_response[block]["required"] = False
    with pytest.raises(
        RequestError,
        match="SENTINEL_FINALIZE_POLICY_UNOBSERVED",
    ) as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize_policy"
    assert client.calls == ["prepare"]
    assert client.auth.turnstile_token == "secret-turnstile"


def test_finalize_failure_never_restores_one_shot_turnstile() -> None:
    client = TransactionClient()
    client.finalize_status = 403
    client.finalize_response = {"detail": "rejected"}
    with pytest.raises(RequestError, match="Sentinel finalize rejected") as captured:
        acquire_finalized_sentinel_bundle(client)
    assert captured.value.request_stage == "sentinel_finalize"
    assert client.calls == ["prepare", "finalize"]
    assert client.auth.turnstile_token is None


def test_bundle_credentials_do_not_participate_in_repr_or_equality() -> None:
    requirements = "UNIQUE_REQUIREMENTS_SECRET_9f47"
    proof = "UNIQUE_PROOF_SECRET_2a81"
    turnstile = "UNIQUE_TURNSTILE_SECRET_6c35"
    first = FinalizedSentinelBundle(requirements, proof, turnstile, 1.0, 2.0)
    second = FinalizedSentinelBundle(requirements, proof, turnstile, 1.0, 2.0)
    assert first is not second
    assert first != second
    rendered = repr(first)
    assert requirements not in rendered
    assert proof not in rendered
    assert turnstile not in rendered
