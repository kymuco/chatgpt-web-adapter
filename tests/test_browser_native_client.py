from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browser_native_client import send_browser_native
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnResult
from chatgpt_web_adapter.types import ChatConversation


class FakeProvider:
    def send_text(self, text, *, conversation=None, timeout=None):
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


def test_client_returns_canonical_readback_not_native_body() -> None:
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
        _browser_native_turn_provider = FakeProvider()

        @staticmethod
        def _emit_event(*args, **kwargs):
            return None

        def get_status(self, conversation):
            return SimpleNamespace(status="completed")

        def get_messages(self, conversation, **kwargs):
            if conversation == "existing-conversation":
                return [old]
            return [old, final]

        def attach_conversation(self, conversation):
            return SimpleNamespace(
                conversation=ChatConversation(conversation_id="conversation-1"),
                title="Browser native test",
            )

    response = send_browser_native(
        Client(),
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
