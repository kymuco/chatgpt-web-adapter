from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import auth_refresh
from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE
from chatgpt_web_adapter.auth_refresh import refresh_auth_session


class RefreshClient:
    def __init__(self, auth_file) -> None:
        self.auth_file = auth_file
        self.auth = SimpleNamespace(
            accessToken="old-access",
            accessTokenSource="file",
            expires=None,
            cookies={
                CHATGPT_SESSION_COOKIE: "old-session",
                "oai-did": "device",
                "cf_clearance": "browser-owned-protection-state",
            },
            headers={"user-agent": "pytest"},
        )
        self.base_headers = {
            "user-agent": "pytest-agent",
            "accept-language": "en-US,en;q=0.8",
            "authorization": "Bearer must-not-cross",
            "x-unrelated-secret": "must-not-cross",
        }
        self.timeout = 17
        self.response_headers = None

    def _json_request(self, *args, **kwargs):
        raise AssertionError("session refresh must not use generic curl JSON transport")

    def _update_cookies_from_text(self, header_text):
        self.response_headers = header_text
        if "rotated-session" in header_text:
            self.auth.cookies[CHATGPT_SESSION_COOKIE] = "rotated-session"


def test_refresh_auth_uses_bounded_worker_and_atomically_persists(
    tmp_path, monkeypatch
) -> None:
    captured = {}

    def run_worker(command, *, input, stdout, stderr, timeout, check):
        captured["command"] = command
        captured["request"] = json.loads(input)
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["timeout"] = timeout
        captured["check"] = check
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": 200,
                    "data": {
                        "accessToken": "new-access",
                        "sessionToken": "new-session",
                        "expires": "2030-01-01T00:00:00.000Z",
                    },
                    "set_cookie_headers": [
                        f"{CHATGPT_SESSION_COOKIE}=rotated-session; Path=/; Secure",
                        "_puid=must-not-be-applied; Path=/; Secure",
                    ],
                }
            ).encode(),
        )

    monkeypatch.setattr(auth_refresh.subprocess, "run", run_worker)
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

    request_headers = captured["request"]["headers"]
    assert captured["command"] == [
        auth_refresh.sys.executable,
        "-m",
        auth_refresh.AUTH_REFRESH_WORKER_MODULE,
    ]
    assert "old-session" not in " ".join(captured["command"])
    assert "authorization" not in request_headers
    assert "x-unrelated-secret" not in request_headers
    assert "cf_clearance" not in request_headers["cookie"]
    assert request_headers["cookie"] == (
        f"{CHATGPT_SESSION_COOKIE}=old-session; oai-did=device"
    )
    assert request_headers["user-agent"] == "pytest-agent"
    assert request_headers["accept-encoding"] == "identity"
    assert captured["request"]["timeout"] == 17.0
    assert captured["stdout"] is subprocess.PIPE
    assert captured["stderr"] is subprocess.DEVNULL
    assert captured["timeout"] == 17.0
    assert captured["check"] is False

    saved = json.loads(auth_file.read_text(encoding="utf-8"))
    assert result.session_token_rotated is True
    assert result.persisted is True
    assert client.auth.accessToken == "new-access"
    assert client.response_headers == (
        f"set-cookie: {CHATGPT_SESSION_COOKIE}=rotated-session; Path=/; Secure"
    )
    assert client.auth.cookies[CHATGPT_SESSION_COOKIE] == "rotated-session"
    assert saved["accessToken"] == "new-access"
    assert saved["sessionToken"] == "new-session"
    assert saved["cookies"][CHATGPT_SESSION_COOKIE] == "rotated-session"
    assert saved["account"] == {"id": "preserve-me"}
    assert "proof_token" not in saved
    assert "turnstile_token" not in saved
    assert not list(tmp_path.glob("*.tmp"))


def test_refresh_auth_preserves_reduced_worker_http_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_refresh.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b'{"status":403,"data":null,"set_cookie_headers":[]}',
        ),
    )
    client = RefreshClient(tmp_path / "auth_data.json")

    with pytest.raises(auth_refresh.AuthError, match=r"status=403$"):
        refresh_auth_session(client, persist=False)


def test_refresh_auth_enforces_total_worker_deadline(tmp_path, monkeypatch) -> None:
    def time_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(auth_refresh.subprocess, "run", time_out)
    client = RefreshClient(tmp_path / "auth_data.json")

    with pytest.raises(
        auth_refresh.AuthError,
        match="failed before receiving an HTTP response",
    ):
        refresh_auth_session(client, persist=False)


def test_refresh_auth_rejects_oversized_worker_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_refresh.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b"x" * (auth_refresh.AUTH_REFRESH_MAX_WORKER_OUTPUT_BYTES + 1),
        ),
    )
    client = RefreshClient(tmp_path / "auth_data.json")

    with pytest.raises(auth_refresh.AuthError, match="returned an invalid response"):
        refresh_auth_session(client, persist=False)


def test_refresh_auth_requires_session_cookie_before_worker(tmp_path, monkeypatch) -> None:
    called = False

    def forbidden_worker(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("worker must not run")

    monkeypatch.setattr(auth_refresh.subprocess, "run", forbidden_worker)
    client = RefreshClient(tmp_path / "auth_data.json")
    client.auth.cookies = {"oai-did": "device"}

    with pytest.raises(
        auth_refresh.AuthError,
        match="requires a ChatGPT session cookie",
    ):
        refresh_auth_session(client, persist=False)
    assert called is False
