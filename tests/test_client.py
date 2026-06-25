from __future__ import annotations

import io
import json
import shutil
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

import chatgpt_web_adapter as adapter
import chatgpt_web_adapter.client as client_mod
import pytest

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 40


def _live_like_stream_events(
    *,
    conversation_id: str = "conv-live",
    assistant_message_id: str = "assistant-final",
    title: str = "Live-like title",
    text_parts: tuple[str, ...] = ("scan-", "ok"),
    finish_reason: str = "stop",
) -> list[dict[str, Any]]:
    return [
        {"type": "resume_conversation_token", "kind": "topic", "token": "resume-token"},
        {
            "v": {
                "conversation_id": conversation_id,
                "message": {
                    "author": {"role": "user"},
                    "id": "user-1",
                    "recipient": "all",
                },
            }
        },
        {
            "v": {
                "message": {
                    "author": {"role": "assistant"},
                    "id": "system-ctx",
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": [""]},
                    "metadata": {
                        "is_user_system_message": True,
                        "model_slug": "gpt-5-3-mini",
                    },
                },
                "conversation_id": conversation_id,
            }
        },
        {
            "type": "input_message",
            "input_message": {
                "id": "user-1",
                "author": {"role": "user"},
            },
        },
        {
            "v": {
                "message": {
                    "author": {"role": "assistant"},
                    "id": assistant_message_id,
                    "recipient": "all",
                    "channel": "final",
                },
                "conversation_id": conversation_id,
            }
        },
        {"type": "title_generation", "title": title},
        {"type": "delta_encoding", "encoding": "v1"},
        {"type": "message_marker", "conversation_id": conversation_id, "message_id": assistant_message_id},
        {
            "v": [
                *(
                    {"p": "/message/content/parts/0", "v": part}
                    for part in text_parts
                ),
                {"p": "/message/metadata", "v": {"finish_details": {"type": finish_reason}}},
            ]
        },
        {"type": "server_ste_metadata", "metadata": {"message_id": assistant_message_id}},
        {"type": "message_stream_complete", "conversation_id": conversation_id},
    ]


def _top_level_id_only_stream_events(
    *,
    conversation_id: str = "conv-top-level",
    assistant_message_id: str = "assistant-top-level",
    text_parts: tuple[str, ...] = ("top-", "level"),
) -> list[dict[str, Any]]:
    return [
        {"type": "resume_conversation_token", "kind": "topic", "token": "resume-token"},
        {
            "v": {
                "message": {
                    "author": {"role": "assistant"},
                    "id": "assistant-ephemeral",
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": [""]},
                }
            }
        },
        {
            "type": "message_marker",
            "conversation_id": conversation_id,
            "message_id": assistant_message_id,
        },
        {
            "v": [
                *(
                    {"p": "/message/content/parts/0", "v": part}
                    for part in text_parts
                ),
                {"p": "/message/metadata", "v": {"finish_details": {"type": "stop"}}},
            ]
        },
        {"type": "message_stream_complete", "conversation_id": conversation_id},
    ]


