from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .auth import (
    CHATGPT_SESSION_COOKIE,
    CHAT_URL,
    DEFAULT_USER_AGENT,
    _get_access_token_expiry,
)
from .auth_store import persist_auth_data
from .exceptions import AuthError
from .web_session import _sync_device_header

SESSION_URL = f"{CHAT_URL.rstrip('/')}/api/auth/session"
AUTH_REFRESH_SKEW_SECONDS = 300
AUTH_REFRESH_WORKER_MODULE = "chatgpt_web_adapter.auth_refresh_worker"
AUTH_REFRESH_MAX_REQUEST_BYTES = 128_000
AUTH_REFRESH_MAX_WORKER_OUTPUT_BYTES = 256_000
AUTH_REFRESH_MAX_TOKEN_CHARS = 100_000
AUTH_REFRESH_MAX_SET_COOKIE_HEADERS = 32
AUTH_REFRESH_MAX_SET_COOKIE_CHARS = 32_768
_AUTH_REFRESH_HEADER_ALLOWLIST = frozenset(
    {
        "accept",
        "accept-language",
        "oai-device-id",
        "origin",
        "priority",
        "referer",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "user-agent",
    }
)


@dataclass(frozen=True)
class AuthRefreshResult:
    """Redacted outcome of a successful ChatGPT session refresh."""

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


def _is_session_cookie_name(value: Any) -> bool:
    return isinstance(value, str) and (
        value == CHATGPT_SESSION_COOKIE
        or value.startswith(f"{CHATGPT_SESSION_COOKIE}.")
    )


def _session_cookie_header(cookies: dict[str, Any]) -> str:
    session_pairs = [
        f"{name}={value}"
        for name, value in cookies.items()
        if _is_session_cookie_name(name)
        and isinstance(value, str)
        and bool(value)
    ]
    if not session_pairs:
        raise AuthError("Session refresh requires a ChatGPT session cookie")

    pairs = list(session_pairs)
    device_id = cookies.get("oai-did")
    if isinstance(device_id, str) and device_id.strip():
        pairs.append(f"oai-did={device_id.strip()}")
    return "; ".join(pairs)


def _bounded_header_value(value: Any, *, max_chars: int = 16_384) -> str | None:
    if not isinstance(value, str) or not value or len(value) > max_chars:
        return None
    if "\r" in value or "\n" in value:
        return None
    return value


def _session_refresh_headers(client: Any, cookies: dict[str, Any]) -> dict[str, str]:
    source = getattr(client, "base_headers", None)
    headers: dict[str, str] = {}
    if isinstance(source, dict):
        for raw_name, raw_value in source.items():
            name = str(raw_name).strip().lower()
            if name not in _AUTH_REFRESH_HEADER_ALLOWLIST:
                continue
            value = _bounded_header_value(raw_value)
            if value is not None:
                headers[name] = value

    headers["accept"] = "application/json"
    headers["accept-encoding"] = "identity"
    headers["origin"] = CHAT_URL.rstrip("/")
    headers["referer"] = CHAT_URL
    headers.setdefault("user-agent", DEFAULT_USER_AGENT)
    device_id = cookies.get("oai-did")
    if isinstance(device_id, str) and device_id.strip():
        headers.setdefault("oai-device-id", device_id.strip())
    headers["cookie"] = _session_cookie_header(cookies)
    return headers


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


def _worker_timeout(client: Any) -> float:
    try:
        timeout = float(getattr(client, "timeout", 30.0))
    except (TypeError, ValueError):
        timeout = 30.0
    return max(1.0, min(timeout, 300.0))


def _validated_session_set_cookie_headers(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > AUTH_REFRESH_MAX_SET_COOKIE_HEADERS
    ):
        raise AuthError("ChatGPT session refresh returned invalid cookie metadata")
    accepted: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or len(item) > AUTH_REFRESH_MAX_SET_COOKIE_CHARS
        ):
            raise AuthError("ChatGPT session refresh returned invalid cookie metadata")
        name = item.split("=", 1)[0].strip()
        if _is_session_cookie_name(name):
            accepted.append(item)
    return accepted


