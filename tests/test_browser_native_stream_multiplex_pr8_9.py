from __future__ import annotations

import threading

import chatgpt_web_adapter.browser_native_host as host_module
import chatgpt_web_adapter.browser_native_provider as provider_module
from chatgpt_web_adapter.browser_native_host import BrowserNativeBroker
from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider


def test_broker_multiplexes_turn_events_before_final_result(monkeypatch, tmp_path) -> None:
    broker = BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    forwarded: list[dict] = []
    emitted: list[dict] = []
    result_box: list[dict] = []

    monkeypatch.setattr(
        host_module,
        "write_native_message",
        lambda _stream, payload: forwarded.append(dict(payload)),
    )

    request = {
        "protocol": 1,
        "token": broker.token,
        "type": "turn",
        "request_id": "r1",
        "text": "hello",
        "timeoutMs": 5000,
        "streamTextObservations": True,
    }

    def run() -> None:
        result_box.append(broker.handle_local_request(request, event_sink=emitted.append))

    thread = threading.Thread(target=run)
    thread.start()
    for _ in range(1000):
        if forwarded:
            break
        threading.Event().wait(0.001)
    assert forwarded and forwarded[0]["request_id"] == "r1"

    broker.route_native_message(
        {
            "protocol": 1,
            "type": "turn_event",
            "request_id": "r1",
            "event": {"type": "assistant_text_snapshot", "sequence": 1, "text": "Hi"},
        }
    )
    broker.route_native_message(
        {
            "protocol": 1,
            "type": "turn_result",
            "request_id": "r1",
            "ok": True,
            "conversationId": "c1",
        }
    )
    thread.join(timeout=2)
    try:
        assert not thread.is_alive()
        assert emitted[0]["type"] == "turn_event"
        assert result_box[0]["type"] == "turn_result"
    finally:
        broker._server.server_close()


class _FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def settimeout(self, _timeout: float) -> None:
        pass


def test_provider_consumes_event_frames_and_returns_only_final(monkeypatch, tmp_path) -> None:
    provider = BrowserNativeTurnProvider(state_dir=tmp_path)
    monkeypatch.setattr(
        provider,
        "_load_descriptor",
        lambda: {"host": "127.0.0.1", "port": 1234, "token": "x" * 32, "protocol": 1},
    )
    monkeypatch.setattr(provider_module.socket, "create_connection", lambda *a, **k: _FakeSocket())
    monkeypatch.setattr(provider_module, "send_local_message", lambda _sock, _payload: None)
    frames = [
        {
            "protocol": 1,
            "type": "turn_event",
            "request_id": "r1",
            "event": {"type": "assistant_text_snapshot", "sequence": 1, "text": "Hi"},
        },
        {"protocol": 1, "type": "turn_result", "request_id": "r1", "ok": True},
    ]
    monkeypatch.setattr(provider_module, "recv_local_message", lambda _sock: frames.pop(0))
    events: list[dict] = []
    response = provider._rpc(
        {"type": "turn", "request_id": "r1"},
        timeout=1.0,
        on_event=events.append,
    )
    assert events == [{"type": "assistant_text_snapshot", "sequence": 1, "text": "Hi"}]
    assert response["type"] == "turn_result"


def test_provider_callback_failure_does_not_cancel_final_frame(monkeypatch, tmp_path) -> None:
    provider = BrowserNativeTurnProvider(state_dir=tmp_path)
    monkeypatch.setattr(
        provider,
        "_load_descriptor",
        lambda: {"host": "127.0.0.1", "port": 1234, "token": "x" * 32, "protocol": 1},
    )
    monkeypatch.setattr(provider_module.socket, "create_connection", lambda *a, **k: _FakeSocket())
    monkeypatch.setattr(provider_module, "send_local_message", lambda _sock, _payload: None)
    frames = [
        {
            "protocol": 1,
            "type": "turn_event",
            "request_id": "r1",
            "event": {"type": "assistant_text_delta", "sequence": 1, "delta": "x"},
        },
        {"protocol": 1, "type": "turn_result", "request_id": "r1", "ok": True},
    ]
    monkeypatch.setattr(provider_module, "recv_local_message", lambda _sock: frames.pop(0))

    def explode(_event: dict) -> None:
        raise RuntimeError("consumer failed")

    response = provider._rpc(
        {"type": "turn", "request_id": "r1"},
        timeout=1.0,
        on_event=explode,
    )
    assert response["ok"] is True