def _handoff_only_stream_events(
    *,
    conversation_id: str = "conv-123",
) -> list[dict[str, Any]]:
    return [
        "v1",
        {
            "type": "resume_conversation_token",
            "kind": "topic",
            "token": "resume-token",
            "conversation_id": conversation_id,
        },
        {
            "type": "stream_handoff",
            "conversation_id": conversation_id,
            "turn_exchange_id": "turn-123",
            "options": [
                {
                    "type": "resume_sse_endpoint",
                    "topic_id": "conversation-turn-123",
                }
            ],
        },
    ]


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
    client.debug_trace_dir = None
    client.debug_trace_sanitize = True
    client._debug_trace_counter = 0
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
    monkeypatch.setattr(client_mod, "CHAT_CONVERSATION_PREPARE_URL", f"{base_url}/backend-api/f/conversation/prepare")
    monkeypatch.setattr(client_mod, "CHAT_CONVERSATION_URL", f"{base_url}/backend-api/conversation/{{conversation_id}}")
    monkeypatch.setattr(client_mod, "CHAT_CONVERSATIONS_URL", f"{base_url}/backend-api/conversations")
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
                if payload.get("messages"):
                    state.setdefault("approval_stream_payloads", []).append(payload)
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
                events = state.get("stream_events") or [
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

            if self.path == "/backend-api/f/conversation/prepare":
                payload = json.loads(self._read_body().decode("utf-8"))
                state.setdefault("prepare_payloads", []).append(payload)
                self._write_json(200, {"status": "ok", "conduit_token": "conduit-token"})
                return

            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:
            if self.path.startswith("/backend-api/conversations"):
                state["conversations_get_calls"] = state.get("conversations_get_calls", 0) + 1
                self._write_json(
                    200,
                    {
                        "items": state.get(
                            "recent_conversations",
                            [{"id": "conv-123", "title": "Test conversation"}],
                        )
                    },
                )
                return
            if self.path == "/backend-api/conversation/conv-123":
                state["conversation_get_calls"] = state.get("conversation_get_calls", 0) + 1
                conversation_statuses = state.get("conversation_get_statuses")
                if isinstance(conversation_statuses, list) and conversation_statuses:
                    status_entry = conversation_statuses.pop(0)
                    if isinstance(status_entry, dict):
                        self._write_json(int(status_entry.get("status", 200)), status_entry.get("payload") or {})
                        return
                conversation_payloads = state.get("conversation_get_payloads")
                if isinstance(conversation_payloads, list) and conversation_payloads:
                    conversation_payload = conversation_payloads.pop(0)
                    if isinstance(conversation_payload, dict):
                        self._write_json(200, conversation_payload)
                        return
                conversation_payload = state.get("conversation_get_payload")
                if isinstance(conversation_payload, dict):
                    self._write_json(200, conversation_payload)
                    return
                self._write_json(
                    200,
                    {
                        "conversation_id": "conv-123",
                        "mapping": {
                            "assistant-old": {
                                "message": {
                                    "id": "assistant-old",
                                    "author": {"role": "assistant"},
                                    "create_time": 1,
                                    "content": {
                                        "content_type": "text",
                                        "parts": ["approval required"],
                                    },
                                }
                            },
                            "assistant-new": {
                                "message": {
                                    "id": "assistant-new",
                                    "author": {"role": "assistant"},
                                    "create_time": 2,
                                    "content": {
                                        "content_type": "text",
                                        "parts": ["approved result"],
                                    },
                                    "metadata": {
                                        "finish_details": {"type": "stop"},
                                    },
                                }
                            },
                        },
                    },
                )
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


def test_run_curl_writes_sanitized_debug_trace(tmp_path) -> None:
    client = _build_client()
    client.debug_trace_dir = tmp_path

    with _serve(CookieHandler) as base_url:
        status, body, _ = client._run_curl(
            "GET",
            f"{base_url}/image.png",
            {
                "user-agent": client.base_headers["user-agent"],
                "authorization": "Bearer secret-token",
                "cookie": "session=secret",
                "openai-sentinel-proof-token": "proof-secret",
            },
        )

    trace_files = sorted(tmp_path.glob("*.json"))
    assert status == 200
    assert body == PNG_BYTES
    assert len(trace_files) == 1

    payload = json.loads(trace_files[0].read_text(encoding="utf-8"))
    assert payload["method"] == "GET"
    assert payload["response_status"] == 200
    assert payload["request_headers"]["authorization"] == "<redacted>"
    assert payload["request_headers"]["cookie"] == "<redacted>"
    assert payload["request_headers"]["openai-sentinel-proof-token"] == "<redacted>"
    assert "Set-Cookie: <redacted>" in payload["response_headers"]
    assert payload["response_body"]["kind"] == "base64"


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


def test_send_writes_stream_debug_trace(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    client.debug_trace_dir = tmp_path
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("hello")

    trace_files = sorted(tmp_path.glob("*.json"))
    assert response.text == "Hello world"
    assert len(trace_files) >= 2

    stream_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in trace_files
        if path.name.endswith("-stream.json")
    ]
    assert len(stream_payloads) == 1
    stream_trace = stream_payloads[0]
    assert stream_trace["request_headers"]["authorization"] == "<redacted>"
    assert stream_trace["response_status"] == 200
    assert stream_trace["stream_text"] == "Hello world"
    assert stream_trace["events"][-1] == "[DONE]"


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


def test_send_instant_mode_uses_minimal_payload_without_thinking_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("Reply with exactly: instant", reasoning_effort="instant")

    payload = state["conversation_payloads"][0]
    assert response.text == "Hello world"
    assert response.request.sent_model == "gpt-5-3-mini"
    assert response.request.sent_reasoning_effort is None
    assert payload["model"] == "gpt-5-3-mini"
    assert "thinking_effort" not in payload
    assert "system_hints" not in payload
    assert [message["author"]["role"] for message in payload["messages"]] == ["user"]


@pytest.mark.parametrize(
    ("reasoning_effort", "expected_model", "expected_effort"),
    [
        ("medium", "gpt-5-5-thinking", "standard"),
        ("high", "gpt-5-5-thinking", "extended"),
    ],
)
def test_send_ui_reasoning_modes_map_to_current_backend_values(
    monkeypatch: pytest.MonkeyPatch,
    reasoning_effort: str,
    expected_model: str,
    expected_effort: str,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("Reply with exactly: mapped", reasoning_effort=reasoning_effort)

    payload = state["conversation_payloads"][0]
    assert response.text == "Hello world"
    assert response.request.requested_reasoning_effort == reasoning_effort
    assert response.request.sent_model == expected_model
    assert response.request.sent_reasoning_effort == expected_effort
    assert payload["model"] == expected_model
    assert payload["thinking_effort"] == expected_effort


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


def test_send_handles_richer_live_like_sse_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    streamed_tokens: list[str] = []
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "stream_events": _live_like_stream_events(),
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("Reply with exactly: scan-ok", on_token=streamed_tokens.append)

    assert streamed_tokens == ["scan-", "ok"]
    assert response.text == "scan-ok"
    assert response.title == "Live-like title"
    assert response.conversation.conversation_id == "conv-live"
    assert response.conversation.message_id == "assistant-final"
    assert response.conversation.finish_reason == "stop"
    assert response.request.sent_model == "gpt-5-3-mini"
    assert response.request.sent_reasoning_effort is None
    assert response.request.observed_model == "gpt-5-3-mini"


def test_send_event_callback_tolerates_live_like_sse_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "stream_events": _live_like_stream_events(
            text_parts=("alpha-", "beta", "-done"),
            title="Live callback title",
        ),
    }
    events: list[dict[str, Any]] = []
    streamed_tokens: list[str] = []

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "Reply with exactly: alpha-beta-done",
            on_token=streamed_tokens.append,
            on_event=events.append,
        )

    assert response.text == "alpha-beta-done"
    assert response.title == "Live callback title"
    assert streamed_tokens == ["alpha-", "beta", "-done"]
    event_types = [event["type"] for event in events]
    assert event_types[0:4] == [
        "request_started",
        "requirements_ready",
        "request_payload_prepared",
        "stream_started",
    ]
    assert event_types.count("raw_sse_event") >= 1
    assert event_types.count("assistant_token") == 3
    assert event_types[-3:] == [
        "stream_completed",
        "stream_done",
        "request_completed",
    ]
    assert events[0]["requested_model"] is None
    assert events[0]["requested_reasoning_effort"] is None
    assert events[2]["payload"]["model"] == "gpt-5-3-mini"
    assert events[-3]["text_length"] == len("alpha-beta-done")
    assert events[-1]["sent_model"] == "gpt-5-3-mini"
    assert events[-1]["observed_model"] == "gpt-5-3-mini"
    assert events[-1]["conversation_id"] == "conv-live"
    assert events[-1]["message_id"] == "assistant-final"


