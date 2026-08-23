from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessChallengeBoundaryError,
    BrowserlessProtocolDriftError,
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.product_capabilities import CapabilityState
from chatgpt_web_adapter.product_contract import product_runtime_contract
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime, assemble_product_runtime
from chatgpt_web_adapter.types import ChatConversation, ChatMessage, ChatResponse


class _DirectClient:
    def __init__(
        self,
        *,
        prepare=None,
        prepare_status: int = 200,
        finalize=None,
        finalize_status: int = 200,
        send_error: Exception | None = None,
        canonical_text: str = "canonical answer",
        status: str = "completed",
        canonical_message_id: str = "canonical-message",
    ) -> None:
        self.prepare = prepare or {
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": False},
            "so": {"required": False},
            "turnstile": {"required": False},
        }
        self.prepare_status = prepare_status
        self.finalize = finalize or {
            "persona": "chatgpt-test",
            "token": "requirements-token",
            "expire_after": 60,
            "expire_at": 9999999999,
        }
        self.finalize_status = finalize_status
        self.send_error = send_error
        self.canonical_text = canonical_text
        self.status_value = status
        self.canonical_message_id = canonical_message_id
        self.timeout = 60.0
        self.prepare_calls = 0
        self.finalize_calls = 0
        self.send_calls = 0
        self.ready_requirements_calls = 0
        self.attach_calls = []
        self.sent_conversations = []
        self.sent_prompts = []
        self.finalize_payloads = []

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **(extra or {})}

    def _json_request(self, method, url, payload, headers):
        assert method == "POST"
        assert "authorization" in headers
        if url.endswith("/chat-requirements/prepare"):
            self.prepare_calls += 1
            assert payload == {"p": None}
            return self.prepare_status, self.prepare
        if url.endswith("/chat-requirements/finalize"):
            self.finalize_calls += 1
            self.finalize_payloads.append(dict(payload))
            assert payload == {
                "prepare_token": "prepare-token",
                "proofofwork": None,
                "turnstile": None,
            }
            return self.finalize_status, self.finalize
        raise AssertionError(f"unexpected direct request URL: {url}")

    def _get_chat_requirements(self):
        raise AssertionError("browserless transport must not call legacy single-step requirements")

    def _build_proof_header(self, requirements):
        raise AssertionError("browserless transport must not generate proof-of-work")

    def send(self, prompt, *, conversation=None, on_token=None, on_event=None, **kwargs):
        self.send_calls += 1
        self.sent_prompts.append(prompt)
        self.sent_conversations.append(conversation)
        if self.send_error is not None:
            raise self.send_error
        requirements, proof = self._get_ready_requirements()
        self.ready_requirements_calls += 1
        assert requirements["token"] == "requirements-token"
        assert requirements["proofofwork"] == {"required": False}
        assert requirements["turnstile"] == {"required": False}
        assert proof is None
        if on_token is not None:
            on_token("stream ")
            on_token("answer")
        return ChatResponse(
            text="stream answer",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="stream-message",
                parent_message_id="stream-message",
            ),
        )

    def get_status(self, conversation):
        return SimpleNamespace(status=self.status_value, finish_reason="stop")

    def get_messages(self, conversation, **kwargs):
        return [
            ChatMessage(role="user", text="prompt", message_id="user-message"),
            ChatMessage(
                role="assistant",
                text=self.canonical_text,
                message_id=self.canonical_message_id,
                model="gpt-test",
                finish_reason="stop",
            ),
        ]

    def attach_conversation(self, conversation):
        self.attach_calls.append(conversation)
        return SimpleNamespace(
            conversation=ChatConversation(
                conversation_id="attached-conversation",
                message_id="attached-parent",
                parent_message_id="attached-parent",
            )
        )


def _runtime(client: _DirectClient) -> ChatGPTProductRuntime:
    return ChatGPTProductRuntime(
        client,
        transport="browserless-request",
        write_transport=BrowserlessRequestTransport(client),
    )


