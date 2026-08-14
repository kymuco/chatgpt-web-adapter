from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_owned_write_runtime as subject


class FakeProvider:
    def __init__(self, *, available=True, connected=True, tab_id=None):
        self._status = subject.BrowserNativeBridgeStatus(
            available=available,
            extension_connected=connected,
            runtime_tab_id=tab_id,
        )

    def status(self):
        return self._status

    def send_text(self, *args, **kwargs):
        raise AssertionError("low-level provider should be called through send_browser_native")


class FakeClient:
    def __init__(self, status="completed"):
        self.status_value = status
        self.status_values = list(status) if isinstance(status, (list, tuple)) else None
        self._browser_native_turn_provider = None

    def get_status(self, conversation):
        value = self.status_values.pop(0) if self.status_values is not None and self.status_values else self.status_value
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(status=value)


def runtime(*, available=True, connected=True, tab_id=None, status="completed"):
    return subject.BrowserOwnedProductWriteRuntime(
        FakeClient(status=status),
        provider=FakeProvider(available=available, connected=connected, tab_id=tab_id),
    )


def test_bridge_unavailable_blocks_before_write() -> None:
    health = runtime(available=False).health()
    assert health.ready is False
    assert health.reason == subject.BRIDGE_UNAVAILABLE


def test_extension_disconnected_blocks_before_write() -> None:
    health = runtime(connected=False).health()
    assert health.ready is False
    assert health.reason == subject.EXTENSION_DISCONNECTED


def test_runtime_tab_is_not_required_before_new_chat() -> None:
    health = runtime(tab_id=None).health()
    assert health.ready is True
    assert health.runtime_tab_id is None
    assert health.runtime_tab_preexisting is False


def test_completed_continuation_is_ready() -> None:
    health = runtime(tab_id=17, status="completed").health("conversation-1")
    assert health.ready is True
    assert health.canonical_status == "completed"
    assert health.canonical_read_checked is True


def test_running_continuation_is_blocked() -> None:
    health = runtime(status="running").health("conversation-1")
    assert health.ready is False
    assert health.reason == subject.CONVERSATION_NOT_COMPLETED
    assert health.canonical_status == "running"


def test_unreadable_continuation_is_blocked() -> None:
    health = runtime(status=RuntimeError("network")).health("conversation-1")
    assert health.ready is False
    assert health.reason == subject.CANONICAL_READ_UNAVAILABLE


def test_preflight_failure_never_delegates_write(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(subject, "send_browser_native", lambda *a, **k: calls.append((a, k)))
    rt = runtime(connected=False)
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello")
    error = caught.value
    assert calls == []
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is True
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False



def test_continuation_commit_point_recheck_blocks_completed_to_running_race(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(subject, "send_browser_native", lambda *a, **k: calls.append((a, k)))
    rt = runtime(status=["completed", "running"])
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello", conversation="conversation-1")
    assert calls == []
    assert caught.value.failure_kind == subject.CONVERSATION_NOT_COMPLETED
    assert caught.value.write_may_have_been_submitted is False
    assert caught.value.manual_retry_safe_after_repair is True


def test_success_delegates_exactly_once(monkeypatch) -> None:
    expected = SimpleNamespace(text="ok")
    calls = []

    def fake_send(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr(subject, "send_browser_native", fake_send)
    rt = runtime()
    result = rt.send_text("hello", timeout=12, poll_interval=0.2)
    assert result is expected
    assert len(calls) == 1
    assert calls[0][0][1] == "hello"
    assert calls[0][1]["timeout"] == 12


def test_readback_timeout_is_accepted_but_incomplete(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise subject.ConversationTimeoutError("readback timeout", timeout=5)

    monkeypatch.setattr(subject, "send_browser_native", fail)
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        runtime().send_text("hello")
    error = caught.value
    assert error.failure_kind == subject.WRITE_ACCEPTED_READBACK_INCOMPLETE
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is False
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True


def test_delegated_provider_error_is_never_auto_retried(monkeypatch) -> None:
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise subject.RequestError("bridge race")

    monkeypatch.setattr(subject, "send_browser_native", fail)
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        runtime().send_text("hello")
    assert calls == 1
    error = caught.value
    assert error.failure_kind == subject.WRITE_OUTCOME_UNKNOWN
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is False
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True


def test_governance_keeps_browser_confined_to_write() -> None:
    policy = runtime().governance()
    assert policy["read_plane"] == subject.READ_PLANE
    assert policy["session_plane"] == subject.SESSION_PLANE
    assert policy["write_plane"] == subject.WRITE_PLANE
    assert policy["browser_launch_owned_by_runtime"] is False
    assert policy["runtime_tab_required_before_turn"] is False
    assert policy["automatic_write_retry"] is False
    assert policy["direct_private_product_write"] is False
