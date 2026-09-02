from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_owned_submission_lifecycle as lifecycle_subject
from chatgpt_web_adapter.browser_native_client import BrowserNativeSubmission
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.browser_owned_submission_lifecycle import (
    SUBMISSION_FINALITY_PENDING,
    SUBMISSION_HANDLE_INVALID,
)
from chatgpt_web_adapter.browser_owned_write_runtime import BrowserOwnedWriteRuntimeError
from chatgpt_web_adapter.product_submission import (
    ProductSubmissionAck,
    SubmissionEvidenceSource,
)
from chatgpt_web_adapter.product_submission_runtime_gate import (
    ProductSubmissionLifecycleUnavailableError,
)
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.revision_safe_streaming_pr8_9 import RevisionSafeTextAccumulator
from chatgpt_web_adapter.types import ChatResponse, ConversationStatus


class FakeClient:
    def __init__(self) -> None:
        self._browser_native_turn_provider = None
        self.readback_ack_count = 0

    def get_status(self, conversation):
        return ConversationStatus(status="completed", message_id="baseline")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        raise AssertionError("canonical attach is replaced by the PR11.4 await stub")

    def complete_canonical_readback(self):
        self.readback_ack_count += 1
        return True


class FakeProvider:
    def __init__(self) -> None:
        self.bound = None
        self.bind_history: list[str | None] = []
        self.status_count = 0
        self.release_calls = []

    def send_text(self, *args, **kwargs):
        raise AssertionError("low-level provider call is replaced by submit_browser_native")

    def status(self):
        self.status_count += 1
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=41,
        )

    def set_browser_authority_lease(self, lease_id):
        self.bound = lease_id
        self.bind_history.append(lease_id)

    def clear_browser_authority_lease(self):
        self.bound = None
        self.bind_history.append(None)

    def release_runtime_tab(
        self,
        *,
        expected_runtime_tab_id,
        browser_authority_lease_id,
        timeout,
    ):
        self.release_calls.append(
            (expected_runtime_tab_id, browser_authority_lease_id, timeout)
        )
        return SimpleNamespace(
            released=True,
            already_absent=False,
            runtime_tab_id=expected_runtime_tab_id,
        )


def _install_split_stubs(monkeypatch, provider: FakeProvider):
    calls = {"submit": 0, "await": 0, "bound_during_await": None}

    def fake_submit(client, text, **kwargs):
        calls["submit"] += 1
        callback = kwargs["on_event"]
        callback(
            {
                "type": "browser_native_write_completed",
                "submission_id": "submission-1",
                "accepted_at_ms": 123456,
                "conversation_id": "conversation-1",
                "turn_exchange_id": "exchange-1",
                "runtime_tab_id": 41,
                "runtime_tab_preexisting": True,
            }
        )
        turn = SimpleNamespace(
            conversation_id="conversation-1",
            turn_exchange_id="exchange-1",
            response_status=200,
            tab_id=41,
        )
        return BrowserNativeSubmission(
            submission_id="submission-1",
            turn=turn,
            baseline_assistant_ids=frozenset(),
            timeout=float(kwargs["timeout"]),
            poll_interval=float(kwargs["poll_interval"]),
            started_monotonic=1.0,
            accepted_at_ms=123456,
            is_continuation=False,
            attachment_count=0,
            stream_state=RevisionSafeTextAccumulator(),
            on_token=kwargs.get("on_token"),
            on_event=callback,
        )

    def fake_await(client, submission):
        calls["await"] += 1
        calls["bound_during_await"] = provider.bound
        submission.on_event(
            {
                "type": "browser_native_readback_completed",
                "submission_id": submission.submission_id,
                "conversation_id": "conversation-1",
                "message_id": "assistant-1",
                "canonical_finality_proven": True,
            }
        )
        return ChatResponse(text="done")

    monkeypatch.setattr(lifecycle_subject, "submit_browser_native", fake_submit)
    monkeypatch.setattr(lifecycle_subject, "await_browser_native_final", fake_await)
    return calls


def _runtime(monkeypatch):
    client = FakeClient()
    provider = FakeProvider()
    calls = _install_split_stubs(monkeypatch, provider)
    transport = BrowserOwnedProductTransport(client, provider=provider)
    runtime = ChatGPTProductRuntime(
        client,
        transport="browser-owned",
        write_transport=transport,
    )
    return runtime, transport, client, provider, calls


def test_submit_ack_is_write_acceptance_not_canonical_finality(monkeypatch):
    runtime, transport, client, provider, calls = _runtime(monkeypatch)

    ack = runtime.submit("hello")

    assert isinstance(ack, ProductSubmissionAck)
    assert ack.submission_id == "submission-1"
    assert ack.conversation_id == "conversation-1"
    assert ack.turn_exchange_id == "exchange-1"
    assert ack.write_may_have_committed is True
    assert ack.automatic_retry_allowed is False
    assert ack.canonical_finality_proven is False
    assert ack.provenance.write_acknowledged is True
    assert ack.provenance.canonical_finality_proven is False
    assert ack.provenance.automatic_write_retry is False
    assert ack.provenance.fallback_transport is None
    assert (
        ack.provenance.evidence_source
        is SubmissionEvidenceSource.BROWSER_NATIVE_WRITE_COMPLETED
    )
    assert calls == {"submit": 1, "await": 0, "bound_during_await": None}
    assert provider.bound is None
    assert client.readback_ack_count == 0

    snapshot = runtime.submission_lifecycle_snapshot()
    assert snapshot["supported"] is True
    assert snapshot["pending"] is True
    assert snapshot["submission_id"] == ack.submission_id
    assert snapshot["turn_lifecycle_state"] == "WRITE_COMPLETED"
    assert snapshot["browser_authority_state"] == "ACTIVE"
    assert snapshot["canonical_finality_proven"] is False

    governance = transport.governance()
    assert governance["submission_ack_is_canonical_finality"] is False
    assert governance["submission_pending_limit"] == 1
    assert governance["submission_pending_blocks_new_write"] is True
    assert governance["submission_dispatch_serialized"] is True
    assert governance["submission_await_serialized"] is True
    assert governance["submission_automatic_write_retry"] is False