def test_happy_path_is_one_direct_write_with_two_phase_token_and_canonical_finality() -> None:
    client = _DirectClient(canonical_text="canonical answer")
    runtime = _runtime(client)
    tokens = []
    events = []

    execution = runtime.send_text_observed(
        "hello",
        on_token=tokens.append,
        on_event=events.append,
    )

    assert client.prepare_calls == 1
    assert client.finalize_calls == 1
    assert client.send_calls == 1
    assert client.ready_requirements_calls == 1
    assert client.sent_prompts == ["hello"]
    assert client.finalize_payloads == [
        {
            "prepare_token": "prepare-token",
            "proofofwork": None,
            "turnstile": None,
        }
    ]
    assert tokens == ["stream ", "answer"]
    assert execution.transport == "browserless-request"
    assert execution.response.text == "canonical answer"
    assert execution.response.conversation.message_id == "canonical-message"
    assert execution.provenance is not None
    assert execution.provenance.completion.canonical_completion_proven is True
    assert execution.observation.sentinel_protocol == "TWO_PHASE_PREPARE_FINALIZE"
    assert execution.observation.reconciliation == "STREAM_REVISED_BY_CANONICAL"
    assert [event["type"] for event in events] == [
        "assistant_text_delta",
        "assistant_text_delta",
        "canonical_text_finalized",
    ]
    assert events[-1]["text"] == "canonical answer"


def test_two_phase_path_never_calls_legacy_requirements_or_proof_generation() -> None:
    client = _DirectClient(canonical_text="stream answer")

    response = BrowserlessRequestTransport(client).send_text("hello")

    assert response.text == "stream answer"
    assert client.prepare_calls == 1
    assert client.finalize_calls == 1
    assert client.send_calls == 1


