from __future__ import annotations

import json
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .browser_native_protocol import (
    PROTOCOL_VERSION,
    bridge_descriptor_path,
    recv_local_message,
    send_local_message,
)
from .exceptions import RequestError
from .types import ChatConversation, ConversationRef


@dataclass(frozen=True)
class BrowserNativeBridgeStatus:
    available: bool
    extension_connected: bool
    host_pid: int | None = None
    extension_id: str | None = None
    runtime_tab_id: int | None = None


@dataclass(frozen=True)
class BrowserNativeTurnResult:
    conversation_id: str
    turn_exchange_id: str | None
    response_status: int
    response_mime_type: str | None
    final_url: str | None
    tab_id: int | None
    tab_was_active: bool
    elapsed_ms: int | None


class BrowserNativeTurnProvider:
    """Send ordinary text turns through the official ChatGPT page runtime.

    The provider never receives browser cookies, Sentinel credentials, Turnstile
    state, or raw conversation SSE. It only talks to the local Native Messaging
    broker and receives safe turn metadata back from the extension.
    """

    def __init__(
        self,
        *,
        state_dir: str | Path | None = None,
        connect_timeout: float = 3.0,
        turn_timeout: float = 150.0,
    ) -> None:
        if connect_timeout <= 0:
            raise ValueError("connect_timeout must be positive")
        if turn_timeout <= 0:
            raise ValueError("turn_timeout must be positive")
        self.state_dir = Path(state_dir) if state_dir is not None else None
        self.connect_timeout = float(connect_timeout)
        self.turn_timeout = float(turn_timeout)

    @property
    def descriptor_path(self) -> Path:
        return bridge_descriptor_path(self.state_dir)

    def _load_descriptor(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.descriptor_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: no running Native Messaging bridge",
                request_stage="browser_native_bridge",
            ) from error
        except (OSError, ValueError) as error:
            raise RequestError(
                f"BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID: {error}",
                request_stage="browser_native_bridge",
            ) from error
        if not isinstance(payload, dict):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID: expected object",
                request_stage="browser_native_bridge",
            )
        host = payload.get("host")
        port = payload.get("port")
        token = payload.get("token")
        protocol = payload.get("protocol")
        if host not in {"127.0.0.1", "localhost"}:
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID: non-loopback host",
                request_stage="browser_native_bridge",
            )
        if not isinstance(port, int) or not (0 < port < 65536):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID: invalid port",
                request_stage="browser_native_bridge",
            )
        if not isinstance(token, str) or len(token) < 20:
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID: invalid token",
                request_stage="browser_native_bridge",
            )
        if protocol != PROTOCOL_VERSION:
            raise RequestError(
                f"BROWSER_NATIVE_PROTOCOL_MISMATCH: host={protocol} client={PROTOCOL_VERSION}",
                request_stage="browser_native_bridge",
            )
        return payload

    def _rpc(self, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            try:
                descriptor = self._load_descriptor()
                request = {
                    "protocol": PROTOCOL_VERSION,
                    "token": descriptor["token"],
                    **payload,
                }
                remaining = max(0.1, deadline - time.monotonic())
                with socket.create_connection(
                    (descriptor["host"], descriptor["port"]),
                    timeout=min(self.connect_timeout, remaining),
                ) as sock:
                    sock.settimeout(remaining)
                    send_local_message(sock, request)
                    response = recv_local_message(sock)
                    if response.get("protocol") != PROTOCOL_VERSION:
                        raise RequestError(
                            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid broker response",
                            request_stage="browser_native_bridge",
                        )
                    return response
            except (RequestError, OSError, EOFError, ValueError) as error:
                last_error = error
                if time.monotonic() >= deadline:
                    break
                time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        raise RequestError(
            f"BROWSER_NATIVE_BRIDGE_UNAVAILABLE: {last_error}",
            request_stage="browser_native_bridge",
        ) from last_error

    def status(self) -> BrowserNativeBridgeStatus:
        try:
            response = self._rpc(
                {"type": "ping", "request_id": str(uuid.uuid4())},
                timeout=self.connect_timeout,
            )
        except RequestError:
            return BrowserNativeBridgeStatus(False, False)
        return BrowserNativeBridgeStatus(
            available=bool(response.get("ok")),
            extension_connected=bool(response.get("extensionConnected")),
            host_pid=response.get("hostPid") if isinstance(response.get("hostPid"), int) else None,
            extension_id=response.get("extensionId") if isinstance(response.get("extensionId"), str) else None,
            runtime_tab_id=response.get("runtimeTabId") if isinstance(response.get("runtimeTabId"), int) else None,
        )

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float | None = None,
    ) -> BrowserNativeTurnResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 200_000:
            raise ValueError("text is too large for browser-native turn")
        conversation_id = None
        if conversation is not None:
            conversation_id = ConversationRef.from_any(conversation).conversation_id
        total_timeout = self.turn_timeout if timeout is None else float(timeout)
        if total_timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "conversationId": conversation_id,
                "text": text,
                "timeoutMs": int(total_timeout * 1000),
            },
            timeout=total_timeout + self.connect_timeout,
        )
        if response.get("request_id") != request_id:
            raise RequestError(
                "BROWSER_NATIVE_RESPONSE_MISMATCH",
                request_stage="browser_native_bridge",
            )
        if not response.get("ok"):
            error = response.get("error") or "BROWSER_NATIVE_TURN_FAILED"
            raise RequestError(str(error), request_stage="browser_native_turn")
        result_conversation_id = response.get("conversationId")
        status = response.get("responseStatus")
        if not isinstance(result_conversation_id, str) or not result_conversation_id.strip():
            raise RequestError(
                "BROWSER_NATIVE_TURN_MISSING_CONVERSATION_ID",
                request_stage="browser_native_turn",
            )
        if not isinstance(status, int) or status < 200 or status >= 300:
            raise RequestError(
                f"BROWSER_NATIVE_TURN_HTTP_STATUS:{status}",
                status_code=status if isinstance(status, int) else None,
                request_stage="browser_native_turn",
            )
        return BrowserNativeTurnResult(
            conversation_id=result_conversation_id.strip(),
            turn_exchange_id=response.get("turnExchangeId")
            if isinstance(response.get("turnExchangeId"), str)
            else None,
            response_status=status,
            response_mime_type=response.get("responseMimeType")
            if isinstance(response.get("responseMimeType"), str)
            else None,
            final_url=response.get("finalUrl") if isinstance(response.get("finalUrl"), str) else None,
            tab_id=response.get("tabId") if isinstance(response.get("tabId"), int) else None,
            tab_was_active=bool(response.get("tabWasActive")),
            elapsed_ms=response.get("elapsedMs") if isinstance(response.get("elapsedMs"), int) else None,
        )