def test_send_recovers_conversation_id_from_top_level_sse_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "stream_events": _top_level_id_only_stream_events(),
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("Reply with exactly: top-level", reasoning_effort="high")

    assert response.text == "top-level"
    assert response.conversation.conversation_id == "conv-top-level"
    assert response.conversation.message_id == "assistant-top-level"
    assert response.request.conversation_id == "conv-top-level"
    assert response.request.sent_model == "gpt-5-5-thinking"
    assert response.request.sent_reasoning_effort == "extended"


def test_send_recovers_message_id_text_and_metadata_after_stream_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "conversation_get_calls": 0,
        "stream_events": _handoff_only_stream_events(),
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "current_node": "assistant-final",
            "mapping": {
                "assistant-final": {
                    "message": {
                        "id": "assistant-final",
                        "author": {"role": "assistant"},
                        "recipient": "all",
                        "create_time": 2,
                        "content": {"content_type": "text", "parts": ["handoff-ok"]},
                        "metadata": {
                            "model_slug": "gpt-5-5-thinking",
                            "thinking_effort": "extended",
                            "finish_details": {"type": "stop"},
                        },
                    }
                }
            },
        },
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("Reply with exactly: handoff-ok", reasoning_effort="high")

    assert state["conversation_get_calls"] == 1
    assert response.text == "handoff-ok"
    assert response.conversation.conversation_id == "conv-123"
    assert response.conversation.message_id == "assistant-final"
    assert response.conversation.parent_message_id == "assistant-final"
    assert response.request.conversation_id == "conv-123"
    assert response.request.sent_model == "gpt-5-5-thinking"
    assert response.request.sent_reasoning_effort == "extended"
    assert response.request.observed_model == "gpt-5-5-thinking"
    assert response.request.observed_reasoning_effort == "extended"


