from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import (
    APPROVALS,
    CANONICAL_READBACK,
    CONTINUATION,
    CONVERSATION_ATTACH,
    CONVERSATION_READ,
    CONVERSATION_STATUS,
    FILES,
    IMAGES,
    MULTIMODAL_CONTINUATION,
    NEW_CHAT,
    PRODUCT_CAPABILITY_NAMES,
    PRODUCT_MEMORY_PERSONALIZATION,
    STREAMING,
    TEXT_TURNS,
    WEB_SEARCH,
    CapabilityOwner,
    CapabilityState,
)


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Provider:
    def status(self):
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=77,
        )

    def send_text(self, *args, **kwargs):
        raise AssertionError("capability tests must not send")


def test_browser_owned_capability_matrix_is_complete_and_evidence_conservative() -> None:
    transport = BrowserOwnedProductTransport(_Client(), provider=_Provider())

    capabilities = transport.capabilities()

    assert tuple(entry.name for entry in capabilities.entries) == PRODUCT_CAPABILITY_NAMES
    assert capabilities.state(TEXT_TURNS) is CapabilityState.AVAILABLE
    assert capabilities.state(NEW_CHAT) is CapabilityState.AVAILABLE
    assert capabilities.state(CONTINUATION) is CapabilityState.AVAILABLE
    assert capabilities.state(CANONICAL_READBACK) is CapabilityState.AVAILABLE
    assert capabilities.state(CONVERSATION_ATTACH) is CapabilityState.AVAILABLE
    assert capabilities.state(CONVERSATION_READ) is CapabilityState.AVAILABLE
    assert capabilities.state(CONVERSATION_STATUS) is CapabilityState.AVAILABLE
    assert capabilities.state(STREAMING) is CapabilityState.AVAILABLE

    assert capabilities.state(IMAGES) is CapabilityState.UNIMPLEMENTED
    assert capabilities.state(APPROVALS) is CapabilityState.UNIMPLEMENTED
    assert capabilities.state(MULTIMODAL_CONTINUATION) is CapabilityState.UNIMPLEMENTED

    assert capabilities.state(FILES) is CapabilityState.UNKNOWN
    assert capabilities.state(WEB_SEARCH) is CapabilityState.UNKNOWN
    assert capabilities.state(PRODUCT_MEMORY_PERSONALIZATION) is CapabilityState.UNKNOWN

    assert capabilities.get(CANONICAL_READBACK).owner is CapabilityOwner.CANONICAL
    assert capabilities.get(PRODUCT_MEMORY_PERSONALIZATION).owner is CapabilityOwner.PRODUCT
    assert capabilities.get(TEXT_TURNS).owner is CapabilityOwner.TRANSPORT
    assert capabilities.get(STREAMING).owner is CapabilityOwner.TRANSPORT
    assert capabilities.get(STREAMING).evidence is not None
    assert "PR8.9.3 production live gate" in capabilities.get(STREAMING).evidence


def test_browser_owned_capability_governance_declares_ordinary_product_semantics() -> None:
    transport = BrowserOwnedProductTransport(_Client(), provider=_Provider())

    governance = transport.governance()

    assert governance["product_semantics"] == "ordinary-chatgpt"
    assert governance["canonical_readback_required"] is True
    assert governance["automatic_write_retry"] is False
    assert governance["streaming_supported"] is True
    assert governance["streaming_event_surface"] == "on_event"
    assert governance["streaming_canonical_finality_authoritative"] is True
    assert governance["streaming_legacy_on_token_semantics"] == "FINAL_ONLY"
