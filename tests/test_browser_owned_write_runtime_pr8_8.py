from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_owned_write_runtime as subject
from chatgpt_web_adapter.browser_authority_lease import (
    BrowserAuthorityLeaseState,
    BrowserAuthorityPolicy,
    TurnLifecycleState,
)


class FakeProvider:
    def __init__(self, statuses=None):
        self.statuses = list(statuses or [
            subject.BrowserNativeBridgeStatus(True, True, runtime_tab_id=41)
        ])
        self.last = self.statuses[-1]
        self.bound = None
        self.releases = []

    def status(self):
        if self.statuses:
            self.last = self.statuses.pop(0)
        return self.last

    def set_browser_authority_lease(self, lease_id):
        self.bound = lease_id

    def clear_browser_authority_lease(self):
        self.bound = None

    def release_runtime_tab(
        self,
        *,
        expected_runtime_tab_id,
        browser_authority_lease_id,
        timeout,
    ):
        self.releases.append(
            (expected_runtime_tab_id, browser_authority_lease_id, timeout)
        )
        return SimpleNamespace(
            released=True,
            already_absent=False,
            runtime_tab_id=expected_runtime_tab_id,
        )


class FakeClient:
    def __init__(self):
        self._browser_native_turn_provider = None

    def get_status(self, conversation):
        return SimpleNamespace(status="completed")


def runtime(provider=None, **kwargs):
    return subject.BrowserOwnedProductWriteRuntime(
        FakeClient(),
        provider=provider or FakeProvider(),
        **kwargs,
    )


def fake_success(subject_module, monkeypatch, *, emit_write=True):
    result = SimpleNamespace(text="ok")

    def fake_send(client, text, **kwargs):
        callback = kwargs.get("on_event")
        if emit_write and callback:
            callback(
                {
                    "type": "browser_native_write_completed",
                    "runtime_tab_id": 41,
                    "runtime_tab_preexisting": True,
                    "foreground_activation_observed": False,
                }
            )
        if callback:
            callback(
                {
                    "type": "browser_native_readback_completed",
                    "conversation_id": "c1",
                    "message_id": "m1",
                }
            )
        return result

    monkeypatch.setattr(subject_module, "send_browser_native", fake_send)
    return result


