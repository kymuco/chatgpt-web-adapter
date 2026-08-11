from __future__ import annotations

import json

from chatgpt_web_adapter import AuthData, BrowserLoginResult, ChatGPTWebClient
from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.exceptions import AuthError


def test_client_auto_login_bootstraps_missing_auth(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / "missing.json"
    captured = AuthData(
        accessToken="captured-token",
        cookies={CHATGPT_SESSION_COOKIE: "captured-session"},
    )

    def fake_login(path, **kwargs):
        assert path == auth_file
        return BrowserLoginResult(captured, auth_file, tmp_path / "profile", True)

    monkeypatch.setattr("chatgpt_web_adapter.auth_browser.browser_login", fake_login)
    client = ChatGPTWebClient(
        auth_file=auth_file,
        auto_login=True,
        auto_refresh_auth=False,
        curl_bin="curl",
    )
    assert client.auth is captured


def test_client_auto_login_recovers_failed_session_refresh(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": None,
                "cookies": {CHATGPT_SESSION_COOKIE: "dead-session"},
            }
        ),
        encoding="utf-8",
    )
    recovered = AuthData(
        accessToken="recovered-token",
        cookies={CHATGPT_SESSION_COOKIE: "recovered-session"},
    )

    monkeypatch.setattr(
        "chatgpt_web_adapter.auth_refresh.refresh_auth_session",
        lambda *args, **kwargs: (_ for _ in ()).throw(AuthError("session rejected")),
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.auth_browser.browser_login",
        lambda *args, **kwargs: BrowserLoginResult(
            recovered, auth_file, tmp_path / "profile", True
        ),
    )

    client = ChatGPTWebClient(auth_file=auth_file, auto_login=True, curl_bin="curl")
    assert client.auth is recovered
    assert client.base_headers["user-agent"]


def test_client_can_configure_persistent_sentinel_automatically(tmp_path) -> None:
    from chatgpt_web_adapter.browser_sentinel import ZendriverSentinelBundleProvider

    client = ChatGPTWebClient(
        auth=AuthData(
            accessToken="not.a.jwt",
            cookies={CHATGPT_SESSION_COOKIE: "session"},
        ),
        auto_refresh_auth=False,
        auto_sentinel=True,
        browser_profile_dir=tmp_path / "profile",
        sentinel_timeout=12,
        sentinel_max_attempts=3,
        sentinel_headless=True,
        curl_bin="curl",
    )

    provider = client._sentinel_bundle_provider
    assert isinstance(provider, ZendriverSentinelBundleProvider)
    assert provider.profile_dir == tmp_path / "profile"
    assert provider.timeout == 12
    assert provider.max_attempts == 3
    assert provider.headless is True
