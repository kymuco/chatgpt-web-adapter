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

    assert auth.api_key == "not.a.jwt"
    assert auth.api_key_source == ".env:accessToken"
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