def test_send_emits_handoff_and_poll_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "conversation_get_calls": 0,
        "stream_events": _handoff_only_stream_events(),
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "current_node": "assistant-final",
            "mapping": {
                "assistant-final": {
                    "message": {
                        "id": "assistant-final",
                        "author": {"role": "assistant"},
                        "recipient": "all",
                        "create_time": 2,
                        "content": {"content_type": "text", "parts": ["handoff-events-ok"]},
                        "metadata": {
                            "model_slug": "gpt-5-5-thinking",
                            "thinking_effort": "extended",
                            "finish_details": {"type": "stop"},
                        },
                    }
                }
            },
        },
    }
    events: list[dict[str, Any]] = []

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "Reply with exactly: handoff-events-ok",
            reasoning_effort="high",
            on_event=events.append,
        )

    assert response.text == "handoff-events-ok"
    event_types = [event["type"] for event in events]
    assert "request_payload_prepared" in event_types
    assert "raw_sse_event" in event_types
    assert "raw_sse_done" in event_types
    assert "stream_handoff" in event_types
    handoff_event = next(event for event in events if event["type"] == "stream_handoff")
    assert handoff_event["conversation_id"] == "conv-123"
    assert handoff_event["turn_exchange_id"] == "turn-123"


def test_send_polls_conversation_until_handoff_reply_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    events: list[dict[str, Any]] = []
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "conversation_get_calls": 0,
        "stream_events": _handoff_only_stream_events(),
        "conversation_get_payloads": [
            {
                "conversation_id": "conv-123",
                "current_node": "user-new",
                "mapping": {
                    "user-new": {
                        "message": {
                            "id": "user-new",
                            "author": {"role": "user"},
                            "recipient": "all",
                            "create_time": 1,
                            "content": {"content_type": "text", "parts": ["Reply with exactly: polled-ok"]},
                        }
                    }
                },
            },
            {
                "conversation_id": "conv-123",
                "current_node": "assistant-final",
                "mapping": {
                    "assistant-final": {
                        "message": {
                            "id": "assistant-final",
                            "author": {"role": "assistant"},
                            "recipient": "all",
                            "create_time": 2,
                            "content": {"content_type": "text", "parts": ["polled-ok"]},
                            "metadata": {
                                "model_slug": "gpt-5-5-thinking",
                                "thinking_effort": "extended",
                                "finish_details": {"type": "stop"},
                            },
                        }
                    }
                },
            },
        ],
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "Reply with exactly: polled-ok",
            reasoning_effort="high",
            on_event=events.append,
        )

    assert state["conversation_get_calls"] >= 2
    assert response.text == "polled-ok"
    assert response.conversation.conversation_id == "conv-123"
    assert response.conversation.message_id == "assistant-final"
    assert response.request.observed_model == "gpt-5-5-thinking"
    assert response.request.observed_reasoning_effort == "extended"
    event_types = [event["type"] for event in events]
    assert "conversation_poll_started" in event_types
    assert "conversation_poll_attempt" in event_types
    assert "conversation_poll_completed" in event_types


