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


def get_auth_status(auth_file: str | Path = DEFAULT_AUTH_FILE) -> AuthStatus:
    path = Path(auth_file)
    if not path.is_file():
        return AuthStatus(path, False, False, None, True, False, None)
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
    return AuthStatus(
        auth_file=path,
        file_exists=True,
        access_token_present=bool(auth.accessToken),
        access_token_expires_at=expires_at,
        access_token_needs_refresh=auth_needs_refresh(auth.accessToken),
        session_cookie_present=has_session,
        session_expires_at=auth.expires,
    )
