from __future__ import annotations

import pytest

from chatgpt_web_adapter import AuthData, RequestError
from chatgpt_web_adapter.web_session import (
    bootstrap_web_session,
    gate_get_ready_requirements,
    redact_web_session_headers,
)


class _FakeClient:
    def __init__(self, *, cookies=None, turnstile_token=None) -> None:
        self.auth = AuthData(
            accessToken="token",
            cookies=cookies or {},
            turnstile_token=turnstile_token,
        )
        self.base_headers = {"content-type": "application/json"}
        self.bootstrap_calls = 0
        self._web_session_bootstrapped = False
        self.debug_trace_sanitize = True

    def _build_headers(self, extra=None):
        headers = dict(self.base_headers)
        if self.auth.cookies:
            headers["cookie"] = "; ".join(
                f"{key}={value}" for key, value in self.auth.cookies.items()
            )
        if extra:
            headers.update({key: value for key, value in extra.items() if value is not None})
        return headers

    def _run_curl(self, method, url, headers, *, follow_redirects=False):
        assert method == "GET"
        assert url == "https://chatgpt.com/"
        assert follow_redirects is True
        self.bootstrap_calls += 1
        self.auth.cookies["oai-did"] = "server-issued-device"
        return 200, b"", ""


def test_bootstrap_reuses_existing_oai_did_without_network() -> None:
    client = _FakeClient(cookies={"oai-did": "existing-device"})

    assert bootstrap_web_session(client) is True
    assert client.bootstrap_calls == 0
    assert client.base_headers["oai-device-id"] == "existing-device"


def test_bootstrap_fetches_server_device_cookie_once() -> None:
    client = _FakeClient()

    assert bootstrap_web_session(client) is True
    assert bootstrap_web_session(client) is True
    assert client.bootstrap_calls == 1
    assert client.base_headers["oai-device-id"] == "server-issued-device"


def test_turnstile_gate_blocks_before_write_without_browser_token() -> None:
    client = _FakeClient(cookies={"oai-did": "device"})
    original_calls = []

    def original(_self):
        original_calls.append(True)
        return {"token": "requirements", "turnstile": {"required": True}}, "proof"

    gated = gate_get_ready_requirements(original)

    with pytest.raises(RequestError) as exc_info:
        gated(client)

    assert original_calls == [True]
    assert exc_info.value.request_stage == "turnstile_gate"
    assert "TURNSTILE_REQUIRED" in str(exc_info.value)


def test_turnstile_gate_accepts_legitimate_supplied_browser_token() -> None:
    client = _FakeClient(
        cookies={"oai-did": "device"},
        turnstile_token="browser-derived-token",
    )

    def original(_self):
        return {"token": "requirements", "turnstile": {"required": True}}, "proof"

    gated = gate_get_ready_requirements(original)

    requirements, proof = gated(client)

    assert requirements["turnstile"]["required"] is True
    assert proof == "proof"


def test_turnstile_gate_allows_non_turnstile_requirements() -> None:
    client = _FakeClient(cookies={"oai-did": "device"})

    def original(_self):
        return {"token": "requirements", "turnstile": {"required": False}}, "proof"

    gated = gate_get_ready_requirements(original)

    requirements, proof = gated(client)

    assert requirements["turnstile"]["required"] is False
    assert proof == "proof"


def test_sensitive_web_session_headers_are_redacted_in_sanitized_traces() -> None:
    client = _FakeClient()

    def original(_self, key, value):
        return value

    sanitize = redact_web_session_headers(original)

    assert sanitize(client, "oai-device-id", "device-secret") == "<redacted>"
    assert sanitize(client, "x-conduit-token", "conduit-secret") == "<redacted>"
    assert sanitize(client, "accept", "application/json") == "application/json"
