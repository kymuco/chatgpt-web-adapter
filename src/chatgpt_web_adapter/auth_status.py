from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .auth import (
    CHATGPT_SESSION_COOKIE,
    DEFAULT_AUTH_FILE,
    _get_access_token_expiry,
)
from .auth_browser import default_browser_profile_dir
from .auth_refresh import auth_needs_refresh
from .types import AuthData


@dataclass(frozen=True)
class AuthStatus:
    auth_file: Path
    file_exists: bool
    access_token_present: bool
    access_token_expires_at: datetime | None
    access_token_needs_refresh: bool
    session_cookie_present: bool
    session_expires_at: Any = None
    browser_cookie_count: int = 0
    browser_profile_dir: Path | None = None
    browser_profile_exists: bool = False
    auth_source: str | None = None
    current_chrome_auth: bool = False


def get_auth_status(
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    *,
    profile_dir: str | Path | None = None,
) -> AuthStatus:
    path = Path(auth_file)
    profile = (
        Path(profile_dir)
        if profile_dir is not None
        else default_browser_profile_dir()
    )
    if not path.is_file():
        return AuthStatus(
            path, False, False, None, True, False, None, 0, profile, profile.is_dir()
        )
    auth = AuthData.from_json(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    has_session = any(
        name == CHATGPT_SESSION_COOKIE or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for name in auth.cookies
    )
    if not has_session and isinstance(raw, dict):
        session_token = raw.get("sessionToken")
        has_session = isinstance(session_token, str) and bool(session_token.strip())
    expires_at = _get_access_token_expiry(auth.accessToken)
    auth_source = raw.get("authSource") if isinstance(raw, dict) else None
    if not isinstance(auth_source, str) or not auth_source.strip():
        auth_source = None
    else:
        auth_source = auth_source.strip()
    return AuthStatus(
        auth_file=path,
        file_exists=True,
        access_token_present=bool(auth.accessToken),
        access_token_expires_at=expires_at,
        access_token_needs_refresh=auth_needs_refresh(auth.accessToken),
        session_cookie_present=has_session,
        session_expires_at=auth.expires,
        browser_cookie_count=len(auth.browserCookies),
        browser_profile_dir=profile,
        browser_profile_exists=profile.is_dir(),
        auth_source=auth_source,
        current_chrome_auth=auth_source == "current-chrome-tab",
    )
