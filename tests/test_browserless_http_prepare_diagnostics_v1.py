"""Privacy-safe Sentinel prepare error classifications for Direct HTTP."""

from __future__ import annotations

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.exceptions import RequestError


class _ValidatedPrepareReached(Exception):
    """Stop at the first step after successful prepare validation."""


class _FakeSentinel:
    def __init__(self, status, response):
        self.status = status
        self.response = response
        self.prepare_requests = 0
        self.solve_requests = 0

    def _js(self, payload):
        if payload["mode"] == "prepare":
            return {"prepareInput": "synthetic"}
        self.solve_requests += 1
        raise _ValidatedPrepareReached

    def _build_headers(self, extra):
        return dict(extra)

    def _json_request(self, method, url, payload, headers):
        self.prepare_requests += 1
        assert method == "POST"
        assert url.endswith("/sentinel/chat-requirements/prepare")
        assert payload == {"p": "synthetic"}
        return self.status, self.response


@pytest.mark.parametrize(
    ("status", "response", "expected"),
    [
        (403, {"prepare_token": "synthetic"}, "http_status"),
        (429, "private-response-must-not-appear", "http_status"),
        (200, "private-response-must-not-appear", "non_object_response"),
        (200, [], "non_object_response"),
        (200, None, "non_object_response"),
        (200, {}, "missing_prepare_token"),
        (200, {"prepare_token": None}, "missing_prepare_token"),
        (200, {"prepare_token": 17}, "missing_prepare_token"),
        (200, {"prepare_token": "  "}, "missing_prepare_token"),
    ],
)
def test_prepare_fails_closed_without_leaking_body(status, response, expected):
    fake = _FakeSentinel(status, response)
    with pytest.raises(RequestError) as caught:
        BrowserlessHTTPClient._acquire_http_bundle(fake, fake)
    error = caught.value
    assert str(error).startswith("browserless Sentinel prepare rejected:")
    assert expected in str(error)
    assert f"http_status={status}" in str(error)
    assert f"response_type={type(response).__name__}" in str(error)
    assert "private-response-must-not-appear" not in str(error)
    assert "synthetic" not in str(error)
    assert error.body_preview is None
    assert error.request_stage == "sentinel_prepare"
    assert error.endpoint == "/backend-api/sentinel/chat-requirements/prepare"
    assert error.status_code == status
    assert fake.prepare_requests == 1
    assert fake.solve_requests == 0


def test_valid_prepare_still_reaches_existing_followup_without_finalizing():
    fake = _FakeSentinel(200, {"prepare_token": "synthetic"})
    with pytest.raises(_ValidatedPrepareReached):
        BrowserlessHTTPClient._acquire_http_bundle(fake, fake)
    assert fake.prepare_requests == 1
    assert fake.solve_requests == 1
