from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import auth_browser
from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.exceptions import AuthError


class FakePage:
    async def get(self, url):
        assert url in {"https://chatgpt.com/", "about:blank"}
        return self

    async def evaluate(self, expression, **kwargs):
        if "api/auth/session" in expression:
            return {
                "status": 200,
                "body": {
                    "accessToken": "browser-access",
                    "sessionToken": "browser-session-json",
                    "expires": "2030-01-01T00:00:00.000Z",
                },
            }
        return "Browser Test Agent"

    async def send(self, command):
        return [
            SimpleNamespace(
                domain=".chatgpt.com",
                name=CHATGPT_SESSION_COOKIE,
                value="browser-session-cookie",
            ),
            SimpleNamespace(domain=".chatgpt.com", name="oai-did", value="device-1"),
            SimpleNamespace(domain="example.com", name="ignored", value="outside"),
        ]


class FakeBrowser:
    def __init__(self):
        self.page = FakePage()
        self.stopped = False

    async def get(self, url):
        assert url == "https://chatgpt.com/"
        return self.page

    async def stop(self):
        self.stopped = True


def test_browser_login_captures_and_persists_reusable_session(tmp_path, monkeypatch) -> None:
    browser = FakeBrowser()

    async def start(**kwargs):
        assert kwargs["user_data_dir"] == str(tmp_path / "profile")
        assert kwargs["headless"] is False
        return browser

    fake_zendriver = SimpleNamespace(
        start=start,
        cdp=SimpleNamespace(
            network=SimpleNamespace(
                get_all_cookies=lambda: "get-all-cookies",
                CookieParam=lambda **kwargs: kwargs,
                set_cookies=lambda cookies: ("set-cookies", cookies),
                TimeSinceEpoch=float,
            )
        ),
    )
    monkeypatch.setattr(auth_browser, "_import_zendriver", lambda: fake_zendriver)

    result = auth_browser.browser_login(
        tmp_path / "auth.json",
        profile_dir=tmp_path / "profile",
        timeout=1,
    )

    saved = json.loads((tmp_path / "auth.json").read_text(encoding="utf-8"))
    assert browser.stopped is True
    assert result.auth.accessToken == "browser-access"
    assert result.auth.cookies[CHATGPT_SESSION_COOKIE] == "browser-session-cookie"
    assert result.auth.cookies["oai-did"] == "device-1"
    assert "ignored" not in result.auth.cookies
    assert saved["sessionToken"] == "browser-session-json"
    assert saved["sessionExpiresAt"] == "2030-01-01T00:00:00.000Z"
    assert saved["headers"]["user-agent"] == "Browser Test Agent"
    assert "proof_token" not in saved
    assert "turnstile_token" not in saved


def test_browser_login_seeds_existing_session_into_persistent_profile(
    tmp_path, monkeypatch
) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "sessionToken": "existing-session",
            }
        ),
        encoding="utf-8",
    )
    browser = FakeBrowser()
    started_urls = []
    commands = []

    async def start(**kwargs):
        return browser

    async def browser_get(url):
        started_urls.append(url)
        return browser.page

    async def page_send(command):
        commands.append(command)
        if command == "get-all-cookies":
            return [
                SimpleNamespace(
                    domain=".chatgpt.com",
                    name=CHATGPT_SESSION_COOKIE,
                    value="browser-session-cookie",
                )
            ]
        return None

    browser.get = browser_get
    browser.page.send = page_send
    fake_network = SimpleNamespace(
        CookieParam=lambda **kwargs: kwargs,
        set_cookies=lambda cookies: ("set-cookies", cookies),
        delete_cookies=lambda name, **kwargs: ("delete-cookie", name),
        get_all_cookies=lambda: "get-all-cookies",
        TimeSinceEpoch=float,
    )
    monkeypatch.setattr(
        auth_browser,
        "_import_zendriver",
        lambda: SimpleNamespace(
            start=start,
            cdp=SimpleNamespace(network=fake_network),
        ),
    )

    auth_browser.browser_login(
        auth_file,
        profile_dir=tmp_path / "profile",
        timeout=1,
    )

    assert started_urls == ["about:blank"]
    seed_command = next(command for command in commands if command[0] == "set-cookies")
    assert seed_command[1][0]["value"] == "existing-session"


def test_browser_login_rejects_active_event_loop() -> None:
    async def run() -> None:
        with pytest.raises(AuthError, match="active asyncio event loop"):
            auth_browser.browser_login(timeout=1)

    import asyncio

    asyncio.run(run())


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"status": 401, "body": {}}, {"status": 200, "body": {}}],
)
def test_valid_session_payload_rejects_incomplete_auth(payload) -> None:
    assert auth_browser._valid_session_payload(payload) is None


def test_session_expiry_timestamp_parses_chatgpt_iso_value() -> None:
    assert auth_browser._session_expiry_timestamp("2030-01-01T00:00:00.000Z") == 1893456000
