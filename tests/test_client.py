from __future__ import annotations

import io
import json
import shutil
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

import webchat_adapter as adapter
import webchat_adapter.client as client_mod
import pytest

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 40


def _build_client() -> adapter.ChatGPTWebClient:
    client = object.__new__(adapter.ChatGPTWebClient)
    client.auth = adapter.AuthData(cookies={})
    client.timeout = 10
    client.base_headers = {"user-agent": "pytest-agent"}
    client.curl_bin = shutil.which("curl.exe") or shutil.which("curl")
    client.prefetched_requirements = None
    client.prefetched_proof_header = None
    client.prefetched_ts = 0.0
    client._file_cache = {}
    if not client.curl_bin:
        raise RuntimeError("curl is required for tests")
    return client


@contextmanager
def _serve(handler_cls: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class CookieHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Set-Cookie", "session=internal; Path=/")
        self.end_headers()
        self.wfile.write(PNG_BYTES)

    def log_message(self, format: str, *args) -> None:
        return None


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{self.server.server_address[1]}/image.png",
            )
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Set-Cookie", "poisoned=1; Path=/")
        self.end_headers()
        self.wfile.write(PNG_BYTES)

    def log_message(self, format: str, *args) -> None:
        return None


def _patch_chat_endpoints(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    monkeypatch.setattr(client_mod, "CHAT_REQUIREMENTS_URL", f"{base_url}/backend-api/sentinel/chat-requirements")
    monkeypatch.setattr(client_mod, "CHAT_BACKEND_URL", f"{base_url}/backend-api/f/conversation")
    monkeypatch.setattr(client_mod, "CHAT_FILES_URL", f"{base_url}/backend-api/files")


def _make_chat_handler(
    state: dict[str, Any],
    *,
    backend_status: int = 200,
) -> type[BaseHTTPRequestHandler]:
    class ChatHandler(BaseHTTPRequestHandler):
        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(length) if length else b""

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path == "/backend-api/sentinel/chat-requirements":
                state["requirements_calls"] += 1
                self._write_json(
                    200,
                    {
                        "token": "req-token",
                        "turnstile": {"required": False},
                        "proofofwork": {"required": False},
                    },
                )
                return

            if self.path == "/backend-api/files":
                payload = json.loads(self._read_body().decode("utf-8"))
                state["file_create_payloads"].append(payload)
                base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
                self._write_json(
                    200,
                    {
                        "upload_url": f"{base_url}/upload/file-1",
                        "file_id": "file-1",
                    },
                )
                return

            if self.path == "/backend-api/files/file-1/uploaded":
                state["finalize_calls"] += 1
                self._write_json(200, {"download_url": "https://download.test/file-1"})
                return

            if self.path == "/backend-api/f/conversation":
                payload = json.loads(self._read_body().decode("utf-8"))
                state["conversation_payloads"].append(payload)
                if backend_status >= 400:
                    body = b"backend exploded"
                    self.send_response(backend_status)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                events = [
                    {
                        "v": {
                            "conversation_id": "conv-123",
                            "message": {
                                "author": {"role": "assistant"},
                                "id": "assistant-1",
                                "recipient": "all",
                            },
                        }
                    },
                    {"type": "title_generation", "title": "Generated title"},
                    {"v": "Hello "},
                    {
                        "v": [
                            {"p": "/message/content/parts/0", "v": "world"},
                            {"p": "/message/metadata", "v": {"finish_details": {"type": "stop"}}},
                        ]
                    },
                ]
                for event in events:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return

            self.send_response(404)
            self.end_headers()

        def do_PUT(self) -> None:
            if self.path == "/upload/file-1":
                state["uploaded_payloads"].append(self._read_body())
                self.send_response(201)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            return None

    return ChatHandler


def test_run_curl_persists_cookies_by_default() -> None:
    client = _build_client()

    with _serve(CookieHandler) as base_url:
        status, body, _ = client._run_curl(
            "GET",
            f"{base_url}/image.png",
            {"user-agent": client.base_headers["user-agent"]},
        )

    assert status == 200
    assert body == PNG_BYTES
    assert client.auth.cookies["session"] == "internal"


def test_media_url_download_follows_redirects_without_polluting_auth_cookies() -> None:
    client = _build_client()

    with _serve(RedirectHandler) as base_url:
        body = client._media_to_bytes(f"{base_url}/redirect")

    assert body == PNG_BYTES
    assert "poisoned" not in client.auth.cookies


def test_normalize_media_items_accepts_raw_values_and_named_items() -> None:
    items = adapter.ChatGPTWebClient._normalize_media_items(
        [
            "https://example.test/image.png",
            (b"raw", "raw.bin"),
        ]
    )

    assert items == [
        ("https://example.test/image.png", None),
        (b"raw", "raw.bin"),
    ]


def test_media_string_local_path_is_supported(tmp_path) -> None:
    client = _build_client()
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(PNG_BYTES)

    assert client._media_to_bytes(str(image_path)) == PNG_BYTES


def test_generate_answer_uses_byte_length_for_difficulty(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHash:
        def digest(self) -> bytes:
            return bytes.fromhex("0a0bffff")

    monkeypatch.setattr(client_mod.hashlib, "new", lambda *_args, **_kwargs: FakeHash())

    _, solved = client_mod._generate_answer("seed", "0a0b", list(range(11)), max_attempts=1)

    assert solved is True


def test_send_rejects_invalid_reasoning_effort() -> None:
    client = _build_client()

    with pytest.raises(ValueError, match="reasoning_effort"):
        client.send("hello", reasoning_effort="deep")


def test_send_with_warmup_media_and_flags_uses_prefetched_requirements(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    image_path = tmp_path / "image.png"
    image_path.write_bytes(PNG_BYTES)
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
    }
    streamed_tokens: list[str] = []

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)

        assert client.warmup() is True
        response = client.send(
            "Describe this image.",
            model="gpt-5.1",
            system="Be concise.",
            web_search=True,
            temporary=True,
            reasoning_effort="standard",
            media=[str(image_path)],
            on_token=streamed_tokens.append,
        )

    assert state["requirements_calls"] == 1
    assert state["file_create_payloads"] == [
        {
            "file_name": "image.png",
            "file_size": len(PNG_BYTES),
            "use_case": "multimodal",
        }
    ]
    assert state["uploaded_payloads"] == [PNG_BYTES]
    assert state["finalize_calls"] == 1
    assert len(state["conversation_payloads"]) == 1

    payload = state["conversation_payloads"][0]
    assert payload["model"] == "gpt-5-1"
    assert payload["history_and_training_disabled"] is True
    assert payload["system_hints"] == ["search"]
    assert payload["thinking_effort"] == "standard"
    assert payload["messages"][0]["author"]["role"] == "system"
    assert payload["messages"][-1]["content"]["content_type"] == "multimodal_text"
    assert payload["messages"][-1]["metadata"]["attachments"][0]["name"] == "image.png"

    assert streamed_tokens == ["Hello ", "world"]
    assert response.text == "Hello world"
    assert response.title == "Generated title"
    assert response.conversation.conversation_id == "conv-123"
    assert response.conversation.message_id == "assistant-1"
    assert response.conversation.finish_reason == "stop"
    assert response.metrics.first_token is not None
    assert response.metrics.total is not None


def test_send_backend_error_raises_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
    }

    with _serve(_make_chat_handler(state, backend_status=500)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)

        with pytest.raises(adapter.RequestError, match="backend status=500"):
            client.send("fail please")


