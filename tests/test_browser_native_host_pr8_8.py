from __future__ import annotations

import chatgpt_web_adapter.browser_native_host as subject


def test_broker_forwards_release_runtime_tab_under_authority_lock(monkeypatch, tmp_path):
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True

    def fake_write(stream, forwarded):
        assert forwarded["type"] == "release_runtime_tab"
        assert forwarded["expectedRuntimeTabId"] == 77
        broker.route_native_message(
            {
                "protocol": subject.PROTOCOL_VERSION,
                "type": "release_runtime_tab_result",
                "request_id": forwarded["request_id"],
                "ok": True,
                "released": True,
                "alreadyAbsent": False,
                "runtimeTabId": 77,
                "browserAuthorityLeaseId": "lease-1",
            }
        )

    monkeypatch.setattr(subject, "write_native_message", fake_write)
    try:
        result = broker.handle_local_request(
            {
                "protocol": subject.PROTOCOL_VERSION,
                "token": broker.token,
                "type": "release_runtime_tab",
                "request_id": "r1",
                "expectedRuntimeTabId": 77,
                "browserAuthorityLeaseId": "lease-1",
                "timeoutMs": 1000,
            }
        )
    finally:
        broker._server.server_close()

    assert result["ok"] is True
    assert result["released"] is True


def test_broker_rejects_release_while_turn_authority_lock_busy(tmp_path):
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    broker.turn_lock.acquire()
    try:
        result = broker.handle_local_request(
            {
                "protocol": subject.PROTOCOL_VERSION,
                "token": broker.token,
                "type": "release_runtime_tab",
                "request_id": "r1",
                "browserAuthorityLeaseId": "lease-1",
            }
        )
    finally:
        broker.turn_lock.release()
        broker._server.server_close()

    assert result["ok"] is False
    assert result["error"] == "BROWSER_NATIVE_BRIDGE_BUSY"
