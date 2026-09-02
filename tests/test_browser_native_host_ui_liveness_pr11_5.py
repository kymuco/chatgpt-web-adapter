from __future__ import annotations

import chatgpt_web_adapter.browser_native_host as subject


def _request(broker: subject.BrowserNativeBroker, **updates) -> dict:
    payload = {
        "protocol": subject.PROTOCOL_VERSION,
        "token": broker.token,
        "type": "ui_liveness",
        "request_id": "liveness-1",
        "timeoutMs": 1000,
    }
    payload.update(updates)
    return payload


def test_disconnected_extension_returns_non_authoritative_unavailable(tmp_path) -> None:
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    try:
        result = broker.handle_local_request(_request(broker))
    finally:
        broker._server.server_close()

    assert result["ok"] is True
    assert result["type"] == "ui_liveness_result"
    assert result["state"] == "UNAVAILABLE"
    assert result["reasonCode"] == "EXTENSION_DISCONNECTED"
    assert result["grantsWriteAuthority"] is False
    assert result["grantsRetryAuthority"] is False
    assert result["canonicalFinalityProven"] is False
    assert broker.turn_lock.locked() is False


def test_active_authority_lane_returns_unknown_without_extension_probe(
    monkeypatch,
    tmp_path,
) -> None:
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    broker.runtime_tab_id = 77
    forwarded = False

    def fake_write(stream, payload):
        nonlocal forwarded
        forwarded = True

    monkeypatch.setattr(subject, "write_native_message", fake_write)
    broker.turn_lock.acquire()
    try:
        result = broker.handle_local_request(_request(broker))
        assert broker.turn_lock.locked() is True
    finally:
        broker.turn_lock.release()
        broker._server.server_close()

    assert result["ok"] is True
    assert result["state"] == "UNKNOWN"
    assert result["reasonCode"] == "AUTHORITY_LANE_ACTIVE"
    assert result["grantsWriteAuthority"] is False
    assert result["canonicalFinalityProven"] is False
    assert forwarded is False


def test_write_bearing_liveness_request_is_rejected_before_forward(
    monkeypatch,
    tmp_path,
) -> None:
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    broker.runtime_tab_id = 77
    forwarded = False

    def fake_write(stream, payload):
        nonlocal forwarded
        forwarded = True

    monkeypatch.setattr(subject, "write_native_message", fake_write)
    try:
        result = broker.handle_local_request(
            _request(broker, text="must never be forwarded")
        )
    finally:
        broker._server.server_close()

    assert result["ok"] is False
    assert result["error"] == "UI_LIVENESS_WRITE_BEARING_FIELDS_FORBIDDEN"
    assert forwarded is False
    assert broker.turn_lock.locked() is False
