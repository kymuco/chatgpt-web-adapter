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


def _response(conversation_id: str):
    return SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id=conversation_id,
            message_id=f"assistant-{conversation_id}",
            finish_reason=None,
        ),
        request=SimpleNamespace(observed_model="gpt-test"),
    )


class _Transport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self) -> None:
        self.write_calls: list[tuple[str, str, dict]] = []
        self.capability_calls = 0
        self.health_calls = 0
        self.runtime_tab_id = 77

    def health(self, conversation=None):
        self.health_calls += 1
        raise AssertionError("TEMP mode isolation must not consult ordinary health as mode proof")

    def capabilities(self):
        self.capability_calls += 1
        raise AssertionError("TEMP mode isolation must not consult capability state as mode proof")

    def send_text(self, text, **kwargs):
        self.write_calls.append(("send_text", text, kwargs))
        cid = str(kwargs.get("conversation") or "ordinary-new-chat")
        return _response(cid)

    def send_text_observed(self, text, **kwargs):
        self.write_calls.append(("send_text_observed", text, kwargs))
        cid = str(kwargs.get("conversation") or "ordinary-new-chat")
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=_response(cid),
            observation={
                "runtime_tab_id": self.runtime_tab_id,
                "ordinary_conversation_id": cid,
            },
        )

    def governance(self):
        return {
            "transport": self.transport_id,
            "product_semantics": "ordinary-chatgpt",
            "canonical_readback_required": True,
        }


def test_normal_success_then_temporary_is_denied_without_second_write() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    runtime.send_text("normal-first", conversation_mode="normal")

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text("temp-after-normal", conversation_mode="temporary")

    assert [call[1] for call in transport.write_calls] == ["normal-first"]
    mode = caught.value.conversation_mode_provenance
    assert mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert mode.observed_conversation_mode is ConversationMode.UNKNOWN
    assert mode.observed_mode_evidence_source is ConversationModeEvidenceSource.NONE
    assert mode.observed_mode_proven is False
    assert transport.capability_calls == 0
    assert transport.health_calls == 0


def test_ordinary_conversation_identity_is_not_reused_as_temporary_authority() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    runtime.send_text(
        "ordinary-continuation",
        conversation="ordinary-conversation-id",
        conversation_mode="normal",
    )

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text(
            "must-not-reuse-ordinary-id",
            conversation="ordinary-conversation-id",
            conversation_mode="temporary",
        )

    assert transport.write_calls == [
        (
            "send_text",
            "ordinary-continuation",
            {
                "conversation": "ordinary-conversation-id",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]


def test_normal_observed_provenance_does_not_become_temporary_mode_proof() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    normal = runtime.send_text_observed(
        "ordinary-observed",
        conversation="ordinary-id",
        conversation_mode="normal",
    )
    normal_mode = normal.provenance.conversation_mode
    assert normal_mode is not None
    assert normal_mode.requested_conversation_mode is ConversationMode.NORMAL
    assert normal_mode.observed_conversation_mode is ConversationMode.NORMAL
    assert normal_mode.observed_mode_proven is True

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text_observed("temp-after-observed-normal", conversation_mode="temporary")

    denied_mode = caught.value.conversation_mode_provenance
    assert denied_mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert denied_mode.observed_conversation_mode is ConversationMode.UNKNOWN
    assert denied_mode.observed_mode_proven is False
    assert [call[1] for call in transport.write_calls] == ["ordinary-observed"]


def test_preexisting_ordinary_runtime_tab_is_not_temporary_mode_proof() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    normal = runtime.send_text_observed("ordinary-tab-owner", conversation_mode="normal")
    assert normal.provenance.transport_metadata["runtime_tab_id"] == 77

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text_observed("temp-cannot-borrow-tab", conversation_mode="temporary")

    assert caught.value.conversation_mode_provenance.observed_conversation_mode is ConversationMode.UNKNOWN
    assert [call[1] for call in transport.write_calls] == ["ordinary-tab-owner"]


def test_repeated_normal_to_temporary_sequences_never_make_temp_dispatchable() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    for index in range(3):
        runtime.send_text(f"normal-{index}", conversation_mode="normal")
        with pytest.raises(ProductConversationModeUnavailableError):
            runtime.send_text(f"temp-{index}", conversation_mode="temporary")

    assert [call[1] for call in transport.write_calls] == [
        "normal-0",
        "normal-1",
        "normal-2",
    ]


def test_governance_declares_normal_to_temporary_isolation() -> None:
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport())
    governance = runtime.governance()

    assert governance["conversation_mode_state_scope"] == "REQUEST"
    assert governance["temporary_mode_requires_fresh_request_resolution"] is True
    assert governance["normal_mode_success_mutates_temporary_authority"] is False
    assert governance["temporary_mode_inherits_normal_identity"] is False
    assert governance["temporary_mode_inherits_normal_lifecycle"] is False
    assert governance["temporary_mode_inherits_normal_provenance"] is False
    assert governance["ordinary_runtime_tab_is_temporary_mode_proof"] is False
    assert governance["ordinary_conversation_identity_is_temporary_mode_proof"] is False