@pytest.mark.parametrize("challenge", ["proofofwork", "turnstile", "so"])
def test_required_current_challenge_fails_after_prepare_before_finalize_and_write(
    challenge: str,
) -> None:
    prepare = {
        "persona": "chatgpt-test",
        "prepare_token": "prepare-token",
        "proofofwork": {"required": False},
        "so": {"required": False},
        "turnstile": {"required": False},
    }
    prepare[challenge] = {"required": True}
    client = _DirectClient(prepare=prepare)

    with pytest.raises(BrowserlessChallengeBoundaryError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert challenge in error.challenges
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.prepare_calls == 1
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_unknown_future_required_descriptor_also_fails_closed() -> None:
    client = _DirectClient(
        prepare={
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": False},
            "so": {"required": False},
            "turnstile": {"required": False},
            "future_protection": {"required": True, "shape": "unknown"},
        }
    )

    with pytest.raises(BrowserlessChallengeBoundaryError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    assert captured.value.challenges == ("future_protection",)
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_prepare_http_403_is_challenge_boundary_not_write_failure() -> None:
    client = _DirectClient(prepare_status=403)

    with pytest.raises(BrowserlessChallengeBoundaryError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    assert captured.value.status_code == 403
    assert captured.value.request_stage == "browserless_sentinel_prepare"
    assert captured.value.write_may_have_been_submitted is False
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_finalize_http_403_is_challenge_boundary_before_write() -> None:
    client = _DirectClient(finalize_status=403)

    with pytest.raises(BrowserlessChallengeBoundaryError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    assert captured.value.status_code == 403
    assert captured.value.request_stage == "browserless_sentinel_finalize"
    assert client.prepare_calls == 1
    assert client.finalize_calls == 1
    assert client.send_calls == 0


def test_missing_prepare_contract_key_is_protocol_drift() -> None:
    client = _DirectClient(
        prepare={
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": False},
            "turnstile": {"required": False},
        }
    )

    with pytest.raises(BrowserlessProtocolDriftError, match="missing observed keys"):
        BrowserlessRequestTransport(client).send_text("hello")

    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_missing_finalize_token_is_protocol_drift() -> None:
    client = _DirectClient(
        finalize={
            "persona": "chatgpt-test",
            "expire_after": 60,
            "expire_at": 9999999999,
        }
    )

    with pytest.raises(BrowserlessProtocolDriftError, match="missing observed keys"):
        BrowserlessRequestTransport(client).send_text("hello")

    assert client.send_calls == 0


def test_non_boolean_required_flag_is_protocol_drift() -> None:
    client = _DirectClient(
        prepare={
            "persona": "chatgpt-test",
            "prepare_token": "prepare-token",
            "proofofwork": {"required": "yes"},
            "so": {"required": False},
            "turnstile": {"required": False},
        }
    )

    with pytest.raises(BrowserlessProtocolDriftError, match="required is not boolean"):
        BrowserlessRequestTransport(client).send_text("hello")

    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_browser_or_sentinel_provider_is_rejected_at_construction() -> None:
    client = _DirectClient()
    client._sentinel_bundle_provider = lambda *args, **kwargs: object()

    with pytest.raises(ValueError, match="forbids configured Sentinel"):
        BrowserlessRequestTransport(client)


def test_continuation_uses_canonical_attach_before_direct_write() -> None:
    client = _DirectClient(canonical_text="canonical answer")

    BrowserlessRequestTransport(client).send_text(
        "continue",
        conversation="conversation-from-caller",
    )

    assert client.attach_calls == ["conversation-from-caller"]
    sent = client.sent_conversations[0]
    assert isinstance(sent, ChatConversation)
    assert sent.conversation_id == "attached-conversation"
    assert sent.parent_message_id == "attached-parent"


def test_canonical_readback_must_advance_beyond_prewrite_parent() -> None:
    client = _DirectClient(canonical_message_id="attached-parent")

    with pytest.raises(BrowserlessRequestTransportError, match="did not advance") as captured:
        BrowserlessRequestTransport(client).send_text(
            "continue",
            conversation="conversation-from-caller",
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.write_may_have_been_submitted is True


def test_prewrite_conversation_prepare_failure_is_not_marked_ambiguous() -> None:
    client = _DirectClient(
        send_error=RequestError(
            "prepare failed",
            status_code=409,
            endpoint="conversation/prepare",
            request_stage="conversation_prepare",
        )
    )

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.write_may_have_been_submitted is False
    assert error.reconciliation_required is False
    assert client.send_calls == 1


def test_unknown_write_outcome_requires_reconciliation_and_is_not_retried() -> None:
    client = _DirectClient(
        send_error=RequestError(
            "stream disconnected",
            status_code=502,
            endpoint="conversation",
            request_stage="conversation_stream",
        )
    )

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text("hello")

    error = captured.value
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert client.send_calls == 1
    assert client.prepare_calls == 1
    assert client.finalize_calls == 1


def test_canonical_finality_failure_requires_reconciliation() -> None:
    client = _DirectClient(status="running")

    with pytest.raises(BrowserlessRequestTransportError) as captured:
        BrowserlessRequestTransport(client).send_text(
            "hello",
            timeout=0.01,
            poll_interval=0.005,
        )

    assert captured.value.request_stage == "canonical_reconciliation"
    assert captured.value.write_may_have_been_submitted is True
    assert captured.value.reconciliation_required is True
    assert client.send_calls == 1


def test_capabilities_are_feature_scoped_while_transport_stays_experimental() -> None:
    client = _DirectClient()
    runtime = _runtime(client)
    capabilities = runtime.capabilities()

    assert capabilities.transport == "browserless-request"
    assert capabilities.transport_support_tier.value == "EXPERIMENTAL"
    assert capabilities.require("text_turns").state is CapabilityState.AVAILABLE
    assert capabilities.require("streaming").state is CapabilityState.AVAILABLE
    assert capabilities.require("temporary_chat").state is CapabilityState.UNKNOWN
    assert capabilities.require("model_selection").state is CapabilityState.UNKNOWN

    contract = product_runtime_contract(runtime)
    assert contract.transport == "browserless-request"
    assert contract.transport_support_tier.value == "EXPERIMENTAL"
    assert contract.automatic_write_retry is False
    assert contract.fallback_transport is None
    assert contract.legacy_direct_write_fallback is False
    assert contract.incremental_observation_is_canonical_finality is False

    governance = runtime.governance()
    assert governance["browserless_sentinel_protocol"] == "TWO_PHASE_PREPARE_FINALIZE"
    assert governance["browserless_legacy_single_step_requirements_fallback"] is False


def test_profile_temporary_and_browser_authority_requests_fail_before_network() -> None:
    client = _DirectClient()
    runtime = _runtime(client)

    with pytest.raises(ValueError, match="model profile selection is unavailable"):
        runtime.send_text("hello", model_profile="DEEP")
    with pytest.raises(RuntimeError, match="PRODUCT_CONVERSATION_MODE_UNAVAILABLE"):
        runtime.send_text("hello", conversation_mode="temporary")
    with pytest.raises(ValueError, match="browser authority policy overrides are unavailable"):
        runtime.send_text("hello", browser_authority_policy="TURN_SCOPED")

    assert client.prepare_calls == 0
    assert client.finalize_calls == 0
    assert client.send_calls == 0


def test_runtime_assembly_selects_browserless_without_provider_or_fallback() -> None:
    client = _DirectClient()

    runtime = assemble_product_runtime(
        transport="browserless-request",
        client=client,
    )

    assert runtime.transport == "browserless-request"
    assert isinstance(runtime.write_transport, BrowserlessRequestTransport)
    assert runtime.governance()["fallback_transport"] is None
    assert runtime.governance()["browser_fallback_supported"] is False

    with pytest.raises(ValueError, match="does not accept browser-native"):
        assemble_product_runtime(
            transport="browserless-request",
            client=_DirectClient(),
            provider=object(),
        )
