from __future__ import annotations

import json
import socket
import threading

from chatgpt_web_adapter.browser_native_protocol import recv_local_message, send_local_message
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider


def test_provider_round_trip_uses_loopback_token_and_safe_result(tmp_path) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    token = "t" * 32
    (tmp_path / "bridge.json").write_text(
        json.dumps(
            {
                "protocol": 1,
                "host": "127.0.0.1",
                "port": listener.getsockname()[1],
                "token": token,
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def serve() -> None:
        connection, _ = listener.accept()
        with connection:
            request = recv_local_message(connection)
            captured.update(request)
            send_local_message(
                connection,
                {
                    "protocol": 1,
                    "type": "turn_result",
                    "request_id": request["request_id"],
                    "ok": True,
                    "conversationId": "conversation-1",
                    "turnExchangeId": "turn-1",
                    "responseStatus": 200,
                    "responseMimeType": "text/event-stream",
                    "finalUrl": "https://chatgpt.com/c/conversation-1",
                    "tabId": 42,
                    "tabWasActive": False,
                    "elapsedMs": 1234,
                },
            )
        listener.close()

    thread = threading.Thread(target=serve)
    thread.start()
    result = BrowserNativeTurnProvider(state_dir=tmp_path).send_text("hello", timeout=2)
    thread.join(timeout=2)

    assert captured["token"] == token
    assert captured["conversationId"] is None
    assert result.conversation_id == "conversation-1"
    assert result.turn_exchange_id == "turn-1"
    assert result.response_status == 200
    assert result.tab_was_active is False
