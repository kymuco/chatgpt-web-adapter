from __future__ import annotations

from threading import Barrier, Thread
from types import SimpleNamespace
from typing import Any, Callable

from chatgpt_web_adapter.browserless_request_transport import BrowserlessRequestTransport
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.types import ChatConversation, ChatResponse


class _HealthCycleClient:
    def __init__(self) -> None:
        self.timeout = 60.0
        self.base_headers = {"user-agent": "health-cycle-test"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.status_reads = 0
        self.message_reads = 0
        self.status_hook: Callable[[], Any] | None = None

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **dict(extra or {})}

    def _json_request(self, method, url, payload, headers):
        raise AssertionError("nested health must fail before canonical network reads")

    def send(self, prompt, *, conversation=None, **kwargs):
        return ChatResponse(
            text="ordinary answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="ordinary-assistant",
                parent_message_id="ordinary-assistant",
            ),
        )

    def attach_conversation(self, conversation):
        return SimpleNamespace(
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="current-parent",
                parent_message_id="current-parent",
            )
        )

    def get_status(self, conversation):
        self.status_reads += 1
        if self.status_hook is not None:
            self.status_hook()
        return SimpleNamespace(
            status="completed",
            finish_reason="stop",
            message_id="current-parent",
        )

    def get_messages(self, conversation, **kwargs):
        self.message_reads += 1
        return []


def _conversation() -> ChatConversation:
    return ChatConversation(
        conversation_id="conversation-1",
        message_id="current-parent",
        parent_message_id="current-parent",
    )


def test_opposite_order_cross_client_health_callbacks_fail_without_deadlock() -> None:
    client_a = _HealthCycleClient()
    client_b = _HealthCycleClient()
    transport_a = BrowserlessRequestTransport(client_a)
    transport_b = BrowserlessRequestTransport(client_b)
    both_outer_locks_held = Barrier(2)
    errors: list[BaseException] = []

    def send_a(prompt, *, conversation=None, **kwargs):
        both_outer_locks_held.wait(timeout=1.0)
        return transport_b.health(_conversation())

    def send_b(prompt, *, conversation=None, **kwargs):
        both_outer_locks_held.wait(timeout=1.0)
        return transport_a.health(_conversation())

    client_a.send = send_a
    client_b.send = send_b

    def run(client: _HealthCycleClient, label: str) -> None:
        try:
            client.send(label)
        except BaseException as error:
            errors.append(error)

    thread_a = Thread(target=run, args=(client_a, "outer-a"))
    thread_b = Thread(target=run, args=(client_b, "outer-b"))
    thread_a.start()
    thread_b.start()
    thread_a.join(2.0)
    thread_b.join(2.0)

    assert thread_a.is_alive() is False
    assert thread_b.is_alive() is False
    assert len(errors) == 2
    assert all(isinstance(error, RequestError) for error in errors)
    assert all(
        "cross-client nested mutation browserless_health while send owns mutation authority"
        in str(error)
        for error in errors
    )
    assert client_a.status_reads == 0
    assert client_b.status_reads == 0
    assert client_a.message_reads == 0
    assert client_b.message_reads == 0


def test_opposite_order_cross_client_health_reads_fail_without_deadlock() -> None:
    client_a = _HealthCycleClient()
    client_b = _HealthCycleClient()
    transport_a = BrowserlessRequestTransport(client_a)
    transport_b = BrowserlessRequestTransport(client_b)
    both_health_reads_entered = Barrier(2)
    results: list[Any] = []
    errors: list[BaseException] = []

    def status_a() -> None:
        both_health_reads_entered.wait(timeout=1.0)
        transport_b.health(_conversation())

    def status_b() -> None:
        both_health_reads_entered.wait(timeout=1.0)
        transport_a.health(_conversation())

    client_a.status_hook = status_a
    client_b.status_hook = status_b

    def run(transport: BrowserlessRequestTransport) -> None:
        try:
            results.append(transport.health(_conversation()))
        except BaseException as error:
            errors.append(error)

    thread_a = Thread(target=run, args=(transport_a,))
    thread_b = Thread(target=run, args=(transport_b,))
    thread_a.start()
    thread_b.start()
    thread_a.join(2.0)
    thread_b.join(2.0)

    assert thread_a.is_alive() is False
    assert thread_b.is_alive() is False
    assert errors == []
    assert len(results) == 2
    assert all(result.ready is False for result in results)
    assert all(
        result.reason == "CANONICAL_STATUS_UNAVAILABLE:RequestError"
        for result in results
    )
    assert client_a.status_reads == 1
    assert client_b.status_reads == 1
    assert client_a.message_reads == 0
    assert client_b.message_reads == 0
