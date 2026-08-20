from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
    runtime_reloaded: bool = False
    runtime_reload_ms: int | None = None
    runtime_tab_preexisting: bool | None = None
    runtime_tab_created_for_turn: bool | None = None
    tab_active_after: bool | None = None
    tab_activated_during_turn: bool | None = None
    foreground_activation_observed: bool | None = None
    browser_authority_lease_id: str | None = None


@dataclass(frozen=True)
class BrowserNativeRuntimeTabReleaseResult:
    released: bool
    already_absent: bool
    runtime_tab_id: int | None
    browser_authority_lease_id: str


class BrowserNativeTurnProvider:
    """Send ordinary text turns through the official ChatGPT page runtime.

    PR8.9 adds optional revision-safe text event frames over the same loopback
    request. Raw conversation SSE still never leaves the extension.
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
        self._authority_context = threading.local()

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

    def _rpc(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            request_sent = False
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
                    request_sent = True
                    while True:
                        response = recv_local_message(sock)
                        if response.get("protocol") != PROTOCOL_VERSION:
                            raise RequestError(
                                "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid broker response",
                                request_stage="browser_native_bridge",
                            )
                        if response.get("type") == "turn_event":
                            if response.get("request_id") != payload.get("request_id"):
                                raise RequestError(
                                    "BROWSER_NATIVE_RESPONSE_MISMATCH",
                                    request_stage="browser_native_bridge",
                                )
                            event = response.get("event")
                            if isinstance(event, dict) and on_event is not None:
                                try:
                                    on_event(dict(event))
                                except Exception:
                                    # Observation callbacks cannot invalidate or
                                    # replay an already-delegated product write.
                                    pass
                            continue
                        return response
            except (RequestError, OSError, EOFError, ValueError) as error:
                last_error = error
                if request_sent:
                    raise RequestError(
                        f"BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: {error}",
                        request_stage="browser_native_bridge",
                    ) from error
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

    @staticmethod
    def _optional_bool(response: dict[str, Any], key: str) -> bool | None:
        value = response.get(key)
        return value if isinstance(value, bool) else None

    def set_browser_authority_lease(self, lease_id: str) -> None:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("browser authority lease_id is required")
        self._authority_context.lease_id = lease_id.strip()

    def clear_browser_authority_lease(self) -> None:
        if hasattr(self._authority_context, "lease_id"):
            del self._authority_context.lease_id

    def _current_browser_authority_lease_id(self) -> str | None:
        value = getattr(self._authority_context, "lease_id", None)
        return value if isinstance(value, str) and value else None

    def _send_text_request(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None,
        timeout: float | None,
        canonical_completed_at_ms: int | None,
        on_text_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> BrowserNativeTurnResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 200_000:
            raise ValueError("text is too large for browser-native turn")
        conversation_id = None
        if conversation is not None:
            conversation_id = ConversationRef.from_any(conversation).conversation_id
        if canonical_completed_at_ms is not None and conversation_id is None:
            raise ValueError("stale UI recovery requires an existing conversation")
        if canonical_completed_at_ms is not None:
            if isinstance(canonical_completed_at_ms, bool) or canonical_completed_at_ms <= 0:
                raise ValueError("canonical_completed_at_ms must be a positive integer")
            canonical_completed_at_ms = int(canonical_completed_at_ms)

        total_timeout = self.turn_timeout if timeout is None else float(timeout)
        if total_timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        authority_lease_id = self._current_browser_authority_lease_id()
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "conversationId": conversation_id,
                "text": text,
                "timeoutMs": int(total_timeout * 1000),
                "canonicalCompleted": canonical_completed_at_ms is not None,
                "canonicalCompletedAtMs": canonical_completed_at_ms,
                "browserAuthorityLeaseId": authority_lease_id,
                "streamTextObservations": on_text_event is not None,
            },
            timeout=total_timeout + self.connect_timeout,
            on_event=on_text_event,
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
        response_lease_id = response.get("browserAuthorityLeaseId")
        if authority_lease_id is not None and response_lease_id != authority_lease_id:
            raise RequestError(
                "BROWSER_NATIVE_AUTHORITY_LEASE_MISMATCH",
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
            runtime_reloaded=bool(response.get("runtimeReloaded")),
            runtime_reload_ms=response.get("runtimeReloadMs")
            if isinstance(response.get("runtimeReloadMs"), int)
            else None,
            runtime_tab_preexisting=self._optional_bool(response, "runtimeTabPreexisting"),
            runtime_tab_created_for_turn=self._optional_bool(response, "runtimeTabCreatedForTurn"),
            tab_active_after=self._optional_bool(response, "tabActiveAfter"),
            tab_activated_during_turn=self._optional_bool(response, "tabActivatedDuringTurn"),
            foreground_activation_observed=self._optional_bool(response, "foregroundActivationObserved"),
            browser_authority_lease_id=response_lease_id
            if isinstance(response_lease_id, str)
            else None,
        )

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float | None = None,
    ) -> BrowserNativeTurnResult:
        return self._send_text_request(
            text,
            conversation=conversation,
            timeout=timeout,
            canonical_completed_at_ms=None,
        )

    def send_text_streaming(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str | None = None,
        timeout: float | None = None,
        on_text_event: Callable[[dict[str, Any]], None],
    ) -> BrowserNativeTurnResult:
        if not callable(on_text_event):
            raise TypeError("on_text_event must be callable")
        return self._send_text_request(
            text,
            conversation=conversation,
            timeout=timeout,
            canonical_completed_at_ms=None,
            on_text_event=on_text_event,
        )

    def send_text_with_stale_ui_recovery(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
        timeout: float | None = None,
        canonical_completed_at_ms: int,
    ) -> BrowserNativeTurnResult:
        return self._send_text_request(
            text,
            conversation=conversation,
            timeout=timeout,
            canonical_completed_at_ms=canonical_completed_at_ms,
        )

    def send_text_with_stale_ui_recovery_streaming(
        self,
        text: str,
        *,
        conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
        timeout: float | None = None,
        canonical_completed_at_ms: int,
        on_text_event: Callable[[dict[str, Any]], None],
    ) -> BrowserNativeTurnResult:
        if not callable(on_text_event):
            raise TypeError("on_text_event must be callable")
        return self._send_text_request(
            text,
            conversation=conversation,
            timeout=timeout,
            canonical_completed_at_ms=canonical_completed_at_ms,
            on_text_event=on_text_event,
        )

    def release_runtime_tab(
        self,
        *,
        expected_runtime_tab_id: int | None,
        browser_authority_lease_id: str,
        timeout: float = 10.0,
    ) -> BrowserNativeRuntimeTabReleaseResult:
        if expected_runtime_tab_id is not None and (
            isinstance(expected_runtime_tab_id, bool)
            or not isinstance(expected_runtime_tab_id, int)
            or expected_runtime_tab_id <= 0
        ):
            raise ValueError("expected_runtime_tab_id must be a positive int or None")
        if not isinstance(browser_authority_lease_id, str) or not browser_authority_lease_id.strip():
            raise ValueError("browser_authority_lease_id is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        request_id = str(uuid.uuid4())
        lease_id = browser_authority_lease_id.strip()
        response = self._rpc(
            {
                "type": "release_runtime_tab",
                "request_id": request_id,
                "expectedRuntimeTabId": expected_runtime_tab_id,
                "browserAuthorityLeaseId": lease_id,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout + self.connect_timeout,
        )
        if response.get("request_id") != request_id:
            raise RequestError(
                "BROWSER_NATIVE_RESPONSE_MISMATCH",
                request_stage="browser_native_runtime_tab_release",
            )
        if not response.get("ok"):
            error = response.get("error") or "BROWSER_NATIVE_RUNTIME_TAB_RELEASE_FAILED"
            raise RequestError(
                str(error),
                request_stage="browser_native_runtime_tab_release",
            )
        response_lease_id = response.get("browserAuthorityLeaseId")
        if response_lease_id != lease_id:
            raise RequestError(
                "BROWSER_NATIVE_AUTHORITY_LEASE_MISMATCH",
                request_stage="browser_native_runtime_tab_release",
            )
        runtime_tab_id = response.get("runtimeTabId")
        return BrowserNativeRuntimeTabReleaseResult(
            released=bool(response.get("released")),
            already_absent=bool(response.get("alreadyAbsent")),
            runtime_tab_id=runtime_tab_id if isinstance(runtime_tab_id, int) else None,
            browser_authority_lease_id=lease_id,
        )
