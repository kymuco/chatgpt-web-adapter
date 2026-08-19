from __future__ import annotations

import inspect
from types import SimpleNamespace

from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import STREAMING, CapabilityOwner, CapabilityState
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.revision_safe_streaming_pr8_9 import (
    ASSISTANT_TEXT_DELTA,
    ASSISTANT_TEXT_REVISION,
    ASSISTANT_TEXT_SNAPSHOT,
    CANONICAL_EXTENDS_STREAM,
    CANONICAL_TEXT_FINALIZED,
    EXACT_MATCH,
    STREAM_INCOMPLETE,
    STREAM_REVISED_BY_CANONICAL,
    UNAVAILABLE,
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
        raise AssertionError("graduation tests must not send")


def test_streaming_capability_is_available_with_pr89_production_evidence() -> None:
    transport = BrowserOwnedProductTransport(_Client(), provider=_Provider())
    capability = transport.capabilities().get(STREAMING)

    assert capability is not None
    assert capability.state is CapabilityState.AVAILABLE
    assert capability.owner is CapabilityOwner.TRANSPORT
    assert capability.evidence is not None
    assert "PR8.9.3 production live gate" in capability.evidence
    assert "EXACT_MATCH" in capability.evidence


def test_streaming_governance_freezes_revision_safe_public_contract() -> None:
    transport = BrowserOwnedProductTransport(_Client(), provider=_Provider())
    governance = transport.governance()

    assert governance["streaming_supported"] is True
    assert governance["streaming_contract_version"] == 1
    assert governance["streaming_event_surface"] == "on_event"
    assert governance["streaming_event_types"] == [
        ASSISTANT_TEXT_SNAPSHOT,
        ASSISTANT_TEXT_DELTA,
        ASSISTANT_TEXT_REVISION,
        CANONICAL_TEXT_FINALIZED,
    ]
    assert governance["streaming_source"] == "CDP_NETWORK_STREAM_RESOURCE_CONTENT"
    assert governance["streaming_delivery"] == "REVISION_SAFE_EVENT_STREAM"
    assert governance["streaming_canonical_finality"] == "BROWSERLESS_CANONICAL_HTTP"
    assert governance["streaming_canonical_finality_authoritative"] is True
    assert governance["streaming_reconciliation_states"] == [
        EXACT_MATCH,
        CANONICAL_EXTENDS_STREAM,
        STREAM_REVISED_BY_CANONICAL,
        STREAM_INCOMPLETE,
        UNAVAILABLE,
    ]
    assert governance["streaming_legacy_on_token_semantics"] == "FINAL_ONLY"
    assert governance["streaming_raw_sse_exported"] is False
    assert governance["streaming_automatic_write_retry"] is False


def test_product_runtime_keeps_on_event_as_the_streaming_surface() -> None:
    for method_name in ("send_text", "send", "send_text_observed"):
        parameters = inspect.signature(getattr(ChatGPTProductRuntime, method_name)).parameters
        assert "on_event" in parameters
        assert "on_token" in parameters
