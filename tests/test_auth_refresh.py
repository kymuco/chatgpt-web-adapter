from __future__ import annotations

import json
from types import SimpleNamespace

from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.auth_refresh import refresh_auth_session


class RefreshClient:
    def __init__(self, auth_file) -> None:
        self.auth_file = auth_file
        self.auth = SimpleNamespace(
            accessToken="old-access",
            accessTokenSource="file",
            expires=None,
            cookies={CHATGPT_SESSION_COOKIE: "old-session", "oai-did": "device"},
            headers={"user-agent": "pytest"},
        )
        self.base_headers = {}

    def _build_headers(self, extra):
        headers = {
            "authorization": f"Bearer {self.auth.accessToken}",
            "cookie": "; ".join(f"{key}={value}" for key, value in self.auth.cookies.items()),
        }
        headers.update({key: value for key, value in extra.items() if value is not None})
        return headers

    def _json_request(self, method, url, payload, headers):
        assert method == "GET"
        assert url.endswith("/api/auth/session")
        assert payload is None
        assert "old-session" in headers["cookie"]
        return 200, {
            "accessToken": "new-access",
            "sessionToken": "new-session",
            "expires": "2030-01-01T00:00:00.000Z",
            "user": {"id": "preserved-server-field"},
        }


def test_refresh_auth_rotates_and_atomically_persists_session(tmp_path) -> None:
    auth_file = tmp_path / "auth_data.json"
    auth_file.write_text(
        json.dumps(
            {
                "accessToken": "old-access",
                "sessionToken": "old-session",
                "account": {"id": "preserve-me"},
                "proof_token": ["must", "disappear"],
                "turnstile_token": "must-disappear",
            }
        ),
        encoding="utf-8",
    )
    client = RefreshClient(auth_file)

    result = refresh_auth_session(client)

    saved = json.loads(auth_file.read_text(encoding="utf-8"))
    assert result.session_token_rotated is True
    assert result.persisted is True
    assert client.auth.accessToken == "new-access"
    assert client.auth.cookies[CHATGPT_SESSION_COOKIE] == "new-session"
    assert saved["accessToken"] == "new-access"
    assert saved["sessionToken"] == "new-session"
    assert saved["account"] == {"id": "preserve-me"}
    assert saved["cookies"][CHATGPT_SESSION_COOKIE] == "new-session"
    assert "proof_token" not in saved
    assert "turnstile_token" not in saved
    assert not list(tmp_path.glob("*.tmp"))
