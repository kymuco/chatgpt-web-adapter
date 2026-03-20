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

    candidates: list[tuple[str, str]] = []
    if auth.api_key:
        candidates.append((f"{auth_path.name}:api_key", auth.api_key))
    env_api_key = _load_access_token(auth_path)
    if env_api_key and env_api_key != auth.api_key:
        candidates.append((".env:accessToken", env_api_key))

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
        auth.api_key = token
        auth.api_key_source = source
        break

    if not auth.api_key:
        if expired_sources:
            raise AuthError(
                "All available access tokens are expired: "
                + "; ".join(expired_sources)
                + ". Refresh authorization before using the adapter."
            )
        raise AuthError(
            f"No access token found. Expected api_key in {auth_path.name}"
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
    headers.setdefault("accept", "*/*")
    headers.setdefault("accept-language", "en-US,en;q=0.8")
    headers.setdefault("content-type", "application/json")
    headers.setdefault("referer", CHAT_URL)
    headers.setdefault("user-agent", DEFAULT_USER_AGENT)
    return headers
