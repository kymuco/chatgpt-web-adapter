from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import AuthError
from .types import AuthData

CHAT_URL = "https://chatgpt.com/"
DEFAULT_AUTH_FILE = Path("auth_data.json")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
CHATGPT_SESSION_COOKIE = "__Secure-next-auth.session-token"


def _iter_env_candidates(auth_path: Path) -> list[Path]:
    module_dir = Path(__file__).resolve().parent
    candidates = [
        Path.cwd() / ".env",
        auth_path.parent / ".env",
        module_dir / ".env",
        module_dir.parent / ".env",
        module_dir.parent.parent / ".env",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _load_access_token(auth_path: Path) -> str | None:
    if os.getenv("accessToken"):
        return os.getenv("accessToken")
    for env_path in _iter_env_candidates(auth_path):
        if not env_path.is_file():
            continue
        try:
            text = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() != "accessToken":
                continue
            token = value.strip().strip("'").strip('"')
            if token:
                return token
    return None


def _get_access_token_expiry(access_token: str | None) -> datetime | None:
    if not access_token or access_token.count(".") < 2:
        return None
    try:
        payload = access_token.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(int(exp), tz=timezone.utc)
    except Exception:
        return None


def _has_session_cookie(auth: AuthData) -> bool:
    return any(
        name == CHATGPT_SESSION_COOKIE or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for name in auth.cookies
    )


def _seed_session_cookie_from_auth_file(auth: AuthData, auth_path: Path) -> None:
    """Best-effort mapping for a raw ``/api/auth/session`` JSON dump.

    ChatGPT's session endpoint exposes ``sessionToken`` while browser requests use
    the NextAuth session cookie. Explicit cookies always win, including chunked
    ``.0``/``.1`` variants copied from a browser.
    """

    if _has_session_cookie(auth) or not auth_path.is_file():
        return
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(payload, dict):
        return
    session_token = payload.get("sessionToken")
    if isinstance(session_token, str) and session_token.strip():
        auth.cookies[CHATGPT_SESSION_COOKIE] = session_token.strip()


def load_auth_data(auth_file: str | Path = DEFAULT_AUTH_FILE) -> AuthData:
    auth_path = Path(auth_file)
    try:
        auth = AuthData.from_json(auth_path)
    except FileNotFoundError:
        auth = AuthData()
    except OSError as error:
        raise AuthError(f"Failed to read auth data from {auth_path}: {error}") from error
    except ValueError as error:
        raise AuthError(f"Failed to parse auth data from {auth_path}: {error}") from error

    _seed_session_cookie_from_auth_file(auth, auth_path)

    candidates: list[tuple[str, str]] = []
    if auth.accessToken:
        candidates.append((f"{auth_path.name}:accessToken", auth.accessToken))
    env_access_token = _load_access_token(auth_path)
    if env_access_token and env_access_token != auth.accessToken:
        candidates.append((".env:accessToken", env_access_token))

    expired_sources: list[str] = []
    now_utc = datetime.now(timezone.utc)
    for source, token in candidates:
        expires_at = _get_access_token_expiry(token)
        if expires_at is not None and expires_at <= now_utc:
            expires_local = expires_at.astimezone()
            expired_sources.append(
                f"{source} expired at {expires_local.strftime('%Y-%m-%d %H:%M:%S %z')}"
            )
            continue
        auth.accessToken = token
        auth.accessTokenSource = source
        break

    if not auth.accessToken:
        if expired_sources:
            raise AuthError(
                "All available access tokens are expired: "
                + "; ".join(expired_sources)
                + ". Refresh authorization before using the adapter."
            )
        raise AuthError(
            f"No access token found. Expected accessToken in {auth_path.name}"
            " or accessToken in .env."
        )
    return auth


def build_base_headers(auth: AuthData) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in auth.headers.items():
        if key is None or value is None:
            continue
        key_str = str(key).lower()
        if key_str in {"authorization", "cookie"}:
            continue
        headers[key_str] = str(value)
    device_id = auth.cookies.get("oai-did")
    if isinstance(device_id, str) and device_id.strip():
        headers.setdefault("oai-device-id", device_id.strip())
    headers.setdefault("accept", "*/*")
    headers.setdefault("accept-language", "en-US,en;q=0.8")
    headers.setdefault("content-type", "application/json")
    headers.setdefault("referer", CHAT_URL)
    headers.setdefault("user-agent", DEFAULT_USER_AGENT)
    return headers
