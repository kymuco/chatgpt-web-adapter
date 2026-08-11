from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import CHATGPT_SESSION_COOKIE, CHAT_URL, DEFAULT_AUTH_FILE, load_auth_data
from .auth_store import persist_auth_data
from .exceptions import AuthError
from .types import AuthData

SESSION_SCRIPT = """
fetch('/api/auth/session', {credentials: 'include', cache: 'no-store'})
  .then(async response => ({status: response.status, body: await response.json()}))
  .catch(error => ({status: 0, error: String(error)}))
"""


@dataclass(frozen=True)
class BrowserLoginResult:
    auth: AuthData
    auth_file: Path
    profile_dir: Path
    persisted: bool


def default_browser_profile_dir() -> Path:
    configured = os.getenv("CHATGPT_WEB_ADAPTER_PROFILE_DIR")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return root / "chatgpt-web-adapter" / "browser-profile"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "chatgpt-web-adapter" / "browser-profile"
    state_root = Path(os.getenv("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return state_root / "chatgpt-web-adapter" / "browser-profile"


def _import_zendriver() -> Any:
    try:
        import zendriver
    except ImportError as error:
        raise AuthError(
            "Browser login requires the optional browser extra: "
            "pip install 'chatgpt-web-adapter[browser]'"
        ) from error
    return zendriver


def _cookie_dict(browser_cookies: Any) -> dict[str, str]:
    captured: dict[str, str] = {}
    if not isinstance(browser_cookies, list):
        return captured
    for cookie in browser_cookies:
        domain = getattr(cookie, "domain", "")
        name = getattr(cookie, "name", None)
        value = getattr(cookie, "value", None)
        if (
            isinstance(domain, str)
            and domain.lstrip(".").lower().endswith("chatgpt.com")
            and isinstance(name, str)
            and isinstance(value, str)
        ):
            captured[name] = value
    return captured


def _valid_session_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or int(value.get("status") or 0) != 200:
        return None
    body = value.get("body")
    if not isinstance(body, dict):
        return None
    access_token = body.get("accessToken")
    session_token = body.get("sessionToken")
    if not isinstance(access_token, str) or not access_token.strip():
        return None
    if not isinstance(session_token, str) or not session_token.strip():
        return None
    return body


def _session_expiry_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


async def _graceful_browser_stop(browser: Any, zendriver: Any) -> None:
    """Give Chromium time to flush a custom profile before zendriver terminates it."""

    connection = getattr(browser, "connection", None)
    process = getattr(browser, "_process", None)
    if connection is None or process is None:
        await browser.stop()
        return
    try:
        await connection.send(zendriver.cdp.browser.close())
        for _ in range(100):
            if getattr(process, "returncode", None) is not None:
                break
            await asyncio.sleep(0.1)
    except Exception:
        pass
    await browser.stop()


async def _delete_session_cookies(page: Any, zendriver: Any, names: Any) -> None:
    for name in names:
        if name == CHATGPT_SESSION_COOKIE or str(name).startswith(
            f"{CHATGPT_SESSION_COOKIE}."
        ):
            for domain in ("chatgpt.com", ".chatgpt.com"):
                try:
                    await page.send(
                        zendriver.cdp.network.delete_cookies(
                            str(name), domain=domain, path="/"
                        )
                    )
                except Exception:
                    pass


async def _browser_login_async(
    *,
    auth_file: Path,
    profile_dir: Path,
    timeout: float,
    headless: bool,
    browser_executable_path: str | Path | None,
    persist: bool,
    reuse_existing_auth: bool,
) -> BrowserLoginResult:
    zendriver = _import_zendriver()
    profile_dir.mkdir(parents=True, exist_ok=True)
    browser = await zendriver.start(
        user_data_dir=str(profile_dir),
        headless=headless,
        browser_executable_path=browser_executable_path,
    )
    try:
        seed_cookies: dict[str, str] = {}
        seed_expires: float | None = None
        if reuse_existing_auth and auth_file.is_file():
            try:
                seed_auth = load_auth_data(
                    auth_file, allow_expired_session_refresh=True
                )
                seed_cookies = seed_auth.cookies
                seed_expires = _session_expiry_timestamp(seed_auth.expires)
            except (AuthError, OSError, ValueError):
                seed_cookies = {}
        if not reuse_existing_auth:
            page = await browser.get("about:blank")
            existing = await page.send(zendriver.cdp.network.get_all_cookies())
            await _delete_session_cookies(
                page,
                zendriver,
                [getattr(cookie, "name", "") for cookie in existing],
            )
            await page.get(CHAT_URL)
        elif seed_cookies:
            page = await browser.get("about:blank")
            await _delete_session_cookies(page, zendriver, seed_auth.cookies)
            cookie_params = [
                zendriver.cdp.network.CookieParam(
                    name=str(name),
                    value=str(value),
                    url=CHAT_URL,
                    secure=True,
                    expires=(
                        zendriver.cdp.network.TimeSinceEpoch(seed_expires)
                        if seed_expires is not None
                        else None
                    ),
                )
                for name, value in seed_cookies.items()
                if name is not None and value is not None
            ]
            await page.send(zendriver.cdp.network.set_cookies(cookie_params))
            await page.get(CHAT_URL)
        else:
            page = await browser.get(CHAT_URL)
        deadline = time.monotonic() + timeout
        seeded_session_deadline = time.monotonic() + 8.0 if seed_cookies else None
        cleared_invalid_seed = False
        session: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                session = _valid_session_payload(
                    await page.evaluate(
                        SESSION_SCRIPT,
                        await_promise=True,
                        return_by_value=True,
                    )
                )
            except Exception:
                session = None
            if session is not None:
                break
            if (
                seeded_session_deadline is not None
                and not cleared_invalid_seed
                and time.monotonic() >= seeded_session_deadline
            ):
                await _delete_session_cookies(page, zendriver, seed_auth.cookies)
                cleared_invalid_seed = True
                await page.get(CHAT_URL)
            await asyncio.sleep(1.0)
        if session is None:
            raise AuthError(
                "Browser login timed out. Complete sign-in in the opened ChatGPT window "
                "and keep it open until authorization is saved."
            )

        browser_cookies = await page.send(zendriver.cdp.network.get_all_cookies())
        cookies = _cookie_dict(browser_cookies)
        if not cookies:
            raise AuthError("Browser login succeeded but no ChatGPT cookies were captured")
        session_expiry = _session_expiry_timestamp(session.get("expires"))
        captured_session_cookies = {
            name: value
            for name, value in cookies.items()
            if name == CHATGPT_SESSION_COOKIE
            or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        }
        captured_session_objects = [
            cookie
            for cookie in browser_cookies
            if getattr(cookie, "name", "") == CHATGPT_SESSION_COOKIE
            or getattr(cookie, "name", "").startswith(f"{CHATGPT_SESSION_COOKIE}.")
        ]
        if any(
            getattr(cookie, "name", "").startswith(f"{CHATGPT_SESSION_COOKIE}.")
            for cookie in captured_session_objects
        ):
            await _delete_session_cookies(
                page, zendriver, [CHATGPT_SESSION_COOKIE]
            )
            cookies.pop(CHATGPT_SESSION_COOKIE, None)
            captured_session_cookies.pop(CHATGPT_SESSION_COOKIE, None)
            captured_session_objects = [
                cookie
                for cookie in captured_session_objects
                if getattr(cookie, "name", "") != CHATGPT_SESSION_COOKIE
            ]
        user_agent = await page.evaluate(
            "window.navigator.userAgent", return_by_value=True
        )
        if captured_session_cookies and session_expiry is not None:
            await page.get("about:blank")
            await page.send(
                zendriver.cdp.network.set_cookies(
                    [
                        zendriver.cdp.network.CookieParam(
                            name=str(getattr(cookie, "name")),
                            value=str(getattr(cookie, "value")),
                            domain=str(getattr(cookie, "domain")),
                            path=str(getattr(cookie, "path", "/")),
                            secure=bool(getattr(cookie, "secure", True)),
                            http_only=bool(getattr(cookie, "http_only", True)),
                            expires=zendriver.cdp.network.TimeSinceEpoch(
                                session_expiry
                            ),
                        )
                        for cookie in captured_session_objects
                    ]
                )
            )
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.8",
            "referer": CHAT_URL,
        }
        if isinstance(user_agent, str) and user_agent.strip():
            headers["user-agent"] = user_agent.strip()
        auth = AuthData(
            accessToken=session["accessToken"].strip(),
            accessTokenSource="browser-login:accessToken",
            cookies=cookies,
            headers=headers,
            expires=session.get("expires"),
        )
        if persist:
            persist_auth_data(
                auth,
                auth_file,
                session_token=session["sessionToken"].strip(),
                session_expires_at=session.get("expires"),
            )
        return BrowserLoginResult(
            auth=auth,
            auth_file=auth_file,
            profile_dir=profile_dir,
            persisted=bool(persist),
        )
    finally:
        await _graceful_browser_stop(browser, zendriver)


def browser_login(
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    *,
    profile_dir: str | Path | None = None,
    timeout: float = 300.0,
    headless: bool = False,
    browser_executable_path: str | Path | None = None,
    persist: bool = True,
    reuse_existing_auth: bool = True,
) -> BrowserLoginResult:
    """Open ChatGPT once, wait for sign-in, and persist reusable session auth."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            _browser_login_async(
                auth_file=Path(auth_file),
                profile_dir=Path(profile_dir) if profile_dir is not None else default_browser_profile_dir(),
                timeout=float(timeout),
                headless=bool(headless),
                browser_executable_path=browser_executable_path,
                persist=bool(persist),
                reuse_existing_auth=bool(reuse_existing_auth),
            )
        )
    raise AuthError("Synchronous browser_login cannot run inside an active asyncio event loop")
