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
        raise AssertionError(
            "low-level provider should be called through send_browser_native"
        )


class FakeClient:
    def __init__(self, status="completed"):
        self.status_value = status
        self.status_values = list(status) if isinstance(status, (list, tuple)) else None
        self._browser_native_turn_provider = None

    def get_status(self, conversation):
        value = (
            self.status_values.pop(0)
            if self.status_values is not None and self.status_values
            else self.status_value
        )
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
    monkeypatch.setattr(
        subject, "send_browser_native", lambda *a, **k: calls.append((a, k))
    )
    rt = runtime(connected=False)
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello")
    error = caught.value
    assert calls == []
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is True
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False


def test_continuation_commit_point_recheck_blocks_completed_to_running_race(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        subject, "send_browser_native", lambda *a, **k: calls.append((a, k))
    )
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


def test_delegated_abort_with_exact_request_identity_classifies_persisted_user(
    monkeypatch,
) -> None:
    calls = 0
    reconciliations = []

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        error = subject.RequestError(
            "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED"
        )
        error.post_delegation_request_correlation_proven = True
        error.post_delegation_user_message_id = "user-message-1"
        error.post_delegation_conversation_id = "conversation-1"
        error.post_delegation_runtime_tab_id = 42
        error.post_delegation_recovery_continuation_observed = True
        error.post_delegation_observer_failure_probe_triggered = True
        raise error

    class Reconciliation:
        outcome = subject.POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE
        canonical_read_performed = False

        @staticmethod
        def to_dict():
            return {
                "outcome": subject.POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE,
                "canonical_read_performed": False,
                "canonical_read_complete": True,
                "conversation_id": "conversation-1",
                "user_message_id": "user-message-1",
                "user_turn_persisted": True,
                "canonical_status": "user_last_message",
            }

    def reconcile(client, *, conversation_id, user_message_id):
        reconciliations.append((client, conversation_id, user_message_id))
        return Reconciliation()

    monkeypatch.setattr(subject, "send_browser_native", fail)
    monkeypatch.setattr(subject, "reconcile_post_delegation_failure", reconcile)

    rt = runtime()
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello", conversation="conversation-1")

    assert calls == 1
    assert len(reconciliations) == 1
    assert reconciliations[0][1:] == ("conversation-1", "user-message-1")
    error = caught.value
    assert error.failure_kind == subject.WRITE_SUBMITTED_GENERATION_INCOMPLETE
    assert (
        error.post_delegation_outcome
        == subject.POST_DELEGATION_SUBMITTED_GENERATION_INCOMPLETE
    )
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is False
    assert error.turn_lifecycle.state.value == "READBACK_INCOMPLETE"
    payload = error.to_dict()
    assert payload["post_delegation_reconciliation"]["user_turn_persisted"] is True
    assert payload["post_delegation_runtime_tab_id"] == 42
    assert payload["post_delegation_recovery_continuation_observed"] is True
    assert payload["post_delegation_observer_failure_probe_triggered"] is True


def test_delegated_abort_conversation_mismatch_stays_unknown(
    monkeypatch,
) -> None:
    calls = 0
    reconciliations = []

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        error = subject.RequestError(
            "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED"
        )
        error.post_delegation_request_correlation_proven = True
        error.post_delegation_user_message_id = "user-message-1"
        error.post_delegation_conversation_id = "different-conversation"
        error.post_delegation_runtime_tab_id = 42
        raise error

    def reconcile(*args, **kwargs):
        reconciliations.append((args, kwargs))
        raise AssertionError("mismatched identity must not enter reconciliation")

    monkeypatch.setattr(subject, "send_browser_native", fail)
    monkeypatch.setattr(subject, "reconcile_post_delegation_failure", reconcile)

    rt = runtime()
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello", conversation="conversation-1")

    assert calls == 1
    assert reconciliations == []
    error = caught.value
    assert error.failure_kind == subject.WRITE_OUTCOME_UNKNOWN
    assert error.post_delegation_outcome is None
    assert error.reconciliation_required is True
    assert error.automatic_retry_allowed is False
    assert error.turn_lifecycle.state.value == "AMBIGUOUS"


def test_delegated_abort_with_canonical_terminal_assistant_finalizes_logical_turn(
    monkeypatch,
) -> None:
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        error = subject.RequestError(
            "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED"
        )
        error.post_delegation_request_correlation_proven = True
        error.post_delegation_user_message_id = "user-message-1"
        error.post_delegation_conversation_id = "conversation-1"
        error.post_delegation_runtime_tab_id = 42
        raise error

    class Reconciliation:
        outcome = subject.POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT
        canonical_read_performed = False

        @staticmethod
        def to_dict():
            return {
                "outcome": subject.POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT,
                "canonical_read_performed": False,
                "canonical_read_complete": True,
                "conversation_id": "conversation-1",
                "user_message_id": "user-message-1",
                "user_turn_persisted": True,
                "canonical_status": "completed",
                "terminal_assistant_message_id": "assistant-message-1",
            }

    monkeypatch.setattr(subject, "send_browser_native", fail)
    monkeypatch.setattr(
        subject,
        "reconcile_post_delegation_failure",
        lambda *args, **kwargs: Reconciliation(),
    )

    rt = runtime()
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("hello", conversation="conversation-1")

    assert calls == 1
    error = caught.value
    assert error.failure_kind == subject.WRITE_SUBMITTED_TERMINAL_ASSISTANT
    assert (
        error.post_delegation_outcome
        == subject.POST_DELEGATION_SUBMITTED_TERMINAL_ASSISTANT
    )
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is False
    assert error.automatic_retry_allowed is False
    assert error.manual_retry_safe_after_repair is False
    assert error.turn_lifecycle.state.value == "FINALIZED"


