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
