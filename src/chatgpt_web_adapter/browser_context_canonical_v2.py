from __future__ import annotations

import json
import socket
import time
import uuid
from typing import Any

from .browser_context_canonical import (
    BROWSER_CONTEXT_CANONICAL_READ_PLANE,
    BrowserContextCanonicalReadError,
    _CanonicalReadChunkCollector,
)
from .browser_context_canonical import (
    BrowserContextCanonicalClient as _LegacyBrowserContextCanonicalClient,
)
from .browser_context_canonical import (
    BrowserContextCanonicalTransport as _LegacyBrowserContextCanonicalTransport,
)
from .browser_native_protocol import (
    PROTOCOL_VERSION,
    recv_local_message,
    send_local_message,
)
from .browser_native_provider import BrowserNativeTurnProvider
from .conversation_read_v2 import get_messages_v2, normalize_conversation_payload
from .types import ConversationRef

_CANONICAL_TIMEOUT_MAX_ATTEMPTS = 2
_CANONICAL_TIMEOUT_RETRY_DELAY_SECONDS = 0.25


class BrowserContextCanonicalTransportV2(_LegacyBrowserContextCanonicalTransport):
    """Read current ChatGPT conversation pages through the authenticated tab."""

    def _read_wire_conversation(
        self,
        conversation_id: str,
        *,
        timeout: float | None = None,
        include_all_pages: bool,
    ) -> dict[str, Any]:
        ref = ConversationRef(conversation_id)
        read_timeout = self.read_timeout if timeout is None else float(timeout)
        if read_timeout <= 0:
            raise ValueError("timeout must be positive")

        lease_id = self._lease_id()
        for attempt in range(1, _CANONICAL_TIMEOUT_MAX_ATTEMPTS + 1):
            try:
                return self._read_wire_conversation_once(
                    ref.conversation_id,
                    read_timeout=read_timeout,
                    include_all_pages=include_all_pages,
                    lease_id=lease_id,
                )
            except BrowserContextCanonicalReadError as error:
                if error.reason_code != "CANONICAL_READ_TIMEOUT":
                    raise
                if attempt >= _CANONICAL_TIMEOUT_MAX_ATTEMPTS:
                    raise BrowserContextCanonicalReadError(
                        "CANONICAL_READ_TIMEOUT_EXHAUSTED",
                        conversation_id=ref.conversation_id,
                        retryable=True,
                    ) from error
                time.sleep(_CANONICAL_TIMEOUT_RETRY_DELAY_SECONDS)

        raise AssertionError("unreachable canonical-read retry state")

    def _read_wire_conversation_once(
        self,
        conversation_id: str,
        *,
        read_timeout: float,
        include_all_pages: bool,
        lease_id: str | None,
    ) -> dict[str, Any]:
        descriptor = self._descriptor()
        request_id = str(uuid.uuid4())
        request = {
            "protocol": PROTOCOL_VERSION,
            "token": descriptor["token"],
            "type": "canonical_read",
            "request_id": request_id,
            "conversationId": conversation_id,
            "timeoutMs": int(read_timeout * 1000),
            "browserAuthorityLeaseId": lease_id,
            "includeAllPages": bool(include_all_pages),
        }
        collector = _CanonicalReadChunkCollector(request_id=request_id)
        deadline = time.monotonic() + read_timeout + 6.0

        try:
            remaining = max(0.1, deadline - time.monotonic())
            with socket.create_connection(
                (descriptor["host"], descriptor["port"]),
                timeout=min(
                    float(getattr(self.provider, "connect_timeout", 3.0)),
                    remaining,
                ),
            ) as sock:
                sock.settimeout(remaining)
                send_local_message(sock, request)
                while True:
                    frame = recv_local_message(sock)
                    if frame.get("protocol") != PROTOCOL_VERSION:
                        raise BrowserContextCanonicalReadError(
                            "CANONICAL_READ_PROTOCOL_MISMATCH",
                            conversation_id=conversation_id,
                        )
                    if frame.get("request_id") != request_id:
                        raise BrowserContextCanonicalReadError(
                            "CANONICAL_READ_RESPONSE_MISMATCH",
                            conversation_id=conversation_id,
                        )
                    if frame.get("type") == "canonical_read_chunk":
                        try:
                            collector.add(frame)
                        except ValueError as error:
                            raise BrowserContextCanonicalReadError(
                                str(error),
                                conversation_id=conversation_id,
                            ) from error
                        continue
                    response = frame
                    break
        except BrowserContextCanonicalReadError:
            raise
        except (OSError, EOFError, ValueError) as error:
            raise BrowserContextCanonicalReadError(
                "CANONICAL_READ_BRIDGE_FAILURE",
                conversation_id=conversation_id,
            ) from error

        if response.get("ok") is not True:
            reason = response.get("reasonCode") or response.get("error")
            status = response.get("status")
            status_code = (
                status
                if isinstance(status, int) and not isinstance(status, bool)
                else None
            )
            raise BrowserContextCanonicalReadError(
                reason if isinstance(reason, str) else "CANONICAL_READ_FAILED",
                conversation_id=conversation_id,
                status_code=status_code,
                content_type=(
                    response.get("contentType")
                    if isinstance(response.get("contentType"), str)
                    else None
                ),
                retryable=response.get("retryable") is True,
            )
        if response.get("type") != "canonical_read_result":
            raise BrowserContextCanonicalReadError(
                "CANONICAL_READ_RESULT_TYPE_INVALID",
                conversation_id=conversation_id,
            )

        try:
            raw_body = collector.finish(response)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            reason = str(error)
            raise BrowserContextCanonicalReadError(
                reason
                if reason.startswith("CANONICAL_READ_")
                else "CANONICAL_READ_MALFORMED_JSON",
                conversation_id=conversation_id,
                status_code=(
                    response.get("status")
                    if isinstance(response.get("status"), int)
                    and not isinstance(response.get("status"), bool)
                    else None
                ),
                content_type=(
                    response.get("contentType")
                    if isinstance(response.get("contentType"), str)
                    else None
                ),
            ) from error
        if not isinstance(payload, dict):
            raise BrowserContextCanonicalReadError(
                "CANONICAL_READ_JSON_OBJECT_REQUIRED",
                conversation_id=conversation_id,
            )
        return payload

    def read_conversation(
        self,
        conversation_id: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        payload = self._read_wire_conversation(
            conversation_id,
            timeout=timeout,
            include_all_pages=False,
        )
        return normalize_conversation_payload(payload)

    def read_full_conversation(
        self,
        conversation_id: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        payload = self._read_wire_conversation(
            conversation_id,
            timeout=timeout,
            include_all_pages=True,
        )
        return normalize_conversation_payload(payload)


class BrowserContextCanonicalClientV2(_LegacyBrowserContextCanonicalClient):
    """Canonical client that understands current flat/paginated conversation reads."""

    def __init__(
        self,
        source_client: Any,
        provider: BrowserNativeTurnProvider,
        *,
        read_timeout: float = 30.0,
    ) -> None:
        super().__init__(source_client, provider, read_timeout=read_timeout)
        self.transport = BrowserContextCanonicalTransportV2(
            provider,
            read_timeout=read_timeout,
        )

    def _get_full_conversation_payload(self, conversation_id: str) -> dict[str, Any]:
        return self.transport.read_full_conversation(conversation_id)

    get_messages = get_messages_v2


__all__ = [
    "BROWSER_CONTEXT_CANONICAL_READ_PLANE",
    "BrowserContextCanonicalClientV2",
    "BrowserContextCanonicalReadError",
    "BrowserContextCanonicalTransportV2",
]
