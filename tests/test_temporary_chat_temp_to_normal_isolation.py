from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_provenance import (
    ConversationMode,
    ConversationModeEvidenceSource,
)
from chatgpt_web_adapter.product_runtime import (
    ChatGPTProductRuntime,
    ProductConversationModeUnavailableError,
)
from chatgpt_web_adapter.product_transport import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    ProductRuntimeExecution,
)


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


def _response(conversation_id: str = "normal-conversation"):
    return SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id=conversation_id,
            message_id="assistant-normal",
            finish_reason=None,
        ),
        request=SimpleNamespace(observed_model="gpt-test"),
    )


class _Transport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self) -> None:
        self.write_calls: list[tuple[str, str, dict]] = []

    def health(self, conversation=None):
        raise AssertionError("health should not be consulted")

    def capabilities(self):
        raise AssertionError("capabilities should not be consulted")

    def send_text(self, text, **kwargs):
        self.write_calls.append(("send_text", text, kwargs))
        return _response(str(kwargs.get("conversation") or "normal-new-chat"))

    def send_text_observed(self, text, **kwargs):
        self.write_calls.append(("send_text_observed", text, kwargs))
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=_response(str(kwargs.get("conversation") or "normal-new-chat")),
            observation={
                "runtime_tab_id": 77,
                "normal_observation": text,
            },
        )

    def governance(self):
        return {
            "transport": self.transport_id,
            "product_semantics": "ordinary-chatgpt",
            "canonical_readback_required": True,
        }


def test_denied_temporary_then_default_normal_dispatches_once_on_same_runtime() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text("temporary-attempt", conversation_mode="temporary")

    assert transport.write_calls == []
    denied_mode = caught.value.conversation_mode_provenance
    assert denied_mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert denied_mode.observed_conversation_mode is ConversationMode.UNKNOWN

    response = runtime.send_text("normal-after-temp")

    assert response.conversation.conversation_id == "normal-new-chat"
    assert transport.write_calls == [
        (
            "send_text",
            "normal-after-temp",
            {
                "conversation": None,
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]


def test_temporary_identity_is_not_inherited_by_following_normal_request() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)
    temporary_identity = "temporary-product-conversation-id"

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text(
            "blocked-temp",
            conversation=temporary_identity,
            conversation_mode="temporary",
        )

    runtime.send_text("fresh-normal", conversation_mode="normal")

    assert transport.write_calls[0][2]["conversation"] is None
    assert temporary_identity not in repr(transport.write_calls)


def test_explicit_normal_identity_overrides_prior_denied_temporary_identity() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text(
            "blocked-temp",
            conversation="temporary-id",
            conversation_mode="temporary",
        )

    runtime.send_text(
        "normal-continuation",
        conversation="ordinary-id",
        conversation_mode="normal",
    )

    assert transport.write_calls == [
        (
            "send_text",
            "normal-continuation",
            {
                "conversation": "ordinary-id",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]


def test_denied_temporary_provenance_does_not_leak_into_following_normal_execution() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text_observed("blocked-temp", conversation_mode="temporary")

    denied = caught.value.conversation_mode_provenance.to_dict()
    execution = runtime.send_text_observed(
        "normal-observed",
        conversation="ordinary-id",
        conversation_mode="normal",
    )

    mode = execution.provenance.conversation_mode
    assert denied["requested_conversation_mode"] == "TEMPORARY"
    assert denied["observed_conversation_mode"] == "UNKNOWN"
    assert mode is not None
    assert mode.requested_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_mode_proven is True
    assert (
        mode.observed_mode_evidence_source
        is ConversationModeEvidenceSource.TRANSPORT_SEMANTICS_CONTRACT
    )
    assert execution.provenance.identity.conversation_id == "ordinary-id"
    assert execution.provenance.transport_metadata == {
        "runtime_tab_id": 77,
        "normal_observation": "normal-observed",
    }


def test_repeated_temporary_denials_do_not_make_normal_mode_sticky_or_unavailable() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    for _ in range(3):
        with pytest.raises(ProductConversationModeUnavailableError):
            runtime.send_text("blocked-temp", conversation_mode="temporary")

    first = runtime.send_text_observed("normal-1")

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text_observed("blocked-again", conversation_mode="temporary")

    second = runtime.send_text_observed("normal-2")

    assert [call[1] for call in transport.write_calls] == ["normal-1", "normal-2"]
    for execution in (first, second):
        mode = execution.provenance.conversation_mode
        assert mode is not None
        assert mode.requested_conversation_mode is ConversationMode.NORMAL
        assert mode.observed_conversation_mode is ConversationMode.NORMAL


def test_governance_declares_request_scoped_temp_to_normal_isolation() -> None:
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport())
    governance = runtime.governance()

    assert governance["conversation_mode_state_scope"] == "REQUEST"
    assert governance["conversation_mode_state_persisted"] is False
    assert governance["temporary_mode_denial_mutates_runtime_mode_state"] is False
    assert governance["normal_mode_requires_fresh_request_resolution"] is True
    assert governance["normal_mode_inherits_temporary_identity"] is False
    assert governance["normal_mode_inherits_temporary_lifecycle"] is False
    assert governance["normal_mode_inherits_temporary_provenance"] is False