def test_send_to_existing_conversation_does_not_return_stale_assistant_reply_after_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    events: list[dict[str, Any]] = []
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "conversation_get_calls": 0,
        "stream_events": _handoff_only_stream_events(),
        "conversation_get_payloads": [
            {
                "conversation_id": "conv-123",
                "current_node": "assistant-old",
                "mapping": {
                    "assistant-old": {
                        "message": {
                            "id": "assistant-old",
                            "author": {"role": "assistant"},
                            "recipient": "all",
                            "create_time": 1,
                            "content": {"content_type": "text", "parts": ["stale-old-reply"]},
                            "metadata": {"finish_details": {"type": "stop"}},
                        }
                    }
                },
            },
            {
                "conversation_id": "conv-123",
                "current_node": "user-new",
                "mapping": {
                    "assistant-old": {
                        "message": {
                            "id": "assistant-old",
                            "author": {"role": "assistant"},
                            "recipient": "all",
                            "create_time": 1,
                            "content": {"content_type": "text", "parts": ["stale-old-reply"]},
                            "metadata": {"finish_details": {"type": "stop"}},
                        }
                    },
                    "user-new": {
                        "parent": "assistant-old",
                        "message": {
                            "id": "user-new",
                            "author": {"role": "user"},
                            "recipient": "all",
                            "create_time": 2,
                            "content": {"content_type": "text", "parts": ["fresh prompt"]},
                        }
                    },
                },
            },
            {
                "conversation_id": "conv-123",
                "current_node": "assistant-final",
                "mapping": {
                    "assistant-old": {
                        "message": {
                            "id": "assistant-old",
                            "author": {"role": "assistant"},
                            "recipient": "all",
                            "create_time": 1,
                            "content": {"content_type": "text", "parts": ["stale-old-reply"]},
                            "metadata": {"finish_details": {"type": "stop"}},
                        }
                    },
                    "user-new": {
                        "parent": "assistant-old",
                        "message": {
                            "id": "user-new",
                            "author": {"role": "user"},
                            "recipient": "all",
                            "create_time": 2,
                            "content": {"content_type": "text", "parts": ["fresh prompt"]},
                        }
                    },
                    "assistant-final": {
                        "parent": "user-new",
                        "message": {
                            "id": "assistant-final",
                            "author": {"role": "assistant"},
                            "recipient": "all",
                            "create_time": 3,
                            "content": {"content_type": "text", "parts": ["fresh-final-reply"]},
                            "metadata": {
                                "model_slug": "gpt-5-5-thinking",
                                "thinking_effort": "extended",
                                "finish_details": {"type": "stop"},
                            },
                        }
                    },
                },
            },
        ],
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "fresh prompt",
            conversation=adapter.ChatConversation(
                conversation_id="conv-123",
                message_id="assistant-old",
                parent_message_id="assistant-old",
            ),
            model="gpt-5-5-thinking",
            reasoning_effort="high",
            on_event=events.append,
        )

    assert state["conversation_get_calls"] >= 3
    assert response.text == "fresh-final-reply"
    assert response.conversation.message_id == "assistant-final"
    event_types = [event["type"] for event in events]
    assert "conversation_poll_started" in event_types
    assert "conversation_poll_completed" in event_types
    attempt_events = [event for event in events if event["type"] == "conversation_poll_attempt"]
    assert attempt_events
    assert attempt_events[0]["lifecycle_status"] == "user_last_message"


def test_send_retries_after_conversation_inaccessible_during_handoff_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    events: list[dict[str, Any]] = []
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "conversation_get_calls": 0,
        "stream_events": _handoff_only_stream_events(),
        "conversation_get_statuses": [
            {
                "status": 404,
                "payload": {
                    "detail": {
                        "message": "conversation not ready yet",
                        "code": "conversation_inaccessible",
                        "can_retry": False,
                        "conversation_id": "conv-123",
                    }
                },
            }
        ],
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "current_node": "assistant-final",
            "mapping": {
                "assistant-final": {
                    "message": {
                        "id": "assistant-final",
                        "author": {"role": "assistant"},
                        "recipient": "all",
                        "create_time": 2,
                        "content": {"content_type": "text", "parts": ["retry-ok"]},
                        "metadata": {
                            "model_slug": "gpt-5-5-thinking",
                            "thinking_effort": "extended",
                            "finish_details": {"type": "stop"},
                        },
                    }
                }
            },
        },
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "Reply with exactly: retry-ok",
            reasoning_effort="high",
            on_event=events.append,
        )

    assert state["conversation_get_calls"] >= 2
    assert response.text == "retry-ok"
    event_types = [event["type"] for event in events]
    assert "conversation_recovery_fetch_error" in event_types
    assert "conversation_poll_completed" in event_types


