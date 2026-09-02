from __future__ import annotations

import threading
from types import SimpleNamespace

from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import ORDINARY_CHATGPT_PRODUCT_SEMANTICS
from chatgpt_web_adapter.product_submission import (
    ProductSubmissionAck,
    ProductSubmissionProvenance,
    SubmissionEvidenceSource,
)
from chatgpt_web_adapter.types import ChatResponse


class _BlockingSubmitLifecycle:
    def __init__(self) -> None:
        self.submit_entered = threading.Event()
        self.allow_submit_return = threading.Event()
        self.pending = False

    def ensure_no_pending_submission(self) -> None:
        if self.pending:
            raise RuntimeError("pending split submission")

    def submit_text(self, text, **kwargs):
        self.submit_entered.set()
        if not self.allow_submit_return.wait(2.0):
            raise AssertionError("submit test release was not signalled")
        self.pending = True
        return SimpleNamespace(
            submission_id="submission-1",
            conversation_id="conversation-1",
            turn_exchange_id="exchange-1",
            accepted_at_ms=123456,
            observation=SimpleNamespace(turn_lifecycle_id="turn-1"),
        )


class _FakeLowerRuntime:
    def __init__(self) -> None:
        self.send_called = threading.Event()

    def send_text(self, text, **kwargs):
        self.send_called.set()
        return ChatResponse(text="compatibility")

    def governance(self):
        return {"write_plane": "BROWSER_NATIVE_PAGE_OWNED_WRITE"}


class _DoubleAwaitLifecycle:
    def __init__(self) -> None:
        self.pending = True
        self.first_entered = threading.Event()
        self.second_entered = threading.Event()
        self.allow_first_return = threading.Event()
        self.call_count = 0
        self.active = 0
        self.max_active = 0
        self._state_lock = threading.Lock()

    def await_final(self, submission_id: str) -> ChatResponse:
        with self._state_lock:
            self.call_count += 1
            call_number = self.call_count
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if call_number == 1:
                self.first_entered.set()
                if not self.allow_first_return.wait(2.0):
                    raise AssertionError("await test release was not signalled")
                self.pending = False
                return ChatResponse(text="done")

            self.second_entered.set()
            if not self.pending:
                raise RuntimeError("submission handle is no longer pending")
            return ChatResponse(text="unexpected")
        finally:
            with self._state_lock:
                self.active -= 1


def _bare_transport() -> BrowserOwnedProductTransport:
    transport = object.__new__(BrowserOwnedProductTransport)
    transport.provider = SimpleNamespace()
    transport._submission_dispatch_lock = threading.RLock()
    transport._runtime = _FakeLowerRuntime()
    return transport


def _submission_ack() -> ProductSubmissionAck:
    provenance = ProductSubmissionProvenance(
        product_semantics=ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
        transport="browser-owned",
        write_plane="BROWSER_NATIVE_PAGE_OWNED_WRITE",
        evidence_source=SubmissionEvidenceSource.BROWSER_NATIVE_WRITE_COMPLETED,
        write_acknowledged=True,
        canonical_finality_proven=False,
        automatic_write_retry=False,
        fallback_transport=None,
    )
    return ProductSubmissionAck(
        submission_id="submission-1",
        transport="browser-owned",
        conversation_id="conversation-1",
        turn_exchange_id="exchange-1",
        accepted_at_ms=123456,
        turn_lifecycle_id="turn-1",
        write_may_have_committed=True,
        automatic_retry_allowed=False,
        canonical_finality_proven=False,
        provenance=provenance,
    )


def test_submit_publication_is_atomic_against_compatibility_send() -> None:
    transport = _bare_transport()
    lifecycle = _BlockingSubmitLifecycle()
    transport._submission_lifecycle = lifecycle

    submit_result: list[ProductSubmissionAck] = []
    submit_errors: list[BaseException] = []
    send_errors: list[BaseException] = []

    def do_submit() -> None:
        try:
            submit_result.append(transport.submit_text("split"))
        except BaseException as error:  # pragma: no cover - surfaced by assertions
            submit_errors.append(error)

    def do_send() -> None:
        try:
            transport.send_text("compatibility")
        except BaseException as error:
            send_errors.append(error)

    submit_thread = threading.Thread(target=do_submit)
    submit_thread.start()
    assert lifecycle.submit_entered.wait(1.0)

    send_thread = threading.Thread(target=do_send)
    send_thread.start()

    # Before the split submit publishes its pending acknowledgement, the
    # compatibility path must still be fenced at the transport dispatch lock.
    assert transport._runtime.send_called.wait(0.05) is False

    lifecycle.allow_submit_return.set()
    submit_thread.join(1.0)
    send_thread.join(1.0)

    assert submit_thread.is_alive() is False
    assert send_thread.is_alive() is False
    assert submit_errors == []
    assert len(submit_result) == 1
    assert submit_result[0].submission_id == "submission-1"
    assert len(send_errors) == 1
    assert str(send_errors[0]) == "pending split submission"
    assert transport._runtime.send_called.is_set() is False


def test_duplicate_await_is_serialized_and_second_handle_is_stale() -> None:
    transport = _bare_transport()
    lifecycle = _DoubleAwaitLifecycle()
    transport._submission_lifecycle = lifecycle
    ack = _submission_ack()

    responses: list[ChatResponse] = []
    errors: list[BaseException] = []

    def await_once() -> None:
        try:
            responses.append(transport.await_final(ack))
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=await_once)
    first.start()
    assert lifecycle.first_entered.wait(1.0)

    second = threading.Thread(target=await_once)
    second.start()

    # The second caller cannot enter lifecycle finalization concurrently.
    assert lifecycle.second_entered.wait(0.05) is False
    assert lifecycle.max_active == 1

    lifecycle.allow_first_return.set()
    first.join(1.0)
    second.join(1.0)

    assert first.is_alive() is False
    assert second.is_alive() is False
    assert [response.text for response in responses] == ["done"]
    assert len(errors) == 1
    assert str(errors[0]) == "submission handle is no longer pending"
    assert lifecycle.call_count == 2
    assert lifecycle.max_active == 1
