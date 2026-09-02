from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import CHATGPT_SESSION_COOKIE, _get_access_token_expiry
from .exceptions import AuthError

_AUTH_FILE_LOCK = threading.Lock()


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


def persist_auth_data(
    auth: Any,
    auth_file: str | Path,
    *,
    session_token: str | None = None,
    session_expires_at: Any = None,
    replace: bool = False,
    auth_source: str | None = None,
) -> Path:
    """Atomically persist reusable auth state while preserving unknown fields."""

    path = Path(auth_file)
    with _AUTH_FILE_LOCK:
        try:
            current = (
                {}
                if replace
                else json.loads(path.read_text(encoding="utf-8"))
                if path.is_file()
                else {}
            )
        except (OSError, ValueError) as error:
            raise AuthError(f"Failed to read auth data before saving: {error}") from error
        if not isinstance(current, dict):
            current = {}

        access_token = getattr(auth, "accessToken", None)
        cookies = dict(getattr(auth, "cookies", {}) or {})
        browser_cookies = [
            dict(item)
            for item in (getattr(auth, "browserCookies", []) or [])
            if isinstance(item, dict)
        ]
        headers = dict(getattr(auth, "headers", {}) or {})
        if isinstance(access_token, str) and access_token.strip():
            current["accessToken"] = access_token.strip()
            access_expires = _get_access_token_expiry(access_token)
            if access_expires is not None:
                current["accessTokenExpiresAt"] = access_expires.isoformat().replace(
                    "+00:00", "Z"
                )
        if session_token is None:
            cookie_token = cookies.get(CHATGPT_SESSION_COOKIE)
            if isinstance(cookie_token, str) and cookie_token.strip():
                session_token = cookie_token
        if isinstance(session_token, str) and session_token.strip():
            current["sessionToken"] = session_token.strip()
        if session_expires_at is None:
            session_expires_at = getattr(auth, "expires", None)
        if session_expires_at is not None:
            current["expires"] = session_expires_at
            current["sessionExpiresAt"] = session_expires_at
        current["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        current["cookies"] = cookies
        current["browserCookies"] = browser_cookies
        current["headers"] = headers
        if isinstance(auth_source, str) and auth_source.strip():
            current["authSource"] = auth_source.strip()
        current.pop("proof_token", None)
        current.pop("turnstile_token", None)
        _atomic_write_json(path, current)
    return path
