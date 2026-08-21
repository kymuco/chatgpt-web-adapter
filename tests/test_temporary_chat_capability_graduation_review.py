from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_owned_product_transport import (
    _BROWSER_OWNED_CAPABILITIES,
)
from chatgpt_web_adapter.product_capabilities import (
    TEMPORARY_CHAT,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_runtime import (
    ChatGPTProductRuntime,
    ProductConversationModeUnavailableError,
)
from chatgpt_web_adapter.product_transport import BROWSER_OWNED_PRODUCT_TRANSPORT


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Transport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self, temporary_state: CapabilityState) -> None:
        self.temporary_state = temporary_state
        self.write_calls: list[tuple[str, str, dict]] = []

    def health(self, conversation=None):
        raise AssertionError("T13 TEMP gate must fail before ordinary transport health")

    def capabilities(self) -> ProductCapabilities:
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(
                ProductCapability(
                    name=TEMPORARY_CHAT,
                    state=self.temporary_state,
                    owner=CapabilityOwner.TRANSPORT,
                    evidence="test capability state",
                ),
            ),
        )

    def send_text(self, text, **kwargs):
        self.write_calls.append(("send_text", text, kwargs))
        raise AssertionError("blocked Temporary request reached transport write")

    def send_text_observed(self, text, **kwargs):
        self.write_calls.append(("send_text_observed", text, kwargs))
        raise AssertionError("blocked Temporary request reached observed transport write")

    def governance(self):
        return {"transport": self.transport_id}


def test_pr813_keeps_browser_owned_temporary_chat_unknown_until_closure_commit() -> None:
    capability = _BROWSER_OWNED_CAPABILITIES.get(TEMPORARY_CHAT)

    assert capability is not None
    assert capability.state is CapabilityState.UNKNOWN
    assert capability.owner is CapabilityOwner.TRANSPORT
    assert capability.evidence is not None
    assert "PR8.13 production route implemented" in capability.evidence
    assert "live graduation pending" in capability.evidence


def test_pr813_validation_phase_does_not_claim_temporary_chat_available() -> None:
    assert _BROWSER_OWNED_CAPABILITIES.state(TEMPORARY_CHAT) is not CapabilityState.AVAILABLE


def test_unimplemented_classification_does_not_relax_t8_fail_closed_gate() -> None:
    transport = _Transport(CapabilityState.UNIMPLEMENTED)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError) as caught:
        runtime.send_text("must remain blocked", conversation_mode="temporary")

    assert transport.write_calls == []
    payload = caught.value.to_dict()
    assert payload["conversation_mode"]["requested_conversation_mode"] == "TEMPORARY"
    assert payload["conversation_mode"]["observed_conversation_mode"] == "UNKNOWN"
    assert payload["temporary_lifecycle"]["temporary_lifecycle_state"] == "NOT_ESTABLISHED"
    assert payload["temporary_lifecycle"]["live_write_authority_proven"] is False


def test_even_premature_available_classification_cannot_enable_temporary_dispatch() -> None:
    transport = _Transport(CapabilityState.AVAILABLE)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text_observed(
            "capability state alone is not authority",
            conversation_mode="temporary",
        )

    assert transport.write_calls == []
