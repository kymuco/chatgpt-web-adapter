from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessProtocolDriftError,
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.sentinel_bundle import prepared_send_active
from chatgpt_web_adapter.types import ChatConversation, ChatMessage, ChatResponse


_PREPARE_PATH = "/backend-api/f/conversation/prepare"
_WRITE_PATH = "/backend-api/f/conversation"


class _SafetyClient:
    def __init__(
        self,
        *,
        prepare: dict | None = None,
        send_mode: str = "success",
        attach_error: Exception | None = None,
    ) -> None:
        self.prepare = prepare or {
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": False},
            "so": {"required": False},
            "turnstile": {"required": False},
        }
        self.finalize = {
            "persona": "chatgpt-test",
            "token": "requirements-token",
            "expire_after": 60,
            "expire_at": 9999999999,
        }
        self.send_mode = send_mode
        self.attach_error = attach_error
        self.timeout = 60.0
        self.base_headers = {"user-agent": "test-agent"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.prepare_calls = 0
        self.finalize_calls = 0
        self.send_calls = 0
        self.attach_calls = 0
        self.refill_calls = 0

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **(extra or {})}

    def _json_request(self, method, url, payload, headers):
        assert method == "POST"
        if url.endswith("/chat-requirements/prepare"):
            self.prepare_calls += 1
            return 200, self.prepare
        if url.endswith("/chat-requirements/finalize"):
            self.finalize_calls += 1
            return 200, self.finalize
        raise AssertionError(f"unexpected URL: {url}")

    def _get_ready_requirements(self):
        raise AssertionError(
            "browserless owner must use its execution-local finalized requirements"
        )

    def start_sentinel_bundle_refill(self, *args, **kwargs):
        self.refill_calls += 1
        return True

    def send(self, prompt, *, conversation=None, on_token=None, on_event=None, **kwargs):
        self.send_calls += 1
        assert prepared_send_active() is True

        self._build_headers(
            {
                "x-openai-target-path": _PREPARE_PATH,
                "x-openai-target-route": _PREPARE_PATH,
            }
        )
        if self.send_mode == "prepare_transport_failure":
            raise RequestError("curl failed before final write", request_stage="transport")

        requirements, proof = self._get_ready_requirements()
        assert requirements["token"] == "requirements-token"
        assert proof is None

        # The real ChatGPTWebClient.send() attempts a Sentinel refill once the
        # prepared path is active. Browserless must suppress that historical hook.
        self.start_sentinel_bundle_refill(on_event=on_event)

        self._build_headers(
            {
                "x-openai-target-path": _WRITE_PATH,
                "x-openai-target-route": _WRITE_PATH,
            }
        )
        if self.send_mode == "final_transport_failure":
            raise RequestError("curl failed on final write", request_stage="transport")

        if on_token is not None:
            on_token("answer")
        return ChatResponse(
            text="answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="canonical-message",
                parent_message_id="canonical-message",
            ),
        )

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", finish_reason="stop")

    def get_messages(self, conversation, **kwargs):
        return [
            ChatMessage(role="user", text="prompt", message_id="user-message"),
            ChatMessage(
                role="assistant",
                text="answer",
                message_id="canonical-message",
                finish_reason="stop",
            ),
        ]

    def attach_conversation(self, conversation):
        self.attach_calls += 1
        if self.attach_error is not None:
            raise self.attach_error
        return SimpleNamespace(
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="parent-message",
                parent_message_id="parent-message",
            )
        )


@pytest.mark.parametrize(
    "provider_name",
    ["_sentinel_challenge_provider", "_sentinel_bundle_provider"],
)
def test_provider_added_after_construction_fails_before_any_network(provider_name: str) -> None:
    client = _SafetyClient()
    transport = BrowserlessRequestTransport(client)
    setattr(client, provider_name, lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("provider must never be invoked")
    ))

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        transport.send_text("hello")

    error = captured.value
    assert error.request_stage == "browserless_provider_guard"
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.prepare_calls == 0
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_future_mapping_without_required_is_protocol_drift_before_finalize() -> None:
    client = _SafetyClient(
        prepare={
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": False},
            "so": {"required": False},
            "turnstile": {"required": False},
            "future_protection": {"nonce": "unclassified"},
        }
    )

    with pytest.raises(BrowserlessProtocolDriftError, match="future_protection.required is missing"):
        BrowserlessRequestTransport(client).send_text("hello")

    assert client.prepare_calls == 1
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_generic_transport_failure_during_conversation_prepare_is_prewrite() -> None:
    client = _SafetyClient(send_mode="prepare_transport_failure")

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.request_stage == "conversation_prepare"
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.send_calls == 1


def test_generic_transport_failure_after_final_headers_is_ambiguous() -> None:
    client = _SafetyClient(send_mode="final_transport_failure")

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.request_stage == "transport"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert client.send_calls == 1


def test_continuation_attach_failure_is_structured_zero_write_error() -> None:
    client = _SafetyClient(
        attach_error=RequestError("canonical attach unavailable", request_stage="transport")
    )

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text(
            "continue",
            conversation="conversation-1",
        )

    error = captured.value
    assert error.request_stage == "canonical_attach"
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.attach_calls == 1
    assert client.prepare_calls == 0
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_historical_sentinel_refill_hook_is_suppressed_and_restored() -> None:
    client = _SafetyClient()
    transport = BrowserlessRequestTransport(client)

    response = transport.send_text("hello")

    assert response.text == "answer"
    assert client.refill_calls == 0

    # The instance override is execution-local: the client's normal method is
    # restored after the browserless turn rather than permanently mutated.
    assert client.start_sentinel_bundle_refill() is True
    assert client.refill_calls == 1


class _MinimalRealClient(ChatGPTWebClient):
    def __init__(self) -> None:
        # Avoid any auth/network bootstrap; this test only verifies which send
        # callable the transport captures for a real ChatGPTWebClient instance.
        self.base_headers = {"user-agent": "test-agent"}
        self.auth = SimpleNamespace(accessToken="token", cookies={}, turnstile_token=None)
        self.timeout = 60.0


def test_real_client_captures_raw_send_below_installed_sentinel_wrapper() -> None:
    client = _MinimalRealClient()
    transport = BrowserlessRequestTransport(client)

    assert transport._direct_send.__func__ is adapter._original_send
