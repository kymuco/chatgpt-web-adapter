from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import post_delegation_reconciliation_live_gate as subject
from chatgpt_web_adapter.browser_owned_write_runtime import (
    WRITE_SUBMITTED_GENERATION_INCOMPLETE,
    BrowserOwnedWriteRuntimeError,
)


class _Provider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None):
        self.payloads.append(dict(payload))
        return {"ok": False}


class _Runtime:
    def __init__(self, *, double_probe_turn: bool = False) -> None:
        self.write_transport = SimpleNamespace(provider=_Provider())
        self.calls = 0
        self.double_probe_turn = double_probe_turn

    def send_text_observed(self, text, *, conversation=None, timeout=150.0):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                response=SimpleNamespace(
                    text=subject.SEED_EXPECTED,
                    conversation=SimpleNamespace(
                        conversation_id="conversation-1",
                        message_id="assistant-seed",
                    ),
                ),
                observation=SimpleNamespace(runtime_tab_id=41),
            )

        provider = self.write_transport.provider
        provider._rpc(
            {
                "type": "turn",
                "request_id": "probe-1",
                "conversationId": conversation,
                "text": text,
            },
            timeout=timeout,
        )
        if self.double_probe_turn:
            provider._rpc(
                {
                    "type": "turn",
                    "request_id": "probe-2",
                    "conversationId": conversation,
                    "text": text,
                },
                timeout=timeout,
            )

        raise BrowserOwnedWriteRuntimeError(
            "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED",
            failure_kind=WRITE_SUBMITTED_GENERATION_INCOMPLETE,
            automatic_retry_allowed=False,
            manual_retry_safe_after_repair=False,
            write_may_have_been_submitted=True,
            reconciliation_required=True,
            request_stage="browser_owned_write_readback",
            conversation_id="conversation-1",
            post_delegation_outcome="SUBMITTED_GENERATION_INCOMPLETE",
            post_delegation_reconciliation={
                "outcome": "SUBMITTED_GENERATION_INCOMPLETE",
                "canonical_read_performed": True,
                "canonical_read_complete": True,
                "conversation_id": "conversation-1",
                "user_message_id": "user-probe",
                "user_turn_persisted": True,
                "canonical_status": "user_last_message",
            },
            post_delegation_runtime_tab_id=41,
            post_delegation_abort_probe_triggered=True,
        )


def _deployment_status() -> dict[str, object]:
    revision = "a" * 40
    return {
        "healthy": True,
        "source_revision": revision,
        "deployment": {"source_revision": revision},
        "extension_digest_matches": True,
        "host_matches_current_environment": True,
        "installed_extension_digest": "digest",
        "installed_extension_dir": "extension",
        "current_host_executable": "native-host",
    }


def test_live_gate_proves_precise_submitted_outcome_without_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime()
    monkeypatch.setattr(
        subject,
        "browser_native_deployment_status",
        _deployment_status,
    )
    monkeypatch.setattr(
        subject,
        "assemble_product_runtime",
        lambda **kwargs: runtime,
    )

    report = subject.run_live_gate(auth_file="auth.json", timeout=30.0)

    assert report["ok"] is True
    assert report["product_write_budget"] == 2
    assert report["product_write_attempts"] == 2
    assert report["probe"]["failure_kind"] == WRITE_SUBMITTED_GENERATION_INCOMPLETE
    assert report["probe"]["abort_probe_triggered"] is True
    assert report["probe"]["automatic_retry_allowed"] is False
    assert report["probe"]["reconciliation"]["user_turn_persisted"] is True
    assert len(runtime.write_transport.provider.payloads) == 1
    assert runtime.write_transport.provider.payloads[0]["postDelegationAbortProbe"] is True


def test_live_gate_blocks_second_probe_turn_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime(double_probe_turn=True)
    monkeypatch.setattr(
        subject,
        "browser_native_deployment_status",
        _deployment_status,
    )
    monkeypatch.setattr(
        subject,
        "assemble_product_runtime",
        lambda **kwargs: runtime,
    )

    with pytest.raises(RuntimeError, match="PR14_9_LIVE_GATE_SECOND_TURN_FORBIDDEN"):
        subject.run_live_gate(auth_file="auth.json", timeout=30.0)

    assert len(runtime.write_transport.provider.payloads) == 1
