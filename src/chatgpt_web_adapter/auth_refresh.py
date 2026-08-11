from __future__ import annotations

import json
import os
import tempfile
import threading
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
from .web_session import _sync_device_header, suppress_web_session_debug_trace

SESSION_URL = f"{CHAT_URL.rstrip('/')}/api/auth/session"
AUTH_REFRESH_SKEW_SECONDS = 300
_AUTH_FILE_LOCK = threading.Lock()


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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode: int | None = None
    try:
        existing_mode = path.stat().st_mode
    except OSError:
        pass
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        if existing_mode is not None:
            os.chmod(temporary_path, existing_mode)
        elif os.name != "nt":
            os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _persist_refreshed_auth(
    client: Any,
    path: Path,
    response: dict[str, Any],
) -> None:
    with _AUTH_FILE_LOCK:
        try:
            current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError) as error:
            raise AuthError(f"Failed to read auth data before refresh: {error}") from error
        if not isinstance(current, dict):
            current = {}
        current["accessToken"] = response["accessToken"].strip()
        current["sessionToken"] = response["sessionToken"].strip()
        if response.get("expires") is not None:
            current["expires"] = response["expires"]
        current["cookies"] = dict(getattr(client.auth, "cookies", {}) or {})
        current["headers"] = dict(getattr(client.auth, "headers", {}) or {})
        current.pop("proof_token", None)
        current.pop("turnstile_token", None)
        _atomic_write_json(path, current)


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
    for name in list(client.auth.cookies):
        if name == CHATGPT_SESSION_COOKIE or name.startswith(f"{CHATGPT_SESSION_COOKIE}."):
            del client.auth.cookies[name]
    client.auth.cookies[CHATGPT_SESSION_COOKIE] = session_token.strip()
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
