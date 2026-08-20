from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import (
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.product_transport import ProductRuntimeExecution, ProductRuntimeHealth


class _Canonical:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _ProfileTransport:
    transport_id = "browser-owned"

    def __init__(self, *, supports_profile: bool = True) -> None:
        self.supports_profile = supports_profile
        self.send_calls = []
        self.observed_calls = []
        self.response = SimpleNamespace(conversation=None, request=None)
        self.observation = SimpleNamespace(source="profile-test")

    def health(self, conversation=None):
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=True,
            reason="READY",
            conversation_id=conversation,
            canonical_status="completed" if conversation else None,
            canonical_read_checked=conversation is not None,
            read_plane="CANONICAL",
            session_plane="CANONICAL",
            write_plane="FAKE",
        )

    def capabilities(self):
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(
                ProductCapability(
                    name="text_turns",
                    state=CapabilityState.AVAILABLE,
                    owner=CapabilityOwner.TRANSPORT,
                    evidence="test transport",
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
        governance = {
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "ambiguous_write_requires_reconciliation": True,
        }
        if self.supports_profile:
            governance["model_profile_product_runtime_selection_supported"] = True
        return governance


def test_product_runtime_forwards_model_profile_only_when_transport_opts_in() -> None:
    transport = _ProfileTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send_text("hello", conversation="c1", model_profile="DEEP")

    assert transport.send_calls == [
        (
            "hello",
            {
                "conversation": "c1",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
                "model_profile": "DEEP",
            },
        )
    ]


def test_send_alias_and_observed_surface_forward_model_profile() -> None:
    transport = _ProfileTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send("hello", model_profile="FAST")
    execution = runtime.send_text_observed("hello again", model_profile="BALANCED")

    assert transport.send_calls[0][1]["model_profile"] == "FAST"
    assert transport.observed_calls[0][1]["model_profile"] == "BALANCED"
    assert execution.provenance is not None


def test_no_model_profile_keeps_generic_transport_call_shape_unchanged() -> None:
    transport = _ProfileTransport(supports_profile=False)
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send_text("hello", conversation="c1")

    assert "model_profile" not in transport.send_calls[0][1]


def test_unsupported_transport_rejects_profile_before_dispatch() -> None:
    transport = _ProfileTransport(supports_profile=False)
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    with pytest.raises(ValueError, match="model profile selection is unavailable"):
        runtime.send_text("hello", model_profile="DEEP")

    assert transport.send_calls == []


def test_runtime_governance_declares_profile_surface_without_preservation_claim() -> None:
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=_ProfileTransport())

    governance = runtime.governance()

    assert governance["model_profile_high_level_surface"] is True
    assert governance["model_profile_selected_transport_support"] is True
    assert governance["model_profile_override_requires_transport_support"] is True
    assert governance["model_profile_fallback"] is None
    assert governance["silent_model_profile_fallback"] is False
    assert governance["model_profile_state_scope"] == "TURN_REQUIREMENT"
    assert governance["model_profile_preservation_scope_proven"] is False


class _ProfileProvider:
    def __init__(self) -> None:
        self.active = None
        self.entries = []

    def send_text(self, *args, **kwargs):
        raise AssertionError("profile provider double must not send directly")

    @contextmanager
    def require_profile(self, profile):
        assert self.active is None
        self.active = profile
        self.entries.append(("enter", profile))
        try:
            yield profile
        finally:
            self.entries.append(("exit", profile))
            self.active = None


class _NoProfileProvider:
    def send_text(self, *args, **kwargs):
        raise AssertionError("non-profile provider double must not send directly")


class _LowerRuntime:
    def __init__(self, provider) -> None:
        self.provider = provider
        self.calls = []

    def send_text(self, text, **kwargs):
        self.calls.append((text, self.provider.active, kwargs))
        return SimpleNamespace(text="ok")

    def send_text_observed(self, text, **kwargs):
        self.calls.append((text, self.provider.active, kwargs))
        return SimpleNamespace(
            response=SimpleNamespace(text="ok"),
            observation=SimpleNamespace(source="lower"),
        )

    def governance(self):
        return {
            "automatic_write_retry": False,
            "canonical_readback_required": True,
        }


def test_browser_transport_moves_proven_profile_context_inside_production_boundary() -> None:
    provider = _ProfileProvider()
    transport = BrowserOwnedProductTransport(_Canonical(), provider=provider)
    transport._runtime = _LowerRuntime(provider)

    transport.send_text("hello", model_profile="BALANCED")
    observed = transport.send_text_observed("again", model_profile="DEEP")

    assert provider.entries == [
        ("enter", "BALANCED"),
        ("exit", "BALANCED"),
        ("enter", "DEEP"),
        ("exit", "DEEP"),
    ]
    assert transport._runtime.calls[0][1] == "BALANCED"
    assert transport._runtime.calls[1][1] == "DEEP"
    assert observed.transport == "browser-owned"


def test_browser_transport_custom_provider_without_profile_support_fails_closed() -> None:
    provider = _NoProfileProvider()
    transport = BrowserOwnedProductTransport(_Canonical(), provider=provider)
    transport._runtime = _LowerRuntime(SimpleNamespace(active=None))

    with pytest.raises(ValueError, match="configured browser-native provider"):
        transport.send_text("hello", model_profile="FAST")

    assert transport._runtime.calls == []
