from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .auth import (
    CHATGPT_SESSION_COOKIE,
    CHAT_URL,
    _get_access_token_expiry,
)
from .exceptions import AuthError
from .auth_store import persist_auth_data
from .web_session import _sync_device_header, suppress_web_session_debug_trace

SESSION_URL = f"{CHAT_URL.rstrip('/')}/api/auth/session"
AUTH_REFRESH_SKEW_SECONDS = 300


@dataclass(frozen=True)
class AuthRefreshResult:
    status_code: int
    access_token_present: bool
    session_token_rotated: bool
    expires_present: bool
    persisted: bool


def auth_needs_refresh(access_token: str | None, *, now: datetime | None = None) -> bool:
    if not isinstance(access_token, str) or not access_token.strip():
        return True
    expires_at = _get_access_token_expiry(access_token)
    if expires_at is None:
        return False
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    return expires_at <= current + timedelta(seconds=AUTH_REFRESH_SKEW_SECONDS)


def _persist_refreshed_auth(
    client: Any,
    path: Path,
    response: dict[str, Any],
) -> None:
    persist_auth_data(
        client.auth,
        path,
        session_token=response["sessionToken"].strip(),
        session_expires_at=response.get("expires"),
    )


def refresh_auth_session(
    client: Any,
    *,
    persist: bool = True,
    auth_file: str | Path | None = None,
) -> AuthRefreshResult:
    """Refresh access/session credentials through the live session endpoint."""

    cookies = getattr(getattr(client, "auth", None), "cookies", None)
    if not isinstance(cookies, dict) or not any(
        name == CHATGPT_SESSION_COOKIE or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for name in cookies
    ):
        raise AuthError("Session refresh requires a ChatGPT session cookie")
    previous_session = cookies.get(CHATGPT_SESSION_COOKIE)
    headers = client._build_headers(
        {
            "accept": "application/json",
            "content-type": None,
            "origin": CHAT_URL.rstrip("/"),
            "referer": CHAT_URL,
        }
    )
    headers.pop("content-type", None)
    with suppress_web_session_debug_trace():
        status, data = client._json_request("GET", SESSION_URL, None, headers)
    if int(status) != 200 or not isinstance(data, dict):
        raise AuthError(f"ChatGPT session refresh failed: status={status}")
    access_token = data.get("accessToken")
    session_token = data.get("sessionToken")
    if not isinstance(access_token, str) or not access_token.strip():
        raise AuthError("ChatGPT session refresh response has no accessToken")
    if not isinstance(session_token, str) or not session_token.strip():
        raise AuthError("ChatGPT session refresh response has no sessionToken")

    client.auth.accessToken = access_token.strip()
    client.auth.accessTokenSource = "session-refresh:accessToken"
    client.auth.expires = data.get("expires")
    _sync_device_header(client)

    target = Path(auth_file) if auth_file is not None else getattr(client, "auth_file", None)
    persisted = bool(persist and isinstance(target, Path))
    if persisted:
        _persist_refreshed_auth(client, target, data)
    return AuthRefreshResult(
        status_code=int(status),
        access_token_present=True,
        session_token_rotated=previous_session != session_token.strip(),
        expires_present=data.get("expires") is not None,
        persisted=persisted,
    )