def test_send_cleans_up_process_on_callback_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.BytesIO(
                b'data: {"v":{"conversation_id":"conv-123","message":{"author":{"role":"assistant"},"id":"assistant-1","recipient":"all"}}}\n'
                b'data: {"v":"Hello"}\n'
            )
            self.stderr = io.BytesIO(b"")
            self.return_code = 0
            self.wait_calls = 0
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            if self.terminated or self.killed or self.wait_calls:
                return self.return_code
            return None

        def wait(self, timeout: float | None = None) -> int:
            self.wait_calls += 1
            return self.return_code

        def terminate(self) -> None:
            self.terminated = True
            self.return_code = -15

        def kill(self) -> None:
            self.killed = True
            self.return_code = -9

    process = FakeProcess()

    monkeypatch.setattr(
        client,
        "_get_ready_requirements",
        lambda: ({"token": "req-token", "turnstile": {"required": False}}, None),
    )

    def fake_build_curl_command(
        method: str,
        url: str,
        headers: dict[str, str],
        header_path: str,
        body_path: str | None = None,
        *,
        no_buffer: bool = False,
        follow_redirects: bool = False,
    ) -> list[str]:
        Path(header_path).write_text("HTTP/1.1 200 OK\r\n\r\n", encoding="utf-8")
        return ["curl"]

    monkeypatch.setattr(client, "_build_curl_command", fake_build_curl_command)
    monkeypatch.setattr(client_mod.subprocess, "Popen", lambda *args, **kwargs: process)

    def on_token(_token: str) -> None:
        raise RuntimeError("callback exploded")

    with pytest.raises(RuntimeError, match="callback exploded"):
        client.send("hello", on_token=on_token)

    assert process.terminated is True
    assert process.killed is False
    assert process.wait_calls >= 1
