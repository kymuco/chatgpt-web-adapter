from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter.browserless_request_live_gate_pr9_1 as live_gate
from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessChallengeBoundaryError,
    BrowserlessProtocolDriftError,
)


class _Capabilities:
    def to_dict(self):
        return {
            "transport": "browserless-request",
            "transport_support_tier": "EXPERIMENTAL",
            "capabilities": {},
        }


class _Contract:
    def to_dict(self):
        return {
            "schema": 1,
            "transport": "browserless-request",
            "transport_support_tier": "EXPERIMENTAL",
        }


class _Runtime:
    transport = "browserless-request"

    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = 0

    def capabilities(self):
        return _Capabilities()

    def send_text_observed(self, *args, **kwargs):
        self.calls += 1
        return self.behavior()


def test_live_gate_accepts_challenge_boundary_as_safe_observation(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessChallengeBoundaryError(("turnstile", "proofofwork"))
        )
    )
    monkeypatch.setattr(live_gate, "assemble_product_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(live_gate, "product_runtime_contract", lambda runtime: _Contract())

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is True
    assert report["outcome"] == "CHALLENGE_BOUNDARY"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 0
    assert report["automatic_write_retry"] is False
    assert report["fallback_transport"] is None
    assert report["boundary"]["challenge_bypass_attempted"] is False
    assert runtime.calls == 1


def test_live_gate_reports_protocol_drift_without_retry(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessProtocolDriftError("shape changed")
        )
    )
    monkeypatch.setattr(live_gate, "assemble_product_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(live_gate, "product_runtime_contract", lambda runtime: _Contract())

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is False
    assert report["outcome"] == "PROTOCOL_DRIFT"
    assert runtime.calls == 1


def test_live_gate_requires_canonical_completion_for_direct_success(monkeypatch) -> None:
    execution = SimpleNamespace(
        response=SimpleNamespace(
            text="CWA_PR9_1_BROWSERLESS_OK",
            conversation=SimpleNamespace(
                conversation_id="conversation-1",
                message_id="assistant-1",
            ),
        ),
        observation=SimpleNamespace(to_dict=lambda: {"canonical_status": "completed"}),
        provenance=SimpleNamespace(
            completion=SimpleNamespace(canonical_completion_proven=True),
            to_dict=lambda: {"completion": {"canonical_completion_proven": True}},
        ),
    )
    runtime = _Runtime(lambda: execution)
    monkeypatch.setattr(live_gate, "assemble_product_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(live_gate, "product_runtime_contract", lambda runtime: _Contract())

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is True
    assert report["outcome"] == "DIRECT_WRITE_COMPLETED"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 1
    assert report["response_matches"] is True
    assert runtime.calls == 1
