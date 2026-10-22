"""Opt-in bridge from an existing ChatGPT browser tab to local auth_data.json.

This intentionally changes the historical no-credential-export boundary ONLY
for an explicit auth_sync RPC. Never print or log returned session/cookie values.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import CHATGPT_SESSION_COOKIE, DEFAULT_AUTH_FILE
from .auth_store import persist_auth_data
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import AuthError, RequestError
from .types import AuthData

_MAX_TOKEN_CHARS = 100_000


@dataclass(frozen=True)
class BrowserAuthSyncResult:
    auth: AuthData
    persisted: bool
    auth_file: Path


def _credential(value: Any, *, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TOKEN_CHARS:
        if optional and value == "":
            return None
        raise AuthError(f"BROWSER_AUTH_INVALID_{field.upper()}")
    return value.strip()


def sync_browser_auth(
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    *,
    provider: BrowserNativeTurnProvider | None = None,
    persist: bool = True,
) -> BrowserAuthSyncResult:
    """Synchronize real browser credentials without launching or navigating a tab."""

    path = Path(auth_file)
    bridge = provider if provider is not None else BrowserNativeTurnProvider()
    request_id = str(uuid.uuid4())
    try:
        response = bridge._rpc(
            {"type": "auth_sync", "request_id": request_id},
            timeout=23.0,
        )
    except RequestError as error:
        raise AuthError("BROWSER_AUTH_BRIDGE_UNAVAILABLE") from error

    if (
        not isinstance(response, dict)
        or response.get("protocol") != 1
        or response.get("request_id") != request_id
        or response.get("type") != "auth_sync_result"
    ):
        raise AuthError("BROWSER_AUTH_RESPONSE_MISMATCH")
    if response.get("ok") is not True:
        reason = response.get("reasonCode")
        if not isinstance(reason, str) or not reason.startswith("BROWSER_AUTH_"):
            reason = "BROWSER_AUTH_SYNC_UNAVAILABLE"
        raise AuthError(reason)

    session = response.get("session")
    if not isinstance(session, dict):
        raise AuthError("BROWSER_AUTH_SESSION_INVALID")
    access_token = _credential(session.get("accessToken"), field="access_token")
    session_token = _credential(
        session.get("sessionToken"), field="session_token", optional=True
    )
    expires = session.get("expires")
    if expires is not None and (not isinstance(expires, str) or len(expires) > 512):
        raise AuthError("BROWSER_AUTH_EXPIRES_INVALID")

    cookies = session.get("cookies")
    records = session.get("browserCookies")
    if not isinstance(cookies, dict) or not isinstance(records, list):
        raise AuthError("BROWSER_AUTH_COOKIES_INVALID")
    if len(cookies) > 100 or len(records) > 100:
        raise AuthError("BROWSER_AUTH_COOKIES_OVERSIZE")
    for name, value in cookies.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(value, str)
            or len(value) > _MAX_TOKEN_CHARS
        ):
            raise AuthError("BROWSER_AUTH_COOKIES_INVALID")
    if not any(
        key == CHATGPT_SESSION_COOKIE
        or key.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for key in cookies
    ):
        raise AuthError("BROWSER_AUTH_SESSION_COOKIE_MISSING")
    clean_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise AuthError("BROWSER_AUTH_COOKIE_RECORD_INVALID")
        domain = record.get("domain")
        name = record.get("name")
        value = record.get("value")
        if (
            not isinstance(domain, str)
            or domain.lstrip(".").lower() != "chatgpt.com"
            and not domain.lstrip(".").lower().endswith(".chatgpt.com")
            or not isinstance(name, str)
            or name not in cookies
            or not isinstance(value, str)
            or cookies[name] != value
        ):
            raise AuthError("BROWSER_AUTH_COOKIE_RECORD_INVALID")
        clean_records.append(dict(record))

    try:
        prior = AuthData.from_json(path) if path.exists() else AuthData()
    except (OSError, ValueError) as error:
        raise AuthError("BROWSER_AUTH_EXISTING_FILE_INVALID") from error

    auth = AuthData(
        accessToken=access_token,
        accessTokenSource="browser-native-auth-sync",
        cookies=cookies,
        browserCookies=clean_records,
        headers=prior.headers,
        expires=expires,
    )
    if persist:
        persist_auth_data(
            auth,
            path,
            session_token=session_token,
            session_expires_at=expires,
        )
    return BrowserAuthSyncResult(auth=auth, persisted=bool(persist), auth_file=path)