def test_approve_pending_action_posts_prepare_and_polls_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    streamed_tokens: list[str] = []
    events: list[dict[str, Any]] = []
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "prepare_payloads": [],
        "conversation_get_calls": 0,
        "approval_stream_payloads": [],
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "mapping": {
                "assistant-target": {
                    "message": {
                        "id": "assistant-target",
                        "author": {"role": "assistant"},
                        "recipient": "api_tool.call_tool",
                        "create_time": 1.0,
                        "content": {"content_type": "text", "parts": [""]},
                    }
                },
                "tool-leaf": {
                    "parent": "assistant-target",
                    "children": [],
                    "message": {
                        "id": "tool-leaf",
                        "author": {"role": "tool"},
                        "recipient": "assistant",
                        "create_time": 2.0,
                        "content": {"content_type": "text", "parts": [""]},
                        "metadata": {
                            "jit_plugin_data": {
                                "from_server": {
                                    "type": "confirm_action",
                                    "body": {
                                        "actions": [
                                            {
                                                "type": "allow",
                                                "allow": {"target_message_id": "assistant-target"},
                                            }
                                        ]
                                    },
                                }
                            }
                        },
                    },
                },
                "assistant-new": {
                    "message": {
                        "id": "assistant-new",
                        "author": {"role": "assistant"},
                        "create_time": 3.0,
                        "content": {
                            "content_type": "text",
                            "parts": ["approved result"],
                        },
                        "metadata": {
                            "finish_details": {"type": "stop"},
                        },
                    }
                },
            },
        },
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)

        response = client.approve_pending_action(
            adapter.ChatConversation(
                conversation_id="conv-123",
                message_id="assistant-old",
                parent_message_id="assistant-old",
            ),
            model="gpt-5-5-thinking",
            reasoning_effort="extended",
            poll_interval=0.01,
            on_token=streamed_tokens.append,
            on_event=events.append,
        )

    assert state["prepare_payloads"] == [
        {
            "action": "next",
            "fork_from_shared_post": False,
            "conversation_id": "conv-123",
            "parent_message_id": "tool-leaf",
            "model": "gpt-5-5-thinking",
            "client_prepare_state": "none",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
            "thinking_effort": "extended",
        }
    ]
    assert len(state["approval_stream_payloads"]) == 1
    stream_payload = state["approval_stream_payloads"][0]
    assert stream_payload["client_prepare_state"] == "success"
    assert stream_payload["parent_message_id"] == "tool-leaf"
    assert stream_payload["messages"][0]["author"] == {"role": "tool", "name": "api_tool.call_tool"}
    assert stream_payload["messages"][0]["recipient"] == "all"
    assert stream_payload["messages"][0]["metadata"]["jit_plugin_data"]["from_client"] == {
        "type": "allow",
        "target_message_id": "assistant-target",
        "remember_answer": False,
    }
    assert state["conversation_get_calls"] == 2
    assert streamed_tokens == ["Hello ", "world"]
    event_types = [event["type"] for event in events]
    assert event_types[:5] == [
        "pending_approval_detected",
        "approval_prepare_succeeded",
        "assistant_token",
        "assistant_token",
        "approval_sent",
    ]
    assert "conversation_poll_started" in event_types
    assert "conversation_poll_attempt" in event_types
    assert "conversation_poll_completed" in event_types
    assert event_types[-1] == "approval_completed"
    assert response.text == "approved result"
    assert response.conversation.conversation_id == "conv-123"
    assert response.conversation.message_id == "assistant-new"
    assert response.conversation.parent_message_id == "assistant-new"
    assert response.conversation.finish_reason == "stop"


