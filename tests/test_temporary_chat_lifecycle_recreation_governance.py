from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_provenance import (
    ConversationMode,
    TemporaryLifecycleEvidenceSource,
    TemporaryLifecycleState,
    ProductTemporaryLifecycleProvenance,
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


class _RecreatableTransport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self, runtime_tab_id: int | None = None) -> None:
        self.runtime_tab_id = runtime_tab_id
        self.write_calls: list[tuple[str, str, dict]] = []
        self.health_calls: list[tuple[object, int | None]] = []
        self.capability_calls = 0

    def health(self, conversation=None):
        self.health_calls.append((conversation, self.runtime_tab_id))
        return SimpleNamespace(
            transport=self.transport_id,
            ready=True,
            reason="READY_FOR_BROWSER_OWNED_WRITE",
            runtime_tab_id=self.runtime_tab_id,
            runtime_tab_preexisting=self.runtime_tab_id is not None,
        )

    def capabilities(self):
        self.capability_calls += 1
        raise AssertionError("T12 TEMP gate must not use capability state as lifecycle proof")

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


def _assert_blocked_without_lifecycle(runtime: ChatGPTProductRuntime, text: str) -> None:
    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text_observed(text, conversation_mode="temporary")

    mode = caught.value.conversation_mode_provenance
    lifecycle = caught.value.temporary_lifecycle_provenance
    assert mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert mode.observed_conversation_mode is ConversationMode.UNKNOWN
    assert lifecycle.temporary_lifecycle_state is TemporaryLifecycleState.NOT_ESTABLISHED
    assert (
        lifecycle.lifecycle_evidence_source
        is TemporaryLifecycleEvidenceSource.RUNTIME_GOVERNANCE_CONTRACT
    )
    assert lifecycle.lifecycle_state_proven is True
    assert lifecycle.live_write_authority_proven is False


def test_cold_runtime_does_not_imply_temporary_lifecycle() -> None:
    transport = _RecreatableTransport(runtime_tab_id=None)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    health = runtime.health()
    assert health.runtime_tab_id is None
    assert health.runtime_tab_preexisting is False

    _assert_blocked_without_lifecycle(runtime, "temp-on-cold-runtime")
    assert transport.write_calls == []
    assert transport.capability_calls == 0


def test_warm_ordinary_runtime_tab_does_not_imply_temporary_lifecycle() -> None:
    transport = _RecreatableTransport(runtime_tab_id=77)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    health = runtime.health()
    assert health.runtime_tab_id == 77
    assert health.runtime_tab_preexisting is True

    _assert_blocked_without_lifecycle(runtime, "temp-on-warm-runtime")
    assert transport.write_calls == []


def test_runtime_reassembly_over_same_browser_authority_does_not_restore_temp() -> None:
    transport = _RecreatableTransport(runtime_tab_id=77)
    first = ChatGPTProductRuntime(_Client(), write_transport=transport)
    second = ChatGPTProductRuntime(_Client(), write_transport=transport)

    normal = first.send_text_observed("ordinary-first", conversation_mode="normal")
    assert normal.provenance.identity.conversation_id == "ordinary-new-chat"
    assert normal.provenance.transport_metadata["runtime_tab_id"] == 77

    _assert_blocked_without_lifecycle(second, "temp-after-runtime-reassembly")
    assert [call[1] for call in transport.write_calls] == ["ordinary-first"]


def test_runtime_tab_loss_and_recreation_never_restores_temp_lifecycle() -> None:
    transport = _RecreatableTransport(runtime_tab_id=77)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    assert runtime.health().runtime_tab_id == 77
    _assert_blocked_without_lifecycle(runtime, "temp-before-tab-loss")

    transport.runtime_tab_id = None
    assert runtime.health().runtime_tab_id is None
    _assert_blocked_without_lifecycle(runtime, "temp-while-tab-missing")

    transport.runtime_tab_id = 88
    assert runtime.health().runtime_tab_id == 88
    _assert_blocked_without_lifecycle(runtime, "temp-after-tab-recreation")

    assert transport.write_calls == []


def test_blocked_temp_error_serializes_mode_and_lifecycle_separately() -> None:
    runtime = ChatGPTProductRuntime(
        _Client(),
        write_transport=_RecreatableTransport(runtime_tab_id=99),
    )

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text("blocked", conversation_mode="temporary")

    payload = caught.value.to_dict()
    assert payload["conversation_mode"]["requested_conversation_mode"] == "TEMPORARY"
    assert payload["conversation_mode"]["observed_conversation_mode"] == "UNKNOWN"
    assert payload["temporary_lifecycle"] == {
        "temporary_lifecycle_state": "NOT_ESTABLISHED",
        "lifecycle_evidence_source": "RUNTIME_GOVERNANCE_CONTRACT",
        "lifecycle_state_proven": True,
        "live_write_authority_proven": False,
        "proof_detail": "request blocked before Temporary lifecycle establishment",
    }


def test_lifecycle_provenance_rejects_unproven_live_authority() -> None:
    with pytest.raises(ValueError, match="unproven temporary lifecycle state must be UNKNOWN"):
        ProductTemporaryLifecycleProvenance(
            temporary_lifecycle_state="LIVE",
            lifecycle_evidence_source="NONE",
            lifecycle_state_proven=False,
            live_write_authority_proven=False,
        )

    with pytest.raises(ValueError, match="live Temporary write authority requires"):
        ProductTemporaryLifecycleProvenance(
            temporary_lifecycle_state="ENDED",
            lifecycle_evidence_source="PRODUCT_LIFECYCLE_OBSERVATION",
            lifecycle_state_proven=True,
            live_write_authority_proven=True,
        )


def test_governance_declares_cold_warm_and_recreation_boundaries() -> None:
    runtime = ChatGPTProductRuntime(
        _Client(),
        write_transport=_RecreatableTransport(runtime_tab_id=77),
    )
    governance = runtime.governance()

    assert governance["temporary_lifecycle_provenance_model"] == "ProductTemporaryLifecycleProvenance"
    assert governance["temporary_lifecycle_authority_scope"] == "LIVE_PRODUCT_LIFECYCLE"
    assert governance["temporary_lifecycle_state_persisted_by_product_runtime"] is False
    assert governance["cold_runtime_implies_temporary_lifecycle"] is False
    assert governance["warm_runtime_implies_temporary_lifecycle"] is False
    assert governance["runtime_reassembly_preserves_temporary_lifecycle"] is False
    assert governance["runtime_tab_presence_implies_temporary_lifecycle"] is False
    assert governance["runtime_tab_recreation_restores_temporary_lifecycle"] is False
    assert governance["browser_authority_recreation_restores_temporary_lifecycle"] is False
    assert governance["temporary_lifecycle_requires_fresh_proof_after_runtime_recreation"] is True
    assert governance["temporary_lifecycle_requires_fresh_proof_after_tab_recreation"] is True
    assert governance["post_close_route_recovery_restores_temporary_lifecycle"] is False
