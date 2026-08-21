from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_provenance import (
    ConversationMode,
    ConversationModeEvidenceSource,
    ProductConversationModeProvenance,
    build_product_execution_provenance,
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


def _response():
    return SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id="assistant-1",
            finish_reason=None,
        ),
        request=SimpleNamespace(observed_model="gpt-test"),
    )


class _Transport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self, *, provenance=None) -> None:
        self.provenance = provenance
        self.write_calls = []

    def health(self, conversation=None):
        raise AssertionError("health should not be consulted")

    def capabilities(self):
        raise AssertionError("capabilities should not be consulted")

    def send_text(self, text, **kwargs):
        self.write_calls.append(("send_text", text, kwargs))
        return _response()

    def send_text_observed(self, text, **kwargs):
        self.write_calls.append(("send_text_observed", text, kwargs))
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=_response(),
            observation={"runtime_tab_id": 77},
            provenance=self.provenance,
        )

    def governance(self):
        return {
            "transport": self.transport_id,
            "product_semantics": "ordinary-chatgpt",
            "canonical_readback_required": True,
        }


def test_normal_observed_execution_has_requested_and_observed_mode_provenance() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    execution = runtime.send_text_observed("hello", conversation_mode=" normal ")

    mode = execution.provenance.conversation_mode
    assert mode is not None
    assert mode.requested_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_mode_proven is True
    assert (
        mode.observed_mode_evidence_source
        is ConversationModeEvidenceSource.TRANSPORT_SEMANTICS_CONTRACT
    )
    assert execution.provenance.to_dict()["conversation_mode"] == {
        "requested_conversation_mode": "NORMAL",
        "observed_conversation_mode": "NORMAL",
        "observed_mode_evidence_source": "TRANSPORT_SEMANTICS_CONTRACT",
        "observed_mode_proven": True,
        "proof_detail": "normal request dispatched through ordinary-mode ProductWriteTransport",
    }


def test_legacy_transport_provenance_without_mode_is_upgraded_by_runtime() -> None:
    supplied = build_product_execution_provenance(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        response=_response(),
        observation={"source": "legacy-transport"},
        governance={"canonical_readback_required": True},
    )
    assert supplied.conversation_mode is None
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport(provenance=supplied))

    execution = runtime.send_text_observed("hello", conversation_mode="normal")

    mode = execution.provenance.conversation_mode
    assert mode is not None
    assert mode.requested_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_conversation_mode is ConversationMode.NORMAL
    assert mode.observed_mode_proven is True
    assert supplied.conversation_mode is None


def test_matching_transport_supplied_mode_provenance_is_preserved() -> None:
    supplied_mode = ProductConversationModeProvenance(
        requested_conversation_mode=ConversationMode.NORMAL,
        observed_conversation_mode=ConversationMode.NORMAL,
        observed_mode_evidence_source=ConversationModeEvidenceSource.PRODUCT_MODE_OBSERVATION,
        observed_mode_proven=True,
        proof_detail="explicit product observation",
    )
    supplied = build_product_execution_provenance(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        response=_response(),
        observation={"source": "transport"},
        governance={"canonical_readback_required": True},
        conversation_mode=supplied_mode,
    )
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport(provenance=supplied))

    execution = runtime.send_text_observed("hello", conversation_mode="normal")

    assert execution.provenance.conversation_mode is supplied_mode


def test_contradictory_transport_mode_provenance_is_rejected() -> None:
    contradictory_mode = ProductConversationModeProvenance(
        requested_conversation_mode=ConversationMode.TEMPORARY,
        observed_conversation_mode=ConversationMode.TEMPORARY,
        observed_mode_evidence_source=ConversationModeEvidenceSource.PRODUCT_MODE_OBSERVATION,
        observed_mode_proven=True,
    )
    supplied = build_product_execution_provenance(
        transport=BROWSER_OWNED_PRODUCT_TRANSPORT,
        response=_response(),
        observation=None,
        governance={},
        conversation_mode=contradictory_mode,
    )
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport(provenance=supplied))

    with pytest.raises(RuntimeError, match="unexpected requested mode"):
        runtime.send_text_observed("hello", conversation_mode="normal")


def test_blocked_temporary_request_exposes_unknown_observed_mode_and_zero_write() -> None:
    transport = _Transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text_observed("must not write", conversation_mode="temporary")

    mode = caught.value.conversation_mode_provenance
    assert mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert mode.observed_conversation_mode is ConversationMode.UNKNOWN
    assert mode.observed_mode_evidence_source is ConversationModeEvidenceSource.NONE
    assert mode.observed_mode_proven is False
    assert transport.write_calls == []
    assert caught.value.to_dict()["conversation_mode"]["observed_conversation_mode"] == "UNKNOWN"


def test_mode_provenance_rejects_claimed_observation_without_proof() -> None:
    with pytest.raises(ValueError, match="unproven observed conversation mode must be UNKNOWN"):
        ProductConversationModeProvenance(
            requested_conversation_mode="temporary",
            observed_conversation_mode="temporary",
            observed_mode_evidence_source="NONE",
            observed_mode_proven=False,
        )


def test_governance_declares_mode_provenance_contract() -> None:
    runtime = ChatGPTProductRuntime(_Client(), write_transport=_Transport())
    governance = runtime.governance()

    assert governance["conversation_mode_provenance_model"] == "ProductConversationModeProvenance"
    assert governance["requested_conversation_mode_is_caller_input"] is True
    assert governance["normal_observed_mode_evidence_source"] == "TRANSPORT_SEMANTICS_CONTRACT"
    assert governance["blocked_temporary_observed_mode"] == "UNKNOWN"
    assert governance["temporary_mode_observation_required_before_write"] is True
