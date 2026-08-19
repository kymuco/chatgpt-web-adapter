from __future__ import annotations

import json
import os
import queue
import secrets
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .browser_native_protocol import (
    PROTOCOL_VERSION,
    bridge_descriptor_path,
    read_native_message,
    recv_local_message,
    send_local_message,
    write_native_message,
)


class _BrokerServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _BrokerHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        broker: BrowserNativeBroker = self.server.broker  # type: ignore[attr-defined]
        request: dict[str, Any] | None = None
        try:
            request = recv_local_message(self.request)

            def emit_event(message: dict[str, Any]) -> None:
                try:
                    send_local_message(self.request, message)
                except OSError:
                    # Observation delivery is best-effort and cannot change the
                    # already-delegated product write outcome.
                    pass

            response = broker.handle_local_request(
                request,
                event_sink=emit_event if request.get("streamTextObservations") is True else None,
            )
        except Exception as error:
            response = {
                "protocol": PROTOCOL_VERSION,
                "request_id": request.get("request_id") if isinstance(request, dict) else None,
                "ok": False,
                "error": f"BROWSER_NATIVE_BROKER_ERROR:{error}",
            }
        try:
            send_local_message(self.request, response)
        except OSError:
            pass


class BrowserNativeBroker:
    def __init__(self, *, state_dir: str | Path | None = None) -> None:
        self.state_dir = Path(state_dir) if state_dir is not None else None
        self.descriptor_path = bridge_descriptor_path(self.state_dir)
        self.token = secrets.token_urlsafe(32)
        self.pending: dict[str, queue.Queue[dict[str, Any]]] = {}
        self.pending_lock = threading.Lock()
        self.write_lock = threading.Lock()
        # PR8.8: turn mutation and runtime-tab disposal share one authority lock.
        # A CLOSE can never be forwarded concurrently with a page-owned turn.
        self.turn_lock = threading.Lock()
        self.extension_connected = False
        self.extension_id: str | None = None
        self.runtime_tab_id: int | None = None
        self._server = _BrokerServer(("127.0.0.1", 0), _BrokerHandler)
        self._server.broker = self  # type: ignore[attr-defined]
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="browser-native-loopback",
            daemon=True,
        )

    def start(self) -> None:
        self._server_thread.start()
        self._write_descriptor()

    def _write_descriptor(self) -> None:
        path = self.descriptor_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "protocol": PROTOCOL_VERSION,
            "host": "127.0.0.1",
            "port": int(self._server.server_address[1]),
            "token": self.token,
            "pid": os.getpid(),
            "startedAt": time.time(),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        try:
            payload = json.loads(self.descriptor_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if isinstance(payload, dict) and payload.get("pid") == os.getpid():
            try:
                self.descriptor_path.unlink()
            except OSError:
                pass
        with self.pending_lock:
            queues = list(self.pending.values())
            self.pending.clear()
        for waiter in queues:
            waiter.put(
                {
                    "protocol": PROTOCOL_VERSION,
                    "ok": False,
                    "error": "BROWSER_NATIVE_HOST_SHUTDOWN",
                }
            )

    def handle_local_request(
        self,
        request: dict[str, Any],
        *,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        request_id = request.get("request_id")
        base = {
            "protocol": PROTOCOL_VERSION,
            "request_id": request_id,
        }
        if request.get("protocol") != PROTOCOL_VERSION:
            return {**base, "ok": False, "error": "BROWSER_NATIVE_PROTOCOL_MISMATCH"}
        if not secrets.compare_digest(str(request.get("token") or ""), self.token):
            return {**base, "ok": False, "error": "BROWSER_NATIVE_UNAUTHORIZED"}

        operation = request.get("type")
        if operation == "ping":
            return {
                **base,
                "ok": True,
                "extensionConnected": self.extension_connected,
                "hostPid": os.getpid(),
                "extensionId": self.extension_id,
                "runtimeTabId": self.runtime_tab_id,
            }

        if operation not in {"turn", "release_runtime_tab"}:
            return {**base, "ok": False, "error": "BROWSER_NATIVE_UNKNOWN_OPERATION"}
        if not isinstance(request_id, str) or not request_id:
            return {**base, "ok": False, "error": "BROWSER_NATIVE_REQUEST_ID_REQUIRED"}
        if not self.extension_connected:
            return {**base, "ok": False, "error": "BROWSER_NATIVE_EXTENSION_NOT_CONNECTED"}
        if not self.turn_lock.acquire(blocking=False):
            return {**base, "ok": False, "error": "BROWSER_NATIVE_BRIDGE_BUSY"}

        try:
            timeout_ms = request.get("timeoutMs")
            default_timeout_ms = 120_000 if operation == "turn" else 10_000
            timeout = max(
                1.0,
                min(float(timeout_ms or default_timeout_ms) / 1000.0, 300.0),
            )
            waiter: queue.Queue[dict[str, Any]] = queue.Queue()
            with self.pending_lock:
                self.pending[request_id] = waiter
            forwarded = {
                key: value
                for key, value in request.items()
                if key != "token"
            }
            try:
                with self.write_lock:
                    write_native_message(sys.stdout.buffer, forwarded)
                deadline = time.monotonic() + timeout + 5.0
                while True:
                    try:
                        message = waiter.get(timeout=max(0.01, deadline - time.monotonic()))
                    except queue.Empty:
                        return {
                            **base,
                            "ok": False,
                            "error": "BROWSER_NATIVE_EXTENSION_TIMEOUT",
                        }
                    if message.get("type") == "turn_event":
                        if event_sink is not None:
                            event_sink(message)
                        continue
                    return message
            finally:
                with self.pending_lock:
                    self.pending.pop(request_id, None)
        finally:
            self.turn_lock.release()

    def route_native_message(self, message: dict[str, Any]) -> None:
        if message.get("protocol") != PROTOCOL_VERSION:
            return
        if message.get("type") == "hello":
            self.extension_connected = True
            self.extension_id = (
                message.get("extensionId")
                if isinstance(message.get("extensionId"), str)
                else None
            )
            self.runtime_tab_id = (
                message.get("runtimeTabId")
                if isinstance(message.get("runtimeTabId"), int)
                else None
            )
            return
        if message.get("type") == "runtime_state":
            self.runtime_tab_id = (
                message.get("runtimeTabId")
                if isinstance(message.get("runtimeTabId"), int)
                else None
            )
            return
        request_id = message.get("request_id")
        if not isinstance(request_id, str):
            return
        with self.pending_lock:
            waiter = self.pending.get(request_id)
        if waiter is not None:
            waiter.put_nowait(message)


def main() -> int:
    broker = BrowserNativeBroker()
    broker.start()
    try:
        while True:
            try:
                message = read_native_message(sys.stdin.buffer)
            except EOFError:
                break
            broker.route_native_message(message)
    except Exception as error:
        print(f"browser-native host error: {error}", file=sys.stderr, flush=True)
        return 2
    finally:
        broker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
