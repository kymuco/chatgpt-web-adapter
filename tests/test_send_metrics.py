from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Iterator

import pytest

import chatgpt_web_adapter as adapter
import chatgpt_web_adapter.client as client_mod


def _live_like_metrics_stream_events(
    *,
    conversation_id: str = "conv-123",
    assistant_message_id: str = "assistant-1",
    text_parts: tuple[str, ...] = ("Hi", " there"),
    finish_reason: str = "stop",
) -> list[dict[str, Any]]:
    return [
        {"type": "resume_conversation_token", "kind": "topic", "token": "resume-token"},
        {
            "v": {
                "conversation_id": conversation_id,
                "message": {
                    "author": {"role": "assistant"},
                    "id": "service-msg",
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": [""]},
                    "metadata": {"is_user_system_message": True},
                },
            }
        },
        {
            "v": {
                "conversation_id": conversation_id,
                "message": {
                    "author": {"role": "assistant"},
                    "id": assistant_message_id,
                    "recipient": "all",
                },
            }
        },
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


def _patch_chat_endpoints(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    monkeypatch.setattr(
        client_mod,
        "CHAT_REQUIREMENTS_URL",
        f"{base_url}/backend-api/sentinel/chat-requirements",
    )
    monkeypatch.setattr(
        client_mod,
        "CHAT_BACKEND_URL",
        f"{base_url}/backend-api/f/conversation",
    )


def _make_metrics_handler(state: dict[str, Any]) -> type[BaseHTTPRequestHandler]:
    class MetricsHandler(BaseHTTPRequestHandler):
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

            if self.path == "/backend-api/f/conversation":
                state["conversation_payloads"].append(
                    json.loads(self._read_body().decode("utf-8"))
                )
                if state.get("backend_status"):
                    self._write_json(state["backend_status"], {"error": "backend failed"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                events = _live_like_metrics_stream_events()
                for event in events:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return None

    return MetricsHandler


def test_send_populates_expanded_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    state: dict[str, Any] = {
        "requirements_calls": 0,
        "conversation_payloads": [],
    }

    with _serve(_make_metrics_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("hello", model="gpt-4o-mini")

    assert state["requirements_calls"] == 1
    assert response.text == "Hi there"
    assert response.metrics.requirements_latency is not None
    assert response.metrics.requirements_latency >= 0
    assert response.metrics.first_token is not None
    assert response.metrics.last_token is not None
    assert response.metrics.stream_duration is not None
    assert response.metrics.stream_duration > 0
    assert response.metrics.total is not None
    assert response.metrics.total >= response.metrics.stream_duration
    assert response.metrics.chars_per_second == len(response.text) / response.metrics.stream_duration
    assert response.metrics.backend_status == 200


def test_send_metrics_to_dict_contains_expanded_values(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    state: dict[str, Any] = {
        "requirements_calls": 0,
        "conversation_payloads": [],
    }

    with _serve(_make_metrics_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send("hello", model="gpt-4o-mini")

    metrics = response.metrics.to_dict()
    assert metrics["first_token"] == response.metrics.first_token
    assert metrics["last_token"] == response.metrics.last_token
    assert metrics["total"] == response.metrics.total
    assert metrics["requirements_latency"] == response.metrics.requirements_latency
    assert metrics["stream_duration"] == response.metrics.stream_duration
    assert metrics["chars_per_second"] == response.metrics.chars_per_second
    assert metrics["backend_status"] == 200


def test_send_emits_event_callback_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    state: dict[str, Any] = {
        "requirements_calls": 0,
        "conversation_payloads": [],
    }
    events: list[dict[str, Any]] = []
    tokens: list[str] = []

    with _serve(_make_metrics_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        response = client.send(
            "hello",
            model="gpt-4o-mini",
            on_token=tokens.append,
            on_event=events.append,
        )

    assert response.text == "Hi there"
    assert tokens == ["Hi", " there"]
    event_types = [event["type"] for event in events]
    assert event_types == [
        "request_started",
        "requirements_ready",
        "stream_started",
        "first_token",
        "assistant_token",
        "assistant_token",
        "stream_completed",
        "stream_done",
        "request_completed",
    ]
    assert events[0]["model"] == "gpt-4o-mini"
    assert events[1]["token_present"] is True
    assert events[3]["token"] == "Hi"
    assert events[4]["token"] == "Hi"
    assert events[5]["token"] == " there"
    assert events[-2]["text_length"] == len("Hi there")
    assert events[-1]["conversation_id"] == "conv-123"
    assert events[-1]["message_id"] == "assistant-1"
    assert events[-1]["finish_reason"] == "stop"


def test_send_emits_error_event_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client()
    state: dict[str, Any] = {
        "requirements_calls": 0,
        "conversation_payloads": [],
        "backend_status": 500,
    }
    events: list[dict[str, Any]] = []

    with _serve(_make_metrics_handler(state)) as base_url:
        _patch_chat_endpoints(monkeypatch, base_url)
        with pytest.raises(adapter.RequestError, match="backend status=500") as exc_info:
            client.send("hello", model="gpt-4o-mini", on_event=events.append)

    error = exc_info.value
    assert str(error).startswith("backend status=500")
    assert error.status_code == 500
    assert error.endpoint.endswith("/backend-api/f/conversation")
    assert error.body_preview is not None
    assert "backend failed" in error.body_preview
    assert error.request_stage == "conversation_stream"

    event_types = [event["type"] for event in events]
    assert event_types == [
        "request_started",
        "requirements_ready",
        "stream_started",
        "error",
    ]
    assert events[-1]["error_type"] == "RequestError"
    assert "backend status=500" in events[-1]["message"]
    assert events[-1]["status_code"] == 500
    assert events[-1]["endpoint"].endswith("/backend-api/f/conversation")
    assert events[-1]["request_stage"] == "conversation_stream"
    assert "backend failed" in events[-1]["body_preview"]