def test_pending_submission_blocks_every_second_write_before_delegation(monkeypatch):
    runtime, transport, _client, _provider, calls = _runtime(monkeypatch)
    ack = runtime.submit("first")

    with pytest.raises(BrowserOwnedWriteRuntimeError) as caught:
        runtime.submit("second")
    assert caught.value.failure_kind == SUBMISSION_FINALITY_PENDING
    assert caught.value.write_may_have_been_submitted is False

    with pytest.raises(BrowserOwnedWriteRuntimeError) as caught_send:
        runtime.send("compatibility send")
    assert caught_send.value.failure_kind == SUBMISSION_FINALITY_PENDING

    with pytest.raises(BrowserOwnedWriteRuntimeError) as caught_temporary:
        transport.send_text("temporary", conversation_mode="temporary")
    assert caught_temporary.value.failure_kind == SUBMISSION_FINALITY_PENDING

    assert calls["submit"] == 1
    assert runtime.submission_lifecycle_snapshot()["submission_id"] == ack.submission_id


def test_await_final_rebinds_same_authority_then_releases_slot(monkeypatch):
    runtime, _transport, client, provider, calls = _runtime(monkeypatch)
    ack = runtime.submit("hello")
    lease_id = ack.turn_lifecycle_id

    response = runtime.await_final(ack)

    assert response.text == "done"
    assert calls["await"] == 1
    assert isinstance(calls["bound_during_await"], str)
    assert calls["bound_during_await"]
    assert provider.bound is None
    assert client.readback_ack_count == 1
    assert runtime.submission_lifecycle_snapshot()["pending"] is False

    lifecycle = runtime.write_transport._runtime.lifecycle_snapshot()
    assert lifecycle["turn_lifecycle"]["state"] == "FINALIZED"
    assert lifecycle["browser_authority_lease"]["state"] == "RELEASED"
    assert lifecycle["browser_authority_lease"]["authority_release_proven"] is True
    assert lifecycle["turn_lifecycle"]["lifecycle_id"] == lease_id

    second = runtime.submit("second")
    assert second.submission_id == "submission-1"
    assert calls["submit"] == 2


def test_foreign_submission_handle_fails_without_consuming_pending(monkeypatch):
    runtime, _transport, _client, _provider, calls = _runtime(monkeypatch)
    ack = runtime.submit("hello")
    foreign = ProductSubmissionAck(
        submission_id="foreign-submission",
        transport=ack.transport,
        conversation_id=ack.conversation_id,
        turn_exchange_id=ack.turn_exchange_id,
        accepted_at_ms=ack.accepted_at_ms,
        turn_lifecycle_id=ack.turn_lifecycle_id,
        write_may_have_committed=True,
        automatic_retry_allowed=False,
        canonical_finality_proven=False,
        provenance=ack.provenance,
    )

    with pytest.raises(BrowserOwnedWriteRuntimeError) as caught:
        runtime.await_final(foreign)

    assert caught.value.failure_kind == SUBMISSION_HANDLE_INVALID
    assert calls["await"] == 0
    assert runtime.submission_lifecycle_snapshot()["submission_id"] == ack.submission_id


class UnsupportedTransport:
    transport_id = "browserless-request"

    def __init__(self) -> None:
        self.write_calls = 0

    def health(self, conversation=None):
        return None

    def capabilities(self):
        return None

    def send_text(self, text, **kwargs):
        self.write_calls += 1
        return ChatResponse(text="unexpected")

    def send_text_observed(self, text, **kwargs):
        self.write_calls += 1
        raise AssertionError("unexpected write")

    def governance(self):
        return {
            "fallback_transport": None,
            "legacy_direct_write_fallback": False,
            "submission_lifecycle_supported": False,
        }


def test_unsupported_transport_fails_split_lifecycle_before_write():
    client = FakeClient()
    writer = UnsupportedTransport()
    runtime = ChatGPTProductRuntime(
        client,
        transport="browserless-request",
        write_transport=writer,
    )

    with pytest.raises(ProductSubmissionLifecycleUnavailableError) as caught:
        runtime.submit("hello")

    assert caught.value.transport == "browserless-request"
    assert writer.write_calls == 0


def test_temporary_split_lifecycle_fails_before_browser_write(monkeypatch):
    runtime, _transport, _client, _provider, calls = _runtime(monkeypatch)

    with pytest.raises(ProductSubmissionLifecycleUnavailableError):
        runtime.submit("hello", conversation_mode="temporary")

    assert calls["submit"] == 0
