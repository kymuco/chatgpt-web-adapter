"""Issue #169 bridge split: DELEGATION_ACCEPTED is its own phase.

Proves the three ACK layers are independent and that the final turn RPC
return is never the single whole-turn authority:

- DELEGATION_ACCEPTED: the host emits ``browser_native_delegation_accepted``
  the moment the command crosses into the browser plane (Native Messaging
  pipe write), BEFORE any extension terminality.
- WRITE_CONFIRMED: the correlated ``browser_native_write_completed`` event
  carrying the typed SSE identity authority for THIS submission.
- RESPONSE_CONFIRMED: the canonical readback plane (separate RPC), never the
  write RPC.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from chatgpt_web_adapter import browser_native_host as host_mod
from chatgpt_web_adapter.browser_native_client import submit_browser_native
from chatgpt_web_adapter.browser_native_host import BrowserNativeBroker
from chatgpt_web_adapter.browser_native_provider import (
    BrowserNativeTurnProvider,
    BrowserNativeTurnResult,
)


# --- host emits delegation_accepted exactly when the pipe write completes ---
def test_host_emits_delegation_accepted_after_pipe_write(tmp_path) -> None:
    broker = BrowserNativeBroker(state_dir=tmp_path)
    received: list[dict] = []
    original = host_mod.write_native_message
    responded: list[bool] = []

    def _capture_write(stream, payload):
        received.append({"pipe": payload})
        # The pipe accepted the command: answer from a background "extension".
        def _respond() -> None:
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                waiter = broker.pending.get("req-1")
                if waiter is not None:
                    waiter.put_nowait(
                        {
                            "protocol": host_mod.PROTOCOL_VERSION,
                            "request_id": "req-1",
                            "ok": True,
                            "type": "turn_result",
                            "conversationId": "conv-1",
                            "responseStatus": 200,
                        }
                    )
                    responded.append(True)
                    return
                time.sleep(0.005)

        threading.Thread(target=_respond, daemon=True).start()

    broker.extension_connected = True
    request = {
        "protocol": host_mod.PROTOCOL_VERSION,
        "token": broker.token,
        "type": "turn",
        "request_id": "req-1",
        "conversationId": None,
        "text": "hello",
        "attachmentPaths": [],
        "timeoutMs": 2000,
        "phases": True,
    }

    def event_sink(message: dict) -> None:
        received.append(message)

    host_mod.write_native_message = _capture_write
    try:
        response = broker.handle_local_request(request, event_sink=event_sink)
    finally:
        host_mod.write_native_message = original

    delegation_frames = [
        frame
        for frame in received
        if frame.get("type") == "turn_event"
        and frame.get("event", {}).get("type")
        == "browser_native_delegation_accepted"
    ]
    assert len(delegation_frames) == 1
    assert delegation_frames[0]["request_id"] == "req-1"
    assert isinstance(delegation_frames[0]["event"].get("acceptedAtMs"), int)
    # delegation lands strictly BEFORE the terminal turn result is returned
    assert responded == [True]
    assert response["ok"] is True
    # NOTE: broker.start() was never called (no serve_forever thread); the
    # embedded TCP server is only server_close()d here - Broker.close() would
    # block forever on shutdown() without a serving loop.
    broker._server.server_close()


def test_host_without_phases_emits_no_delegation_frame(tmp_path) -> None:
    # Compatibility: callers that do not request phases see the old surface.
    broker = BrowserNativeBroker(state_dir=tmp_path)
    received: list[dict] = []
    original = host_mod.write_native_message

    def _capture_write(stream, payload):
        waiter = broker.pending.get("req-quiet")
        if waiter is not None:
            waiter.put_nowait(
                {
                    "protocol": host_mod.PROTOCOL_VERSION,
                    "request_id": "req-quiet",
                    "ok": True,
                    "type": "turn_result",
                    "conversationId": "conv-1",
                    "responseStatus": 200,
                }
            )

    broker.extension_connected = True
    # No phases flag: respond synchronously inside the fake write.
    request = {
        "protocol": host_mod.PROTOCOL_VERSION,
        "token": broker.token,
        "type": "turn",
        "request_id": "req-quiet",
        "conversationId": None,
        "text": "hello",
        "attachmentPaths": [],
        "timeoutMs": 2000,
    }
    host_mod.write_native_message = _capture_write
    try:
        # Pre-seed pending so the synchronous fake write can answer.
        import queue as _queue

        waiter = _queue.Queue()
        waiter.put(
            {
                "protocol": host_mod.PROTOCOL_VERSION,
                "request_id": "req-quiet",
                "ok": True,
                "type": "turn_result",
                "conversationId": "conv-1",
                "responseStatus": 200,
            }
        )
        broker.pending["req-quiet"] = waiter
        response = broker.handle_local_request(
            request, event_sink=lambda message: received.append(message)
        )
    finally:
        host_mod.write_native_message = original
    assert response["ok"] is True
    assert not [
        frame
        for frame in received
        if frame.get("event", {}).get("type")
        == "browser_native_delegation_accepted"
    ]
    broker._server.server_close()


# --- provider requests phases and records the delegation ACK ----------------
def test_provider_records_delegation_accepted_phase() -> None:
    provider = BrowserNativeTurnProvider(state_dir="unused")

    captured: dict = {}

    def fake_rpc(payload, *, timeout, on_event=None):
        captured["payload"] = payload
        assert payload.get("phases") is True
        if on_event is not None:
            on_event(
                {
                    "type": "browser_native_delegation_accepted",
                    "acceptedAtMs": 4242,
                }
            )
        return {
            "protocol": host_mod.PROTOCOL_VERSION,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": "conv-1",
            "responseStatus": 200,
        }

    provider._rpc = fake_rpc
    result = provider.send_text("hello", timeout=1.0)
    assert result.delegation_accepted is True
    assert result.delegation_accepted_at_ms == 4242


def test_provider_without_delegation_frame_reports_not_delegated() -> None:
    provider = BrowserNativeTurnProvider(state_dir="unused")

    def fake_rpc(payload, *, timeout, on_event=None):
        return {
            "protocol": host_mod.PROTOCOL_VERSION,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": "conv-1",
            "responseStatus": 200,
        }

    provider._rpc = fake_rpc
    result = provider.send_text("hello", timeout=1.0)
    assert result.delegation_accepted is False
    assert result.delegation_accepted_at_ms is None


# --- client forwards the phase to the transport on_event stream --------------
def test_client_forwards_delegation_accepted_before_write_completed() -> None:
    class _Provider:
        def send_text(self, text, *, conversation=None, timeout=None):
            return BrowserNativeTurnResult(
                conversation_id="conv-1",
                turn_exchange_id=None,
                response_status=200,
                response_mime_type=None,
                final_url=None,
                tab_id=None,
                tab_was_active=False,
                elapsed_ms=1,
                delegation_accepted=True,
                delegation_accepted_at_ms=555,
            )

    class _Client:
        _browser_native_turn_provider = _Provider()

        def _emit_event(self, callback, event_type, **payload):
            if callback is None:
                return
            callback({"type": event_type, **payload})

        def get_messages(self, *args, **kwargs):
            return []

        def get_status(self, *args, **kwargs):
            return SimpleNamespace(status="completed")

    events: list[dict] = []
    submit_browser_native(
        _Client(),
        "hello",
        conversation=None,
        timeout=5.0,
        poll_interval=0.1,
        on_event=lambda event: events.append(event),
    )
    types = [event.get("type") for event in events]
    assert "browser_native_delegation_accepted" in types
    assert "browser_native_write_completed" in types
    assert types.index("browser_native_delegation_accepted") < types.index(
        "browser_native_write_completed"
    )
    delegation = events[types.index("browser_native_delegation_accepted")]
    assert delegation["acceptedAtMs"] == 555
    assert delegation["canonical_finality_proven"] is False
