from __future__ import annotations

import json

from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.auth_status import get_auth_status


def test_auth_status_reports_missing_file_without_secrets(tmp_path) -> None:
    status = get_auth_status(tmp_path / "missing.json")
    assert status.file_exists is False
    assert status.access_token_needs_refresh is True
    assert status.session_cookie_present is False


def test_auth_status_reports_refreshable_session(tmp_path) -> None:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps(
            {
                "accessToken": "not.a.jwt",
                "cookies": {CHATGPT_SESSION_COOKIE: "secret"},
                "expires": "2030-01-01T00:00:00.000Z",
            }
        ),
        encoding="utf-8",
    )
    status = get_auth_status(path)
    assert status.file_exists is True
    assert status.access_token_present is True
    assert status.access_token_needs_refresh is False
    assert status.session_cookie_present is True
    assert status.session_expires_at == "2030-01-01T00:00:00.000Z"


def test_auth_status_accepts_top_level_session_token(tmp_path) -> None:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps({"accessToken": "not.a.jwt", "sessionToken": "secret"}),
        encoding="utf-8",
    )
    assert get_auth_status(path).session_cookie_present is True