def test_approve_pending_action_missing_pending_descriptor_raises_stage_specific_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "prepare_payloads": [],
        "conversation_get_calls": 0,
        "approval_stream_payloads": [],
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "mapping": {},
        },
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        with pytest.raises(
            adapter.RequestError,
            match="pending tool approval not found in conversation payload",
        ):
            client.approve_pending_action(
                adapter.ChatConversation(conversation_id="conv-123"),
                poll=False,
            )


def test_approve_pending_action_can_skip_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    client.auth.accessToken = "test-token"
    state = {
        "requirements_calls": 0,
        "file_create_payloads": [],
        "conversation_payloads": [],
        "uploaded_payloads": [],
        "finalize_calls": 0,
        "prepare_payloads": [],
        "conversation_get_calls": 0,
        "approval_stream_payloads": [],
        "conversation_get_payload": {
            "conversation_id": "conv-123",
            "mapping": {
                "assistant-target": {
                    "message": {
                        "id": "assistant-target",
                        "author": {"role": "assistant"},
                        "recipient": "api_tool.call_tool",
                        "create_time": 1.0,
                        "content": {"content_type": "text", "parts": [""]},
                    }
                },
                "tool-leaf": {
                    "parent": "assistant-target",
                    "children": [],
                    "message": {
                        "id": "tool-leaf",
                        "author": {"role": "tool"},
                        "recipient": "assistant",
                        "create_time": 2.0,
                        "content": {"content_type": "text", "parts": [""]},
                        "metadata": {
                            "jit_plugin_data": {
                                "from_server": {
                                    "type": "confirm_action",
                                    "body": {
                                        "actions": [
                                            {
                                                "type": "allow",
                                                "allow": {"target_message_id": "assistant-target"},
                                            }
                                        ]
                                    },
                                }
                            }
                        },
                    },
                },
            },
        },
    }

    with _serve(_make_chat_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)

        response = client.approve_pending_action(
            {"conversation_id": "conv-123", "message_id": "assistant-old"},
            poll=False,
        )

    assert len(state["prepare_payloads"]) == 1
    assert state["conversation_get_calls"] == 1
    assert response.text == "Hello world"
    assert response.conversation.message_id == "tool-leaf"


def test_wait_and_approve_pending_actions_stops_when_conversation_becomes_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    responses = [
        adapter.ChatResponse(
            text="created file 1",
            conversation=adapter.ChatConversation(conversation_id="conv-123", message_id="assistant-1"),
        ),
        adapter.ChatResponse(
            text="created file 2",
            conversation=adapter.ChatConversation(conversation_id="conv-123", message_id="assistant-2"),
        ),
    ]
    payloads = [
        {
            "conversation_id": "conv-123",
            "current_node": "a1-final",
            "mapping": {
                "tool-1": {
                    "children": [],
                    "message": {
                        "id": "tool-1",
                        "author": {"role": "tool"},
                        "create_time": 1.0,
                        "metadata": {
                            "jit_plugin_data": {
                                "from_server": {
                                    "type": "confirm_action",
                                    "body": {
                                        "actions": [{"type": "allow", "allow": {"target_message_id": "a1"}}]
                                    },
                                }
                            }
                        },
                    },
                },
                "a1": {"message": {"id": "a1", "author": {"role": "assistant"}, "recipient": "api_tool.call_tool"}},
                "a1-final": {"message": {"id": "a1-final", "author": {"role": "assistant"}, "recipient": "all", "content": {"content_type": "text", "parts": ["created file 1"]}}},
            }
        },
        {
            "conversation_id": "conv-123",
            "current_node": "a2-final",
            "mapping": {
                "tool-2": {
                    "children": [],
                    "message": {
                        "id": "tool-2",
                        "author": {"role": "tool"},
                        "create_time": 2.0,
                        "metadata": {
                            "jit_plugin_data": {
                                "from_server": {
                                    "type": "confirm_action",
                                    "body": {
                                        "actions": [{"type": "allow", "allow": {"target_message_id": "a2"}}]
                                    },
                                }
                            }
                        },
                    },
                },
                "a2": {"message": {"id": "a2", "author": {"role": "assistant"}, "recipient": "api_tool.call_tool"}},
                "a2-final": {"message": {"id": "a2-final", "author": {"role": "assistant"}, "recipient": "all", "content": {"content_type": "text", "parts": ["created file 2"]}}},
            }
        },
        {
            "conversation_id": "conv-123",
            "current_node": "assistant-final",
            "mapping": {
                "assistant-final": {
                    "message": {
                        "id": "assistant-final",
                        "author": {"role": "assistant"},
                        "recipient": "all",
                        "content": {"content_type": "text", "parts": ["created file 2"]},
                        "metadata": {"finish_details": {"type": "stop"}},
                    }
                }
            }
        },
    ]
    approve_calls: list[str] = []

    monkeypatch.setattr(client, "_get_conversation_payload", lambda _cid: payloads.pop(0))
    monkeypatch.setattr(client, "_get_recent_conversation_summary", lambda _cid: {"id": "conv-123", "async_status": None})

    def fake_approve(conversation, **_kwargs):
        approve_calls.append(str(adapter.ChatConversation.from_dict(
            conversation.to_dict() if isinstance(conversation, adapter.ChatConversation) else conversation
        ).conversation_id))
        return responses.pop(0)

    monkeypatch.setattr(client, "approve_pending_action", fake_approve)

    response = client.wait_and_approve_pending_actions(
        adapter.ChatConversation(conversation_id="conv-123", message_id="assistant-old"),
        settle_delay=0.0,
    )

    assert approve_calls == ["conv-123", "conv-123"]
    assert response.text == "created file 2"
    assert response.conversation.message_id == "assistant-final"


