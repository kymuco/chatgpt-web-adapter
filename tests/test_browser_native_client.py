from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browser_native_client import send_browser_native
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnResult
from chatgpt_web_adapter.types import ChatConversation


class FakeProvider:
    def __init__(self) -> None:
        self.normal_calls = []

    def send_text(self, text, *, conversation=None, timeout=None):
        self.normal_calls.append((text, conversation, timeout))
        return BrowserNativeTurnResult(
            conversation_id="conversation-1",
            turn_exchange_id="turn-1",
            response_status=200,
            response_mime_type="text/event-stream",
            final_url="https://chatgpt.com/c/conversation-1",
            tab_id=17,
            tab_was_active=False,
            elapsed_ms=500,
        )


class RecoveryFakeProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.recovery_calls = []

    def send_text_with_stale_ui_recovery(
        self,
        text,
        *,
        conversation,
        timeout=None,
        canonical_completed_at_ms,
    ):
        self.recovery_calls.append(
            (text, conversation, timeout, canonical_completed_at_ms)
        )
        return BrowserNativeTurnResult(
            conversation_id="conversation-1",
            turn_exchange_id="turn-1",
            response_status=200,
            response_mime_type="text/event-stream",
            final_url="https://chatgpt.com/c/conversation-1",
            tab_id=17,
            tab_was_active=False,
            elapsed_ms=500,
            runtime_reloaded=True,
            runtime_reload_ms=321,
        )


def _client(provider, *, status_value="completed"):
    old = SimpleNamespace(
        message_id="old-assistant",
        finish_reason="stop",
        text="old",
        model="gpt-old",
    )
    final = SimpleNamespace(
        message_id="new-assistant",
        finish_reason="stop",
        text="CANONICAL_READBACK",
        model="gpt-new",
    )

    class Client:
        _browser_native_turn_provider = provider

        def __init__(self) -> None:
            self.events = []
            self.status_values = (
                list(status_value)
                if isinstance(status_value, (list, tuple))
                else None
            )

        def _emit_event(self, callback, event_type, **payload):
            self.events.append((event_type, payload))

        def get_status(self, conversation):
            if self.status_values is not None:
                value = self.status_values.pop(0) if self.status_values else "running"
            else:
                value = status_value
            return SimpleNamespace(status=value)

        def get_messages(self, conversation, **kwargs):
            if conversation == "existing-conversation":
                return [old]
            return [old, final]

        def attach_conversation(self, conversation):
            return SimpleNamespace(
                conversation=ChatConversation(conversation_id="conversation-1"),
                title="Browser native test",
            )

    return Client()


def test_client_returns_canonical_readback_not_native_body() -> None:
    provider = FakeProvider()
    client = _client(provider)
    response = send_browser_native(
        client,
        "hello",
        conversation="existing-conversation",
        timeout=2,
        poll_interval=0.01,
    )

    assert response.text == "CANONICAL_READBACK"
    assert response.conversation.conversation_id == "conversation-1"
    assert response.conversation.message_id == "new-assistant"
    assert response.request.turn_exchange_id == "turn-1"
    assert response.request.observed_model == "gpt-new"
    assert response.metrics.backend_status == 200
    assert provider.normal_calls == [("hello", "existing-conversation", 2)]


def test_completed_continuation_authorizes_bounded_stale_ui_recovery() -> None:
    provider = RecoveryFakeProvider()
    client = _client(provider, status_value="completed")

    response = send_browser_native(
        client,
        "hello",
        conversation="existing-conversation",
        timeout=2,
        poll_interval=0.01,
    )

    assert response.text == "CANONICAL_READBACK"
    assert provider.normal_calls == []
    assert len(provider.recovery_calls) == 1
    text, conversation, timeout, completed_at_ms = provider.recovery_calls[0]
    assert (text, conversation, timeout) == ("hello", "existing-conversation", 2)
    assert isinstance(completed_at_ms, int) and completed_at_ms > 0
    write_events = [
        payload
        for event_type, payload in client.events
        if event_type == "browser_native_write_completed"
    ]
    assert write_events[0]["runtime_reloaded"] is True
    assert write_events[0]["runtime_reload_ms"] == 321


def test_running_continuation_never_authorizes_stale_ui_recovery() -> None:
    provider = RecoveryFakeProvider()
    client = _client(provider, status_value="running")

    send_browser_native(
        client,
        "hello",
        conversation="existing-conversation",
        timeout=2,
        poll_interval=0.01,
    )

    assert provider.normal_calls == [("hello", "existing-conversation", 2)]
    assert provider.recovery_calls == []


def test_completion_evidence_must_still_be_completed_on_immediate_recheck() -> None:
    provider = RecoveryFakeProvider()
    client = _client(provider, status_value=["completed", "running", "completed"])

    send_browser_native(
        client,
        "hello",
        conversation="existing-conversation",
        timeout=2,
        poll_interval=0.01,
    )

    assert provider.normal_calls == [("hello", "existing-conversation", 2)]
    assert provider.recovery_calls == []


def test_new_chat_never_authorizes_stale_ui_recovery() -> None:
    provider = RecoveryFakeProvider()
    client = _client(provider, status_value="completed")

    send_browser_native(
        client,
        "hello",
        timeout=2,
        poll_interval=0.01,
    )

    assert provider.normal_calls == [("hello", None, 2)]
    assert provider.recovery_calls == []
