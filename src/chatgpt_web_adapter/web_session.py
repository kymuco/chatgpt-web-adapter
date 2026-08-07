from __future__ import annotations

from typing import Any, Callable

from .auth import CHAT_URL
from .exceptions import RequestError

SENSITIVE_WEB_SESSION_HEADERS = {
    "oai-device-id",
    "x-conduit-token",
}


def _sync_device_header(client: Any) -> bool:
    device_id = getattr(client.auth, "cookies", {}).get("oai-did")
    if not isinstance(device_id, str) or not device_id.strip():
        return False
    client.base_headers["oai-device-id"] = device_id.strip()
    return True


def bootstrap_web_session(client: Any) -> bool:
    """Refresh the minimum server-issued web-session context used by writes.

    This does not solve or synthesize browser challenges. It only reuses supplied
    session material, lets ChatGPT set ordinary cookies such as ``oai-did``, and
    mirrors that device id into the request header expected by the web backend.
    """

    if _sync_device_header(client):
        return True
    if bool(getattr(client, "_web_session_bootstrapped", False)):
        return False

    headers = client._build_headers({"accept": "text/html,application/xhtml+xml"})
    headers.pop("content-type", None)
    status, _body, _header_text = client._run_curl(
        "GET",
        CHAT_URL,
        headers,
        follow_redirects=True,
    )
    client._web_session_bootstrapped = True
    if status >= 400:
        raise RequestError(
            f"web session bootstrap status={status}",
            status_code=status,
            endpoint="/",
            request_stage="web_session_bootstrap",
        )
    return _sync_device_header(client)


def gate_get_ready_requirements(
    original_get_ready_requirements: Callable[..., tuple[dict[str, Any], str | None]],
) -> Callable[..., tuple[dict[str, Any], str | None]]:
    """Require legitimate browser challenge evidence before a write proceeds."""

    def get_ready_requirements(self: Any) -> tuple[dict[str, Any], str | None]:
        bootstrap_web_session(self)
        requirements, proof_header = original_get_ready_requirements(self)
        turnstile = requirements.get("turnstile") if isinstance(requirements, dict) else None
        turnstile_required = bool(turnstile.get("required")) if isinstance(turnstile, dict) else False
        if turnstile_required and not getattr(self.auth, "turnstile_token", None):
            raise RequestError(
                "TURNSTILE_REQUIRED: ChatGPT requires browser-derived Turnstile evidence for this write. "
                "The adapter will not synthesize or bypass that challenge; provide a legitimate token "
                "captured from the active browser session or use a read-only probe.",
                endpoint="chat-requirements",
                request_stage="turnstile_gate",
            )
        return requirements, proof_header

    return get_ready_requirements


def redact_web_session_headers(
    original_sanitize_header_value: Callable[..., str],
) -> Callable[..., str]:
    """Extend sanitized debug traces to cover current web-session credentials."""

    def sanitize_header_value(self: Any, key: str, value: str) -> str:
        if (
            bool(getattr(self, "debug_trace_sanitize", True))
            and key.strip().lower() in SENSITIVE_WEB_SESSION_HEADERS
        ):
            return "<redacted>"
        return original_sanitize_header_value(self, key, value)

    return sanitize_header_value
