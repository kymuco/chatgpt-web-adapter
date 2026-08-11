from __future__ import annotations

import chatgpt_web_adapter.client as client_mod

from chatgpt_web_adapter.conversation_prepare import prepare_text_turn


def test_prepare_uses_runtime_client_endpoint(monkeypatch) -> None:
    patched_url = "http://127.0.0.1:43210/backend-api/f/conversation/prepare"
    monkeypatch.setattr(client_mod, "CHAT_CONVERSATION_PREPARE_URL", patched_url)
    seen = {}

    class Client:
        @staticmethod
        def _build_headers(extra):
            return {key: value for key, value in extra.items() if value is not None}

        def _json_request(self, method, url, payload, headers):
            seen["method"] = method
            seen["url"] = url
            return 200, {"status": "ok", "conduit_token": "test-token"}

    result, _payload = prepare_text_turn(
        Client(),
        "hello",
        model="gpt-5-6-thinking",
        conversation={"conversation_id": "conv-1", "message_id": "parent-1"},
        partial_query_message_id="user-1",
    )

    assert result.status_ok is True
    assert seen == {"method": "POST", "url": patched_url}
