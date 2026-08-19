from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_capabilities import (
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.product_transport import (
    CanonicalConversationClient,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    ProductWriteTransport,
    require_canonical_conversation_client,
    require_product_write_transport,
)


class _Canonical:
    def __init__(self) -> None:
        self.status_calls = []
        self.message_calls = []
        self.attach_calls = []

    def get_status(self, conversation):
        self.status_calls.append(conversation)
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        self.message_calls.append((conversation, kwargs))
        return []

    def attach_conversation(self, conversation):
        self.attach_calls.append(conversation)
        return SimpleNamespace(conversation_id=conversation)


class _FakeTransport:
    transport_id = "browser-owned"

    def __init__(self) -> None:
        self.health_calls = []
        self.send_calls = []
        self.observed_calls = []
        self.response = object()
        self.observation = SimpleNamespace(source="fake")

    def health(self, conversation=None):
        self.health_calls.append(conversation)
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=True,
            reason="FAKE_READY",
            conversation_id=conversation,
            canonical_status="completed" if conversation else None,
            canonical_read_checked=conversation is not None,
            read_plane="FAKE_CANONICAL",
            session_plane="FAKE_SESSION",
            write_plane="FAKE_WRITE",
        )

    def capabilities(self):
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(
                ProductCapability(
                    name="text_turns",
                    state=CapabilityState.AVAILABLE,
                    owner=CapabilityOwner.TRANSPORT,
                    evidence="fake transport",
                ),
            ),
        )

    def send_text(self, text, **kwargs):
        self.send_calls.append((text, kwargs))
        return self.response

    def send_text_observed(self, text, **kwargs):
        self.observed_calls.append((text, kwargs))
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=self.response,
            observation=self.observation,
        )

    def governance(self):
        return {
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "ambiguous_write_requires_reconciliation": True,
        }


def test_protocols_accept_structural_implementations() -> None:
    canonical = _Canonical()
    transport = _FakeTransport()

    assert isinstance(canonical, CanonicalConversationClient)
    assert isinstance(transport, ProductWriteTransport)
    assert require_canonical_conversation_client(canonical) is canonical
    assert require_product_write_transport(transport) is transport


def test_runtime_delegates_to_injected_transport_without_browser_contract() -> None:
    canonical = _Canonical()
    transport = _FakeTransport()
    runtime = ChatGPTProductRuntime(canonical, write_transport=transport)

    assert runtime.health("conversation-1").reason == "FAKE_READY"
    response = runtime.send_text(
        "hello",
        conversation="conversation-1",
        timeout=12.0,
        poll_interval=0.25,
    )
    execution = runtime.send_text_observed("hello again")

    assert response is transport.response
    assert execution.response is transport.response
    assert execution.observation is transport.observation
    assert execution.provenance is not None
    assert execution.provenance.transport == "browser-owned"
    assert execution.provenance.completion.canonical_completion_proven is True
    assert transport.health_calls == ["conversation-1"]
    assert transport.send_calls == [
        (
            "hello",
            {
                "conversation": "conversation-1",
                "timeout": 12.0,
                "poll_interval": 0.25,
                "on_token": None,
                "on_event": None,
            },
        )
    ]
    assert transport.observed_calls[0][0] == "hello again"


def test_runtime_capabilities_delegates_to_transport_and_preserves_identity() -> None:
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=_FakeTransport())

    capabilities = runtime.capabilities()

    assert capabilities.transport == "browser-owned"
    assert capabilities.state("text_turns") is CapabilityState.AVAILABLE


def test_runtime_canonical_methods_do_not_route_through_write_transport() -> None:
    canonical = _Canonical()
    transport = _FakeTransport()
    runtime = ChatGPTProductRuntime(canonical, write_transport=transport)

    runtime.get_status("c1")
    runtime.get_messages("c1", limit=3)
    attached = runtime.attach_conversation("c1")

    assert canonical.status_calls == ["c1"]
    assert canonical.message_calls == [("c1", {"limit": 3})]
    assert canonical.attach_calls == ["c1"]
    assert attached.conversation_id == "c1"
    assert transport.health_calls == []
    assert transport.send_calls == []


def test_injected_transport_identity_must_match_selected_production_transport() -> None:
    transport = _FakeTransport()
    transport.transport_id = "future-native"

    with pytest.raises(ValueError, match="identity does not match"):
        ChatGPTProductRuntime(_Canonical(), write_transport=transport)


def test_provider_and_injected_transport_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        ChatGPTProductRuntime(
            _Canonical(),
            provider=object(),
            write_transport=_FakeTransport(),
        )


def test_canonical_contract_fails_closed_when_required_surface_is_missing() -> None:
    class IncompleteCanonical:
        def get_status(self, conversation):
            return None

    with pytest.raises(TypeError, match="canonical client"):
        ChatGPTProductRuntime(IncompleteCanonical(), write_transport=_FakeTransport())


def test_transport_contract_fails_closed_when_capability_surface_is_missing() -> None:
    class IncompleteTransport:
        transport_id = "browser-owned"

        def health(self, conversation=None):
            return None

        def send_text(self, text, **kwargs):
            return None

        def send_text_observed(self, text, **kwargs):
            return None

        def governance(self):
            return {}

    with pytest.raises(TypeError, match="capabilities"):
        ChatGPTProductRuntime(_Canonical(), write_transport=IncompleteTransport())


def test_runtime_governance_exposes_interface_ownership_without_fallback() -> None:
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=_FakeTransport())

    governance = runtime.governance()

    assert governance["canonical_interface"] == "CanonicalConversationClient"
    assert governance["write_transport_interface"] == "ProductWriteTransport"
    assert governance["runtime_depends_on_concrete_browser_transport"] is False
    assert governance["fallback_transport"] is None
    assert governance["legacy_direct_write_fallback"] is False
    assert governance["automatic_write_retry"] is False
    assert governance["canonical_readback_required"] is True
    assert governance["capability_model"] == "ProductCapabilities"
    assert governance["provenance_model"] == "ProductExecutionProvenance"
    assert governance["finish_reason_is_optional_observed_metadata"] is True
