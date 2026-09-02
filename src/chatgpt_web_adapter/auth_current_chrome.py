from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import CHAT_URL, CHATGPT_SESSION_COOKIE, DEFAULT_AUTH_FILE
from .auth_store import persist_auth_data
from .browser_cookies import _is_chatgpt_cookie_domain, flatten_browser_cookies
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import AuthError, RequestError
from .types import AuthData

MAX_COOKIE_COUNT = 256
MAX_COOKIE_NAME_CHARS = 256
MAX_COOKIE_VALUE_CHARS = 32_768
MAX_COOKIE_DOMAIN_CHARS = 256
MAX_COOKIE_PATH_CHARS = 2_048
MAX_TOKEN_CHARS = 100_000


@dataclass(frozen=True, repr=False)
class CurrentChromeLoginResult:
    auth: AuthData
    auth_file: Path
    tab_id: int | None
    persisted: bool


def _bounded_string(
    value: Any,
    *,
    max_chars: int,
    required: bool = False,
) -> str | None:
    if not isinstance(value, str):
        if required:
            raise AuthError("Current Chrome authorization returned invalid data")
        return None
    if len(value) > max_chars or (required and not value.strip()):
        raise AuthError("Current Chrome authorization returned invalid data")
    return value


def _browser_cookies(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > MAX_COOKIE_COUNT:
        raise AuthError("Current Chrome authorization returned invalid cookies")
    records: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AuthError("Current Chrome authorization returned invalid cookies")
        name = _bounded_string(
            item.get("name"), max_chars=MAX_COOKIE_NAME_CHARS, required=True
        )
        cookie_value = _bounded_string(
            item.get("value"), max_chars=MAX_COOKIE_VALUE_CHARS
        )
        domain = _bounded_string(
            item.get("domain"), max_chars=MAX_COOKIE_DOMAIN_CHARS, required=True
        )
        path = _bounded_string(
            item.get("path", "/"), max_chars=MAX_COOKIE_PATH_CHARS, required=True
        )
        if cookie_value is None or not _is_chatgpt_cookie_domain(domain):
            raise AuthError("Current Chrome authorization returned invalid cookies")
        record: dict[str, Any] = {
            "name": name,
            "value": cookie_value,
            "domain": domain,
            "path": path,
        }
        for field in (
            "secure",
            "http_only",
            "same_site",
            "expires",
            "priority",
            "same_party",
            "source_scheme",
            "source_port",
        ):
            field_value = item.get(field)
            if isinstance(field_value, (str, int, float, bool)):
                record[field] = field_value
        records.append(record)
    return records


def _auth_from_capture(payload: Any) -> tuple[AuthData, str | None, int | None]:
    if not isinstance(payload, dict):
        raise AuthError("Current Chrome authorization returned invalid data")
    access_token = _bounded_string(
        payload.get("accessToken"), max_chars=MAX_TOKEN_CHARS, required=True
    )
    session_token = _bounded_string(
        payload.get("sessionToken"), max_chars=MAX_TOKEN_CHARS
    )
    browser_cookies = _browser_cookies(payload.get("browserCookies"))
    cookies = flatten_browser_cookies(browser_cookies)
    if not any(
        name == CHATGPT_SESSION_COOKIE or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for name in cookies
    ):
        raise AuthError("Current Chrome authorization returned no session cookie")
    user_agent = _bounded_string(payload.get("userAgent"), max_chars=2_048)
    expires = payload.get("expires")
    if isinstance(expires, str):
        expires = _bounded_string(expires, max_chars=256)
    elif not isinstance(expires, (int, float, type(None))):
        raise AuthError("Current Chrome authorization returned invalid data")
    if isinstance(expires, float) and not math.isfinite(expires):
        raise AuthError("Current Chrome authorization returned invalid data")
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.8",
        "referer": CHAT_URL,
    }
    if user_agent and user_agent.strip():
        headers["user-agent"] = user_agent.strip()
    tab_id = payload.get("tabId")
    return (
        AuthData(
            accessToken=access_token,
            accessTokenSource="current-chrome-tab:accessToken",
            cookies=cookies,
            browserCookies=browser_cookies,
            headers=headers,
            expires=expires,
        ),
        session_token.strip() if session_token and session_token.strip() else None,
        tab_id if isinstance(tab_id, int) and tab_id >= 0 else None,
    )


def browser_login_current_tab(
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    *,
    timeout: float = 300.0,
    persist: bool = True,
    fresh: bool = False,
    state_dir: str | Path | None = None,
) -> CurrentChromeLoginResult:
    """Authorize through a new tab in the connected, already-running Chrome.

    ``fresh`` never clears or imports browser cookies. Current Chrome remains the
    authority, and a successful capture replaces saved account credentials.
    """

    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number")
    if not isinstance(persist, bool) or not isinstance(fresh, bool):
        raise TypeError("persist and fresh must be bool")
    try:
        payload = BrowserNativeTurnProvider(state_dir=state_dir).capture_current_chrome_auth(
            timeout=float(timeout)
        )
    except (RequestError, OSError, ValueError):
        raise AuthError(
            "Current Chrome authorization failed at the browser bridge; "
            "ensure the CWA Native Messaging host and extension are connected"
        ) from None
    auth, session_token, tab_id = _auth_from_capture(payload)
    path = Path(auth_file)
    if persist:
        persist_auth_data(
            auth,
            path,
            session_token=session_token,
            session_expires_at=auth.expires,
            replace=True,
            auth_source="current-chrome-tab",
        )
    return CurrentChromeLoginResult(
        auth=auth,
        auth_file=path,
        tab_id=tab_id,
        persisted=persist,
    )
