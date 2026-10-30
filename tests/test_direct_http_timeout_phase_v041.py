"""Offline Direct HTTP timeout-phase attribution; no network or request replay."""

from __future__ import annotations

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError


@pytest.mark.parametrize(
    ("method", "url", "expected"),
    [
        (
            "POST",
            "https://chatgpt.com/backend-api/files",
            "file_registration",
        ),
        (
            "PUT",
            "https://upload.example.invalid/blob/secret?sig=DO-NOT-EXPOSE",
            "file_upload",
        ),
        (
            "POST",
            "https://chatgpt.com/backend-api/files/PRIVATE-FILE-ID/uploaded",
            "file_finalize",
        ),
        (
            "POST",
            "https://chatgpt.com/backend-api/sentinel/chat-requirements/prepare",
            "sentinel_prepare",
        ),
        (
            "POST",
            "https://chatgpt.com/backend-api/sentinel/chat-requirements/finalize",
            "sentinel_finalize",
        ),
        (
            "GET",
            "https://chatgpt.com/backend-api/conversations/PRIVATE-CHAT-ID?num_turns=20",
            "canonical_get",
        ),
        (
            "GET",
            "https://chatgpt.com/backend-api/conversations?offset=0&limit=10",
            "conversation_list",
        ),
        (
            "POST",
            "https://chatgpt.com/backend-api/f/conversation",
            "conversation_write",
        ),
        (
            "GET",
            "https://chatgpt.com/",
            "session_bootstrap",
        ),
        (
            "POST",
            "https://example.invalid/opaque?token=HIDDEN",
            "other_http",
        ),
    ],
)
def test_transport_timeout_attribution_is_allowlisted_and_never_exposes_urls(
    monkeypatch, method, url, expected
):
    calls = []

    def failing(self, method, url, headers, body=None, **kwargs):
        calls.append((method, url))
        raise RequestError(
            "curl failed: exit_code=28; http_status=200",
            status_code=200,
            request_stage="transport_timeout",
        )

    monkeypatch.setattr(ChatGPTWebClient, "_run_curl", failing)
    client = object.__new__(BrowserlessHTTPClient)

    with pytest.raises(RequestError) as caught:
        client._run_curl(method, url, {"authorization": "PRIVATE"})

    error = caught.value
    assert error.request_stage == "transport_timeout"
    assert error.status_code == 200
    assert error.endpoint == expected
    assert calls == [(method, url)]
    assert url not in str(error)
    assert "DO-NOT-EXPOSE" not in error.endpoint
    assert "PRIVATE" not in error.endpoint
    assert "HIDDEN" not in error.endpoint


def test_nontransport_request_error_is_unchanged(monkeypatch):
    original = RequestError(
        "file registration failed", status_code=400, request_stage="file_create"
    )
    calls = []

    def failing(self, method, url, headers, body=None, **kwargs):
        calls.append(method)
        raise original

    monkeypatch.setattr(ChatGPTWebClient, "_run_curl", failing)
    client = object.__new__(BrowserlessHTTPClient)
    with pytest.raises(RequestError) as caught:
        client._run_curl("POST", "https://chatgpt.com/backend-api/files", {})
    assert caught.value is original
    assert calls == ["POST"]


def test_non_timeout_curl_failure_keeps_transport_stage(monkeypatch):
    calls = []

    def failing(self, method, url, headers, body=None, **kwargs):
        calls.append(method)
        raise RequestError(
            "curl failed: exit_code=18; http_status=200",
            status_code=200,
            request_stage="transport",
        )

    monkeypatch.setattr(ChatGPTWebClient, "_run_curl", failing)
    client = object.__new__(BrowserlessHTTPClient)
    with pytest.raises(RequestError) as caught:
        client._run_curl(
            "PUT",
            "https://upload.example.invalid/private?sig=SECRET",
            {},
        )
    assert caught.value.endpoint == "file_upload"
    assert caught.value.request_stage == "transport"
    assert "SECRET" not in str(caught.value)
    assert calls == ["PUT"]
