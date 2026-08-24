from __future__ import annotations

from contextvars import Context
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.sentinel_bundle import prepared_send_active
from chatgpt_web_adapter.types import ChatMessage


_PREPARE_PATH = "/backend-api/f/conversation/prepare"
_WRITE_PATH = "/backend-api/f/conversation"
_SENTINEL_PREPARE_PATH = "/backend-api/sentinel/chat-requirements/prepare"
_SENTINEL_FINALIZE_PATH = "/backend-api/sentinel/chat-requirements/finalize"


class _IsolationClient:
    def __init__(self, *, failure_at: str | None = None) -> None:
        self.failure_at = failure_at
        self.timeout = 60.0
        self.base_headers = {"user-agent": "test-agent"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.delegate_ready_calls = 0
        self.delegate_header_calls = 0
        self.delegate_refill_calls = 0
        self.send_calls = 0

    def _get_ready_requirements(self):
        self.delegate_ready_calls += 1
        return {"token": "foreign-token"}, "foreign-proof"

    def _build_headers(self, extra=None):
        target_path = dict(extra or {}).get("x-openai-target-path")
        if self.failure_at == "prepare_headers" and target_path == _SENTINEL_PREPARE_PATH:
            raise OSError("prepare headers unavailable")
        if self.failure_at == "finalize_headers" and target_path == _SENTINEL_FINALIZE_PATH:
            raise OSError("finalize headers unavailable")
        self.delegate_header_calls += 1
        return {"delegated": "yes", **(extra or {})}

    def _json_request(self, method, url, payload, headers):
        assert method == "POST"
        if url.endswith("/chat-requirements/prepare"):
            if self.failure_at == "prepare_request":
                raise OSError("prepare transport unavailable")
            return 200, {
                "persona": "chatgpt-test",
                "prepare_token": "prepare-token",
                "proofofwork": {"required": False},
                "so": {"required": False},
                "turnstile": {"required": False},
            }
        if url.endswith("/chat-requirements/finalize"):
            if self.failure_at == "finalize_request":
                raise OSError("finalize transport unavailable")
            return 200, {
                "persona": "chatgpt-test",
                "token": "requirements-token",
                "expire_after": 60,
                "expire_at": 9999999999,
            }
        raise AssertionError(f"unexpected URL: {url}")

    def start_sentinel_bundle_refill(self, *args, **kwargs):
        self.delegate_refill_calls += 1
        return "foreign-refill"

    def send(self, prompt, **kwargs):
        self.send_calls += 1
        raise AssertionError("send is not expected in these focused tests")

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", finish_reason="stop")

    def get_messages(self, conversation, **kwargs):
        return [ChatMessage(role="assistant", text="answer", message_id="message-1")]

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation=conversation)


def test_prepared_binding_is_visible_only_to_own_execution_context() -> None:
    client = _IsolationClient()
    transport = BrowserlessRequestTransport(client)
    requirements = {
        "token": "browserless-token",
        "persona": "chatgpt-test",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    write_state = {"final_write_started": False}

    original_ready = client._get_ready_requirements
    original_headers = client._build_headers
    original_refill = client.start_sentinel_bundle_refill

    with transport._bind_current_prepared_write(requirements, write_state=write_state):
        assert prepared_send_active() is True

        foreign = Context()
        assert foreign.run(prepared_send_active) is False
        assert foreign.run(client._get_ready_requirements) == (
            {"token": "foreign-token"},
            "foreign-proof",
        )
        foreign_headers = foreign.run(
            client._build_headers,
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
            },
        )
        assert foreign_headers["delegated"] == "yes"
        assert "x-oai-turn-trace-id" not in foreign_headers
        assert write_state["final_write_started"] is False
        assert foreign.run(client.start_sentinel_bundle_refill) == "foreign-refill"

        owner_requirements, owner_proof = client._get_ready_requirements()
        assert owner_requirements["token"] == "browserless-token"
        assert owner_proof is None
        owner_headers = client._build_headers(
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
            }
        )
        assert "x-oai-turn-trace-id" in owner_headers
        assert "delegated" not in owner_headers
        assert write_state["final_write_started"] is True
        assert client.start_sentinel_bundle_refill() is False

    assert prepared_send_active() is False
    assert client._get_ready_requirements == original_ready
    assert client._build_headers == original_headers
    assert client.start_sentinel_bundle_refill == original_refill
    assert client.delegate_ready_calls == 1
    assert client.delegate_header_calls == 1
    assert client.delegate_refill_calls == 1


@pytest.mark.parametrize(
    ("failure_at", "expected_stage"),
    [
        ("prepare_headers", "browserless_sentinel_prepare"),
        ("prepare_request", "browserless_sentinel_prepare"),
        ("finalize_headers", "browserless_sentinel_finalize"),
        ("finalize_request", "browserless_sentinel_finalize"),
    ],
)
def test_generic_preflight_operational_failures_are_structured_zero_write(
    failure_at: str,
    expected_stage: str,
) -> None:
    client = _IsolationClient(failure_at=failure_at)

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.request_stage == expected_stage
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.send_calls == 0
