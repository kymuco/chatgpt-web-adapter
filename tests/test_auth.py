from __future__ import annotations

import base64
import json

import chatgpt_web_adapter as adapter
import pytest

from chatgpt_web_adapter.auth import build_base_headers


def _expired_access_token() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("ascii").rstrip("=")
    payload = base64.urlsafe_b64encode(b'{"exp":1}').decode("ascii").rstrip("=")
    return f"{header}.{payload}.signature"


def test_load_auth_data_uses_env_token_when_auth_file_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("accessToken", raising=False)
    (tmp_path / ".env").write_text("accessToken=not.a.jwt\n", encoding="utf-8")

    auth = adapter.load_auth_data(tmp_path / "missing_auth.json")

    assert auth.accessToken == "not.a.jwt"
    assert auth.accessTokenSource == ".env:accessToken"
    assert auth.cookies == {}
    assert auth.headers == {}


def test_load_auth_data_without_sources_raises_auth_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("accessToken", raising=False)

    with pytest.raises(adapter.AuthError, match="No access token found"):
        adapter.load_auth_data(tmp_path / "missing_auth.json")


def test_load_auth_data_does_not_cache_dotenv_token_across_projects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("accessToken", raising=False)

    project_one = tmp_path / "project-one"
    project_two = tmp_path / "project-two"
    project_one.mkdir()
    project_two.mkdir()
    (project_one / ".env").write_text("accessToken=token-one\n", encoding="utf-8")
    (project_two / ".env").write_text("accessToken=token-two\n", encoding="utf-8")

    auth_one = adapter.load_auth_data(project_one / "missing_auth.json")
    auth_two = adapter.load_auth_data(project_two / "missing_auth.json")

    assert auth_one.accessToken == "token-one"
    assert auth_one.accessTokenSource == ".env:accessToken"
    assert auth_two.accessToken == "token-two"
    assert auth_two.accessTokenSource == ".env:accessToken"


def test_load_auth_data_accepts_legacy_api_key_field(tmp_path) -> None:
    auth_file = tmp_path / "auth_data.json"
    auth_file.write_text('{"api_key":"legacy-token"}', encoding="utf-8")

    auth = adapter.load_auth_data(auth_file)

    assert auth.accessToken == "legacy-token"
    assert auth.accessTokenSource == "auth_data.json:accessToken"
    assert auth.api_key == "legacy-token"


def test_auth_data_accepts_legacy_constructor_names() -> None:
    auth = adapter.AuthData(api_key="legacy-token", api_key_source="legacy-source")

    assert auth.accessToken == "legacy-token"
    assert auth.accessTokenSource == "legacy-source"
    assert auth.api_key == "legacy-token"
    assert auth.api_key_source == "legacy-source"


def test_load_auth_data_maps_raw_chatgpt_session_token_to_cookie(tmp_path) -> None:
    auth_file = tmp_path / "auth_data.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "sessionToken": "browser-session-token",
                "user": {"id": "redacted"},
                "account": {"id": "redacted"},
            }
        ),
        encoding="utf-8",
    )

    auth = adapter.load_auth_data(auth_file)

    assert auth.accessToken == "not.a.jwt"
    assert auth.cookies["__Secure-next-auth.session-token"] == "browser-session-token"


def test_explicit_chunked_browser_session_cookies_win_over_session_token(tmp_path) -> None:
    auth_file = tmp_path / "auth_data.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "sessionToken": "must-not-replace-explicit-cookie",
                "cookies": {
                    "__Secure-next-auth.session-token.0": "chunk-zero",
                    "__Secure-next-auth.session-token.1": "chunk-one",
                },
            }
        ),
        encoding="utf-8",
    )

    auth = adapter.load_auth_data(auth_file)

    assert "__Secure-next-auth.session-token" not in auth.cookies
    assert auth.cookies["__Secure-next-auth.session-token.0"] == "chunk-zero"
    assert auth.cookies["__Secure-next-auth.session-token.1"] == "chunk-one"


def test_oai_did_cookie_seeds_device_header() -> None:
    auth = adapter.AuthData(
        accessToken="token",
        cookies={"oai-did": "device-id"},
    )

    headers = build_base_headers(auth)

    assert headers["oai-device-id"] == "device-id"


def test_expired_access_token_can_be_loaded_only_for_session_refresh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("accessToken", raising=False)
    auth_file = tmp_path / "auth_data.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": _expired_access_token(),
                "sessionToken": "refreshable-session",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(adapter.AuthError, match="expired"):
        adapter.load_auth_data(auth_file)

    auth = adapter.load_auth_data(auth_file, allow_expired_session_refresh=True)
    assert auth.accessToken is None
    assert auth.cookies["__Secure-next-auth.session-token"] == "refreshable-session"