def _request_session_json(
    client: Any,
    headers: dict[str, str],
) -> tuple[int, Any, list[str]]:
    """Run the auth-only HTTPS worker under one cancellable wall-clock deadline."""

    timeout = _worker_timeout(client)
    request_bytes = json.dumps(
        {"headers": headers, "timeout": timeout},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(request_bytes) > AUTH_REFRESH_MAX_REQUEST_BYTES:
        raise AuthError(
            "ChatGPT session refresh request exceeded the bounded transport size"
        )

    command = [sys.executable, "-m", AUTH_REFRESH_WORKER_MODULE]
    try:
        completed = subprocess.run(
            command,
            input=request_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AuthError(
            "ChatGPT session refresh failed before receiving an HTTP response"
        ) from None
    if completed.returncode != 0:
        raise AuthError(
            "ChatGPT session refresh failed before receiving an HTTP response"
        )
    if len(completed.stdout) > AUTH_REFRESH_MAX_WORKER_OUTPUT_BYTES:
        raise AuthError("ChatGPT session refresh returned an invalid response")
    try:
        result = json.loads(completed.stdout)
        status = int(result["status"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise AuthError("ChatGPT session refresh returned an invalid response") from None
    if not isinstance(result, dict) or status < 0 or status > 599:
        raise AuthError("ChatGPT session refresh returned an invalid response")

    set_cookie_headers = _validated_session_set_cookie_headers(
        result.get("set_cookie_headers", [])
    )
    return status, result.get("data"), set_cookie_headers


def _required_token(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > AUTH_REFRESH_MAX_TOKEN_CHARS
    ):
        raise AuthError(f"ChatGPT session refresh response has no valid {label}")
    return value.strip()


def refresh_auth_session(
    client: Any,
    *,
    persist: bool = True,
    auth_file: str | Path | None = None,
) -> AuthRefreshResult:
    """Refresh access/session credentials without delegating auth to curl."""

    cookies = getattr(getattr(client, "auth", None), "cookies", None)
    if not isinstance(cookies, dict):
        raise AuthError("Session refresh requires a ChatGPT session cookie")
    headers = _session_refresh_headers(client, cookies)
    previous_session = cookies.get(CHATGPT_SESSION_COOKIE)

    status, data, set_cookie_headers = _request_session_json(client, headers)
    if int(status) != 200 or not isinstance(data, dict):
        raise AuthError(f"ChatGPT session refresh failed: status={status}")

    access_token = _required_token(data.get("accessToken"), label="accessToken")
    session_token = _required_token(data.get("sessionToken"), label="sessionToken")
    expires = data.get("expires")
    if expires is not None and (
        not isinstance(expires, str) or len(expires) > 512
    ):
        raise AuthError("ChatGPT session refresh response has invalid expires metadata")

    update_cookies = getattr(client, "_update_cookies_from_text", None)
    if callable(update_cookies) and set_cookie_headers:
        update_cookies(
            "\n".join(f"set-cookie: {header}" for header in set_cookie_headers)
        )
    client.auth.accessToken = access_token
    client.auth.accessTokenSource = "session-refresh:accessToken"
    client.auth.expires = expires
    _sync_device_header(client)

    response = {
        "accessToken": access_token,
        "sessionToken": session_token,
        "expires": expires,
    }
    target = (
        Path(auth_file)
        if auth_file is not None
        else getattr(client, "auth_file", None)
    )
    persisted = bool(persist and isinstance(target, Path))
    if persisted:
        _persist_refreshed_auth(client, target, response)
    return AuthRefreshResult(
        status_code=int(status),
        access_token_present=True,
        session_token_rotated=previous_session != session_token,
        expires_present=expires is not None,
        persisted=persisted,
    )
