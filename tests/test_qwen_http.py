from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import URLError

import pytest

from chatgpt_web_adapter.qwen_http import (
    QwenHttpClient,
    QwenHttpConversation,
    QwenHttpCredentials,
    QwenHttpError,
    QwenHttpWriteOutcomeAmbiguousError,
)


class _Reply(io.BytesIO):
    def __init__(self, payload):
        if isinstance(payload, list):
            data = "".join(
                "data: " + json.dumps(event) + "\n\n"
                if isinstance(event, dict)
                else "data: " + event + "\n\n"
                for event in payload
            )
        else:
            data = json.dumps(payload)
        super().__init__(data.encode())
        self.headers = Message()


def test_http_new_chat_streams_and_continues_without_browser():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/chats/new"):
            return _Reply({"data": {"id": "chat-1"}})
        return _Reply(
            [
                {"response.created": {"response_id": "parent-2"}},
                {"choices": [{"delta": {"content": "QWEN_"}}]},
                {
                    "choices": [
                        {"delta": {"content": "HTTP_OK"}, "finish_reason": "stop"}
                    ]
                },
                "[DONE]",
            ]
        )

    client = QwenHttpClient(
        QwenHttpCredentials("example", {"qwen_session": "abc"}), opener=open_
    )
    chunks = []
    first = client.send_text("first", on_token=chunks.append)
    second = client.send_text("second")
    assert first.text == second.text == "QWEN_HTTP_OK"
    assert chunks == ["QWEN_", "HTTP_OK"]
    assert client.conversation == QwenHttpConversation("chat-1", "parent-2")
    assert len(requests) == 3
    assert all(
        request.full_url.startswith("https://chat.qwen.ai/api/") for request in requests
    )
    assert requests[-1].get_header("Authorization") == "Bearer example"
    body = json.loads(requests[-1].data.decode("utf-8"))
    assert body["parent_id"] == "parent-2"


def test_no_automatic_generation_resend_after_transport_failure():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        raise URLError("offline")

    client = QwenHttpClient(QwenHttpCredentials("example"), opener=open_)
    with pytest.raises(QwenHttpWriteOutcomeAmbiguousError) as caught:
        client.send_text("message", conversation=QwenHttpConversation("chat-1"))
    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False
    assert len(requests) == 1


def test_stream_without_finality_is_ambiguous():

    def open_(request, timeout):
        return _Reply([{"choices": [{"delta": {"content": "partial"}}]}])

    client = QwenHttpClient(QwenHttpCredentials("example"), opener=open_)
    with pytest.raises(QwenHttpWriteOutcomeAmbiguousError):
        client.send_text("message", conversation=QwenHttpConversation("chat-1"))


def test_stale_page_expiry_hint_does_not_block_first_http_send():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/chats/new"):
            return _Reply({"data": {"id": "chat-stale"}})
        return _Reply(
            [
                {"choices": [{"delta": {"content": "hello"}, "finish_reason": "stop"}]},
                "[DONE]",
            ]
        )

    client = QwenHttpClient(
        QwenHttpCredentials("possibly-valid", expires_at=1),
        opener=open_,
    )
    response = client.send_text("message")
    assert response.text == "hello"
    assert len(requests) == 2
    assert all(request.get_method() == "POST" for request in requests)


def test_expired_auth_refreshes_before_write_only_with_configured_path():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        return _Reply({"data": {"access_token": "new-token"}})

    client = QwenHttpClient(
        QwenHttpCredentials("old-token", {"session": "example"}, expires_at=1),
        opener=open_,
        refresh_path="/api/v1/auths/refresh",
    )
    client._preflight_auth()
    assert client.credentials.access_token == "new-token"
    assert len(requests) == 1
    assert requests[0].get_method() == "GET"


def test_expired_auth_does_not_invent_or_call_refresh_endpoint():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        return _Reply({"data": {"id": "chat-stale"}})

    client = QwenHttpClient(
        QwenHttpCredentials("possibly-valid", expires_at=1),
        opener=open_,
    )
    client.create_chat()
    assert len(requests) == 1
    assert "/api/v2/chats/new" in requests[0].full_url


def test_refresh_is_pre_send_only():
    requests = []

    def open_(request, timeout):
        requests.append(request)
        return _Reply({"data": {"access_token": "renewed"}})

    creds = QwenHttpCredentials("old", {"session": "secret"}, expires_at=1)
    client = QwenHttpClient(creds, opener=open_, refresh_path="/api/v1/auths/refresh")
    client.refresh()
    assert creds.access_token == "renewed"
    assert len(requests) == 1 and requests[0].get_method() == "GET"


def test_qwen_cookie_rotation_notifies_store_once():
    captured = []

    def open_(request, timeout):
        reply = _Reply({"data": {"id": "chat-cookies"}})
        reply.headers.add_header("Set-Cookie", "session=rotated; Path=/; HttpOnly")
        return reply

    creds = QwenHttpCredentials("sample", {"session": "initial"})
    client = QwenHttpClient(creds, opener=open_, on_auth_updated=captured.append)
    client.create_chat()
    assert creds.cookies["session"] == "rotated"
    assert len(captured) == 1
