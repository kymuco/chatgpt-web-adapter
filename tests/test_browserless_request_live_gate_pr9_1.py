from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter.browserless_request_live_gate_pr9_1 as live_gate
from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessChallengeBoundaryError,
    BrowserlessProtocolDriftError,
    BrowserlessRequestTransportError,
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


def _install_runtime(monkeypatch, runtime: _Runtime) -> None:
    monkeypatch.setattr(live_gate, "assemble_product_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(live_gate, "product_runtime_contract", lambda runtime: _Contract())


def test_live_gate_accepts_challenge_boundary_as_safe_prewrite_observation(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessChallengeBoundaryError(("turnstile", "proofofwork"))
        )
    )
    _install_runtime(monkeypatch, runtime)

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is True
    assert report["outcome"] == "CHALLENGE_BOUNDARY"
    assert report["product_turn_invocations"] == 1
    assert report["conversation_write_attempts"] == 0
    assert report["conversation_write_completions"] == 0
    assert report["automatic_write_retry"] is False
    assert report["fallback_transport"] is None
    assert report["boundary"]["challenge_bypass_attempted"] is False
    assert runtime.calls == 1


def test_live_gate_reports_protocol_drift_as_zero_write_attempts(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessProtocolDriftError("shape changed")
        )
    )
    _install_runtime(monkeypatch, runtime)

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is False
    assert report["outcome"] == "PROTOCOL_DRIFT"
    assert report["product_turn_invocations"] == 1
    assert report["conversation_write_attempts"] == 0
    assert runtime.calls == 1


def test_live_gate_prewrite_transport_failure_is_zero_write_attempts(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessRequestTransportError(
                "prepare failed",
                request_stage="conversation_prepare",
                write_may_have_been_submitted=False,
                reconciliation_required=False,
            )
        )
    )
    _install_runtime(monkeypatch, runtime)

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["outcome"] == "DIRECT_REQUEST_FAILED"
    assert report["conversation_write_attempts"] == 0
    assert report["conversation_write_completions"] == 0


def test_live_gate_ambiguous_failure_counts_one_possible_write(monkeypatch) -> None:
    runtime = _Runtime(
        lambda: (_ for _ in ()).throw(
            BrowserlessRequestTransportError(
                "stream disconnected",
                request_stage="conversation_stream",
                write_may_have_been_submitted=True,
                reconciliation_required=True,
            )
        )
    )
    _install_runtime(monkeypatch, runtime)

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["outcome"] == "RECONCILIATION_REQUIRED"
    assert report["conversation_write_attempts"] == 1
    assert report["conversation_write_completions"] == 0


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
    _install_runtime(monkeypatch, runtime)

    report = live_gate.run_live_gate(auth_file="unused.json")

    assert report["ok"] is True
    assert report["outcome"] == "DIRECT_WRITE_COMPLETED"
    assert report["product_turn_invocations"] == 1
    assert report["conversation_write_attempts"] == 1
    assert report["conversation_write_completions"] == 1
    assert report["response_matches"] is True
    assert runtime.calls == 1
