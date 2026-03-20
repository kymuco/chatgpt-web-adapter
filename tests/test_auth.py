from __future__ import annotations

import webchat_adapter as adapter
import pytest


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