def _aborted_rich_new_chat_snapshot(*, terminal: bool, user_id: str = "user-rich-1"):
    from chatgpt_web_adapter.canonical_conversation_snapshot import (
        canonical_snapshot_from_payload,
    )

    mapping = {
        "root": {
            "id": "root",
            "parent": None,
            "children": ["user-node"],
            "message": None,
        },
        "user-node": {
            "id": "user-node",
            "parent": "root",
            "children": ["assistant-node"] if terminal else [],
            "message": {
                "id": user_id,
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["prompt"]},
                "metadata": {},
            },
        },
    }
    if terminal:
        mapping["assistant-node"] = {
            "id": "assistant-node",
            "parent": "user-node",
            "children": [],
            "message": {
                "id": "assistant-rich-1",
                "author": {"role": "assistant"},
                "content": {"content_type": "text", "parts": ["canonical answer"]},
                "metadata": {"finish_details": {"type": "stop"}},
            },
        }
    return canonical_snapshot_from_payload(
        "rich-conversation-1",
        {
            "conversation_id": "rich-conversation-1",
            "current_node": "assistant-node" if terminal else "user-node",
            "mapping": mapping,
        },
    )


def _aborted_rich_new_chat_error(*, route_candidate: bool = True):
    error = subject.RequestError(
        "PR9_2_DOWNSTREAM_FAILED_AND_ATTACHMENT_CLEANUP_UNPROVEN:"
        "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED"
    )
    error.post_delegation_request_correlation_proven = True
    error.post_delegation_user_message_id = "user-rich-1"
    error.post_delegation_conversation_id = "rich-conversation-1"
    error.post_delegation_runtime_tab_id = 73
    error.post_delegation_new_chat_route_candidate_only = route_candidate
    return error


@pytest.mark.parametrize(
    ("terminal", "snapshot_user_id", "expected_outcome"),
    [
        (True, "user-rich-1", "success"),
        (False, "user-rich-1", subject.WRITE_SUBMITTED_GENERATION_INCOMPLETE),
        (True, "unrelated-user", subject.WRITE_OUTCOME_UNKNOWN),
    ],
)
def test_aborted_rich_new_chat_requires_exact_canonical_proof_before_success(
    monkeypatch, terminal, snapshot_user_id, expected_outcome
) -> None:
    class SnapshotClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def get_conversation_snapshot(self, conversation):
            assert conversation == "rich-conversation-1"
            self.reads += 1
            return _aborted_rich_new_chat_snapshot(
                terminal=terminal, user_id=snapshot_user_id
            )

    calls = []

    def failed_send(*args, **kwargs):
        calls.append(1)
        raise _aborted_rich_new_chat_error()

    monkeypatch.setattr(subject, "send_browser_native", failed_send)
    client = SnapshotClient()
    rt = subject.BrowserOwnedProductWriteRuntime(client, provider=FakeProvider())
    events = []

    if expected_outcome == "success":
        response = rt.send_text("prompt", on_event=events.append)
        assert response.text == "canonical answer"
        assert response.conversation.conversation_id == "rich-conversation-1"
        assert response.conversation.message_id == "assistant-rich-1"
        assert [event["type"] for event in events] == [
            "browser_native_write_completed",
            "browser_native_readback_completed",
        ]
        assert rt.lifecycle_snapshot()["turn_lifecycle"]["state"] == "FINALIZED"
    else:
        with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
            rt.send_text("prompt", on_event=events.append)
        assert caught.value.failure_kind == expected_outcome
        assert caught.value.automatic_retry_allowed is False
        assert events == []

    assert calls == [1]
    assert client.reads == 1


def test_aborted_rich_new_chat_without_candidate_never_enters_readback(monkeypatch):
    class SnapshotClient(FakeClient):
        def get_conversation_snapshot(self, conversation):
            raise AssertionError("untrusted route must not authorize readback")

    def failed_send(*args, **kwargs):
        raise _aborted_rich_new_chat_error(route_candidate=False)

    monkeypatch.setattr(subject, "send_browser_native", failed_send)
    rt = subject.BrowserOwnedProductWriteRuntime(
        SnapshotClient(), provider=FakeProvider()
    )
    with pytest.raises(subject.BrowserOwnedWriteRuntimeError) as caught:
        rt.send_text("prompt")
    assert caught.value.failure_kind == subject.WRITE_OUTCOME_UNKNOWN
    assert caught.value.automatic_retry_allowed is False