def test_default_persistent_releases_lease_but_never_closes_tab(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    fake_success(subject, monkeypatch)

    rt.send_text("hello")
    snapshot = rt.lifecycle_snapshot()

    assert snapshot["browser_authority_lease"]["state"] == "RELEASED"
    assert snapshot["browser_authority_lease"]["policy"] == "PERSISTENT"
    assert snapshot["browser_authority_lease"]["disposal_due_at_ms"] is None
    assert snapshot["turn_lifecycle"]["state"] == "FINALIZED"
    assert snapshot["pending_disposal"] is False
    assert provider.releases == []


def test_write_event_releases_browser_authority_before_turn_finality(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    states = []
    result = SimpleNamespace(text="ok")

    def fake_send(client, text, **kwargs):
        callback = kwargs["on_event"]
        callback({"type": "browser_native_write_completed", "runtime_tab_id": 41})
        states.append(rt.lifecycle_snapshot())
        callback({"type": "browser_native_readback_completed"})
        return result

    monkeypatch.setattr(subject, "send_browser_native", fake_send)
    assert rt.send_text("hello") is result

    middle = states[0]
    assert middle["browser_authority_lease"]["state"] == "RELEASED"
    assert middle["turn_lifecycle"]["state"] == "WRITE_COMPLETED"
    assert middle["turn_lifecycle"]["logical_turn_terminal"] is False
    assert rt.lifecycle_snapshot()["turn_lifecycle"]["state"] == "FINALIZED"


def test_turn_scoped_zero_ttl_closes_only_after_release(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    fake_success(subject, monkeypatch)

    rt.send_text(
        "hello",
        browser_authority_policy="TURN_SCOPED",
        browser_authority_ttl_ms=0,
    )
    deadline = time.time() + 1.0
    while time.time() < deadline and not provider.releases:
        time.sleep(0.01)

    assert len(provider.releases) == 1
    assert provider.releases[0][0] == 41
    assert isinstance(provider.releases[0][1], str)
    assert rt.lifecycle_snapshot()["last_disposal_result"]["status"] == "CLOSED"


def test_new_generation_cancels_stale_idle_ttl_close(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    fake_success(subject, monkeypatch)

    rt.send_text(
        "first",
        browser_authority_policy="IDLE_TTL",
        browser_authority_ttl_ms=200,
    )
    first = rt.lifecycle_snapshot()["browser_authority_lease"]
    assert first["disposal_due_at_ms"] is not None

    rt.send_text("second", browser_authority_policy="PERSISTENT")
    time.sleep(0.3)

    assert provider.releases == []
    assert rt.lifecycle_snapshot()["browser_authority_lease"]["policy"] == "PERSISTENT"


def test_fresh_browser_authority_loss_blocks_before_delegation(monkeypatch):
    provider = FakeProvider(
        statuses=[
            subject.BrowserNativeBridgeStatus(True, True, runtime_tab_id=41),
            subject.BrowserNativeBridgeStatus(False, False, runtime_tab_id=None),
        ]
    )
    delegated = []
    monkeypatch.setattr(
        subject,
        "send_browser_native",
        lambda *a, **k: delegated.append((a, k)),
    )
    rt = runtime(provider)

    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello")

    assert caught.value.failure_kind == subject.BRIDGE_UNAVAILABLE
    assert caught.value.write_may_have_been_submitted is False
    assert delegated == []
    assert rt.lifecycle_snapshot()["browser_authority_lease"] is None


def test_success_without_write_release_event_never_starts_ttl(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    fake_success(subject, monkeypatch, emit_write=False)

    rt.send_text(
        "hello",
        browser_authority_policy="TURN_SCOPED",
        browser_authority_ttl_ms=0,
    )
    time.sleep(0.05)
    snapshot = rt.lifecycle_snapshot()

    assert snapshot["browser_authority_lease"]["state"] == "RELEASE_UNKNOWN"
    assert snapshot["browser_authority_lease"]["disposal_due_at_ms"] is None
    assert provider.releases == []


def test_readback_timeout_after_release_keeps_turn_reconciliation_state(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)

    def fail(client, text, **kwargs):
        callback = kwargs["on_event"]
        callback({"type": "browser_native_write_completed", "runtime_tab_id": 41})
        raise subject.ConversationTimeoutError("readback timeout", timeout=5)

    monkeypatch.setattr(subject, "send_browser_native", fail)

    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello")

    error = caught.value
    assert error.failure_kind == subject.WRITE_ACCEPTED_READBACK_INCOMPLETE
    assert error.browser_authority_lease.state is BrowserAuthorityLeaseState.RELEASED
    assert error.turn_lifecycle.state is TurnLifecycleState.READBACK_INCOMPLETE
    assert error.reconciliation_required is True


def test_delegated_ambiguous_error_never_disposes_without_release_proof(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)

    def fail(*args, **kwargs):
        raise subject.RequestError("bridge race")

    monkeypatch.setattr(subject, "send_browser_native", fail)

    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text(
            "hello",
            browser_authority_policy="TURN_SCOPED",
            browser_authority_ttl_ms=0,
        )

    error = caught.value
    assert error.browser_authority_lease.state is BrowserAuthorityLeaseState.RELEASE_UNKNOWN
    assert error.turn_lifecycle.state is TurnLifecycleState.AMBIGUOUS
    assert provider.releases == []


def test_observed_execution_exposes_lease_and_turn_metadata(monkeypatch):
    provider = FakeProvider()
    rt = runtime(provider)
    fake_success(subject, monkeypatch)

    execution = rt.send_text_observed("hello")
    obs = execution.observation
    assert obs.write_event_observed is True
    assert obs.browser_authority_policy == "PERSISTENT"
    assert obs.browser_authority_release_proven is True
    assert obs.turn_lifecycle_state_at_write == "WRITE_COMPLETED"
    assert obs.browser_authority_lease_id


def test_governance_declares_pr88_lease_invariants():
    policy = runtime().governance()
    assert policy["browser_authority_lease_distinct_from_turn_lifecycle"] is True
    assert policy["browser_authority_default_policy"] == "PERSISTENT"
    assert policy["browser_authority_ttl_starts_after_release"] is True
    assert policy["browser_authority_disposal_action_v1"] == "CLOSE"
    assert policy["browser_authority_disposal_requires_release_proof"] is True
    assert policy["turn_scoped_zero_ttl_allowed"] is True


def test_nonpersistent_policy_requires_release_and_fencing_before_any_lease(monkeypatch):
    class NoReleaseProvider:
        def status(self):
            return subject.BrowserNativeBridgeStatus(True, True, runtime_tab_id=41)

    delegated = []
    monkeypatch.setattr(subject, "send_browser_native", lambda *a, **k: delegated.append((a, k)))
    rt = subject.BrowserOwnedProductWriteRuntime(FakeClient(), provider=NoReleaseProvider())

    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello", browser_authority_policy="TURN_SCOPED")

    assert caught.value.failure_kind == subject.BROWSER_AUTHORITY_RELEASE_UNSUPPORTED
    assert caught.value.write_may_have_been_submitted is False
    assert delegated == []
    assert rt.lifecycle_snapshot()["browser_authority_lease"] is None
