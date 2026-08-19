from __future__ import annotations

from chatgpt_web_adapter.browser_native_host import BrowserNativeBroker


def test_broker_rejects_wrong_local_token_and_answers_ping(tmp_path) -> None:
    broker = BrowserNativeBroker(state_dir=tmp_path)
    broker.start()
    try:
        denied = broker.handle_local_request(
            {"protocol": 1, "type": "ping", "request_id": "x", "token": "wrong"}
        )
        assert denied["ok"] is False
        assert denied["error"] == "BROWSER_NATIVE_UNAUTHORIZED"

        allowed = broker.handle_local_request(
            {
                "protocol": 1,
                "type": "ping",
                "request_id": "y",
                "token": broker.token,
            }
        )
        assert allowed["ok"] is True
        assert allowed["extensionConnected"] is False
    finally:
        broker.close()
