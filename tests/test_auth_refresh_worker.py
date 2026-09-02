from __future__ import annotations

import json
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chatgpt_web_adapter import auth_refresh_worker
from chatgpt_web_adapter.auth import CHATGPT_SESSION_COOKIE


class FakeSessionResponse:
    status = 200

    def __init__(self, payload: bytes | None = None) -> None:
        self.headers = Message()
        self.headers.add_header(
            "set-cookie",
            f"{CHATGPT_SESSION_COOKIE}=rotated-cookie; Path=/; Secure",
        )
        self.headers.add_header("set-cookie", "_puid=browser-owned; Path=/; Secure")
        self._payload = payload or json.dumps(
            {
                "accessToken": "new-access",
                "sessionToken": "new-session",
                "expires": "2030-01-01T00:00:00.000Z",
                "user": {"private": "must-not-cross-worker-boundary"},
            }
        ).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def test_worker_reduces_headers_cookies_and_session_response(monkeypatch) -> None:
    captured = {}

    class FakeOpener:
        def open(self, request, *, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = {key.lower(): value for key, value in request.header_items()}
            return FakeSessionResponse()

    monkeypatch.setattr(
        auth_refresh_worker,
        "build_opener",
        lambda *handlers: FakeOpener(),
    )

    result = auth_refresh_worker.fetch_session(
        {
            "cookie": (
                f"{CHATGPT_SESSION_COOKIE}=private-session; "
                "oai-did=device; cf_clearance=must-not-cross"
            ),
            "authorization": "Bearer must-not-cross",
            "user-agent": "pytest-agent",
            "accept-encoding": "identity",
        },
        19.0,
    )

    assert captured["url"] == auth_refresh_worker.SESSION_URL
    assert captured["timeout"] == 19.0
    assert "authorization" not in captured["headers"]
    assert "cf_clearance" not in captured["headers"]["cookie"]
    assert captured["headers"]["cookie"] == (
        f"{CHATGPT_SESSION_COOKIE}=private-session; oai-did=device"
    )
    assert result == {
        "status": 200,
        "data": {
            "accessToken": "new-access",
            "sessionToken": "new-session",
            "expires": "2030-01-01T00:00:00.000Z",
        },
        "set_cookie_headers": [
            f"{CHATGPT_SESSION_COOKIE}=rotated-cookie; Path=/; Secure"
        ],
    }


def test_worker_does_not_forward_credentials_across_redirect(monkeypatch) -> None:
    requests = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(
                {
                    "path": self.path,
                    "cookie": self.headers.get("cookie"),
                    "authorization": self.headers.get("authorization"),
                }
            )
            if self.path == "/source":
                self.send_response(302)
                self.send_header(
                    "location",
                    f"http://127.0.0.1:{self.server.server_port}/destination",
                )
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    monkeypatch.setattr(
        auth_refresh_worker,
        "SESSION_URL",
        f"http://127.0.0.1:{server.server_port}/source",
    )
    try:
        result = auth_refresh_worker.fetch_session(
            {
                "cookie": f"{CHATGPT_SESSION_COOKIE}=fake-private-session",
                "authorization": "Bearer fake-private-access",
            },
            2.0,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)

    assert result == {"status": 302, "data": None, "set_cookie_headers": []}
    assert requests == [
        {
            "path": "/source",
            "cookie": f"{CHATGPT_SESSION_COOKIE}=fake-private-session",
            "authorization": None,
        }
    ]


def test_worker_redacts_header_validation_failure(monkeypatch) -> None:
    class InvalidHeaderOpener:
        def open(self, request, *, timeout):
            raise ValueError("Invalid header value b'private-session-value'")

    monkeypatch.setattr(
        auth_refresh_worker,
        "build_opener",
        lambda *handlers: InvalidHeaderOpener(),
    )

    result = auth_refresh_worker.fetch_session(
        {"cookie": f"{CHATGPT_SESSION_COOKIE}=private-session-value"},
        19.0,
    )

    assert result == {"status": 0, "data": None, "set_cookie_headers": []}
    assert "private-session-value" not in json.dumps(result)


def test_worker_rejects_response_body_over_bound(monkeypatch) -> None:
    payload = b"x" * (auth_refresh_worker.MAX_RESPONSE_BYTES + 1)

    class FakeOpener:
        def open(self, request, *, timeout):
            return FakeSessionResponse(payload)

    monkeypatch.setattr(
        auth_refresh_worker,
        "build_opener",
        lambda *handlers: FakeOpener(),
    )

    result = auth_refresh_worker.fetch_session(
        {"cookie": f"{CHATGPT_SESSION_COOKIE}=private-session"},
        19.0,
    )

    assert result == {"status": 200, "data": None, "set_cookie_headers": []}


def test_worker_rejects_cookie_input_without_session_material(monkeypatch) -> None:
    called = False

    class FakeOpener:
        def open(self, request, *, timeout):
            nonlocal called
            called = True
            return FakeSessionResponse()

    monkeypatch.setattr(
        auth_refresh_worker,
        "build_opener",
        lambda *handlers: FakeOpener(),
    )

    result = auth_refresh_worker.fetch_session(
        {"cookie": "cf_clearance=browser-owned"},
        19.0,
    )

    assert result == {"status": 0, "data": None, "set_cookie_headers": []}
    assert called is False
