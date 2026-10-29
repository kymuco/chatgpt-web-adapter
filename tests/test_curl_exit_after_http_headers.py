"""curl exit status is authoritative even when HTTP headers say 200.

These tests use only a fake subprocess and disposable temporary headers.
No network, auth, Sentinel or conversation request is performed.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import RequestError
from chatgpt_web_adapter import legacy_client_core as core


def _client():
    client = core.ChatGPTWebClient.__new__(core.ChatGPTWebClient)
    client.curl_bin = "curl"
    client.timeout = 4
    client.debug_trace_dir = None
    client.auth = SimpleNamespace(cookies={})
    return client


def _fake_curl(monkeypatch, *, status, exit_code, body):
    def run(command, *, capture_output):
        assert capture_output is True
        header_path = Path(command[command.index("-D") + 1])
        header_path.write_text(
            f"HTTP/2 {status}\r\n"
            "content-type: application/json\r\n"
            "set-cookie: session=untrusted-partial; Path=/\r\n\r\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            returncode=exit_code,
            stdout=body,
            stderr=b"curl: fake-error secret-not-for-user",
        )

    monkeypatch.setattr(core.subprocess, "run", run)


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        (200, 18),  # partial transfer after valid response headers
        (200, 28),  # timeout after headers
        (200, 56),  # recv failure after headers
        (0, 6),     # no HTTP response headers
    ],
)
def test_nonzero_curl_exit_rejected_before_json_and_cookie_update(
    monkeypatch, status, exit_code
):
    _fake_curl(
        monkeypatch,
        status=status,
        exit_code=exit_code,
        body=b'{"prepare_token": "partial-secret"',
    )
    client = _client()
    with pytest.raises(RequestError) as caught:
        client._json_request(
            "POST", "https://example.invalid/prepare", {"p": "fake"}, {}
        )
    error = caught.value
    assert f"exit_code={exit_code}" in str(error)
    assert f"http_status={status}" in str(error)
    assert error.status_code == (status or None)
    assert error.request_stage == "transport"
    assert error.body_preview is None
    assert "partial-secret" not in str(error)
    assert "secret-not-for-user" not in str(error)
    assert client.auth.cookies == {}


def test_successful_curl_still_parses_json_and_persists_cookies(monkeypatch):
    _fake_curl(
        monkeypatch,
        status=200,
        exit_code=0,
        body=b'{"answer": "ok"}',
    )
    client = _client()
    status, data = client._json_request(
        "GET", "https://example.invalid/resource", None, {}
    )
    assert status == 200
    assert data == {"answer": "ok"}
    assert client.auth.cookies == {"session": "untrusted-partial"}


def test_http_200_non_json_success_is_still_returned_as_text(monkeypatch):
    _fake_curl(
        monkeypatch,
        status=200,
        exit_code=0,
        body=b"<html>fake non-json response</html>",
    )
    client = _client()
    status, data = client._json_request(
        "GET", "https://example.invalid/resource", None, {}
    )
    assert status == 200
    assert data == "<html>fake non-json response</html>"