def test_send_and_auto_approve_resolves_new_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    recent_calls = {"count": 0}
    events: list[dict[str, Any]] = []

    def fake_list_recent_conversations(*, limit: int = 10) -> list[dict[str, Any]]:
        recent_calls["count"] += 1
        if recent_calls["count"] == 1:
            return [{"id": "conv-old"}]
        return [{"id": "conv-new"}, {"id": "conv-old"}]

    monkeypatch.setattr(client, "_list_recent_conversations", fake_list_recent_conversations)
    monkeypatch.setattr(
        client,
        "send",
        lambda *args, **kwargs: adapter.ChatResponse(
            text="",
            conversation=adapter.ChatConversation(conversation_id=None, message_id="assistant-prompt"),
        ),
    )
    captured: dict[str, Any] = {}

    def fake_wait(conversation, **kwargs):
        captured["conversation"] = conversation
        captured["kwargs"] = kwargs
        return adapter.ChatResponse(
            text="approved final",
            conversation=adapter.ChatConversation(conversation_id="conv-new", message_id="assistant-final"),
        )

    monkeypatch.setattr(client, "wait_and_approve_pending_actions", fake_wait)

    response = client.send_and_auto_approve(
        "create a file",
        pending_poll_interval=0.01,
        settle_delay=0.0,
        on_event=events.append,
    )

    assert response.text == "approved final"
    assert captured["conversation"].conversation_id == "conv-new"
    assert recent_calls["count"] >= 2
    assert [event["type"] for event in events] == [
        "prompt_sent",
        "new_conversation_resolved",
    ]


def test_wait_and_approve_pending_actions_verifies_after_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client()
    events: list[dict[str, Any]] = []
    payload = {
        "conversation_id": "conv-123",
        "current_node": "assistant-final",
        "mapping": {
            "assistant-final": {
                "message": {
                    "id": "assistant-final",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": ["done"]},
                    "metadata": {"finish_details": {"type": "stop"}},
                }
            }
        },
    }
    monkeypatch.setattr(client, "_get_conversation_payload", lambda _cid: payload)
    monkeypatch.setattr(client, "_get_recent_conversation_summary", lambda _cid: {"id": "conv-123", "async_status": None})

    response = client.wait_and_approve_pending_actions(
        adapter.ChatConversation(conversation_id="conv-123"),
        verify=lambda item: item.text == "done",
        on_event=events.append,
    )

    assert response.text == "done"
    assert [event["type"] for event in events] == [
        "conversation_idle",
        "verification_completed",
    ]


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
