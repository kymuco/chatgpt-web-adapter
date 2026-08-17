from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_owned_product_transport as browser_transport
import chatgpt_web_adapter.product_runtime as product_runtime
from chatgpt_web_adapter.product_capabilities import (
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_runtime import (
    ChatGPTProductRuntime,
    ProductConversationModeUnavailableError,
    assemble_product_runtime,
)
from chatgpt_web_adapter.product_transport import (
    ProductRuntimeExecution,
    ProductRuntimeHealth,
)


class _Canonical:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _PolicyTransport:
    transport_id = "browser-owned"

    def __init__(self, *, supports_policy: bool = True) -> None:
        self.supports_policy = supports_policy
        self.send_calls = []
        self.observed_calls = []
        self.response = SimpleNamespace(conversation=None, request=None)
        self.observation = SimpleNamespace(source="policy-test")

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
        if self.supports_policy:
            governance["browser_authority_product_runtime_policy_supported"] = True
        return governance


def test_direct_runtime_assembly_forwards_browser_authority_runtime_default(monkeypatch):
    captured = {}
    transport = _PolicyTransport()

    def fake_assemble(client, **kwargs):
        captured["client"] = client
        captured.update(kwargs)
        return transport

    monkeypatch.setattr(product_runtime, "_assemble_default_write_transport", fake_assemble)
    canonical = _Canonical()

    runtime = ChatGPTProductRuntime(
        canonical,
        browser_authority_policy="IDLE_TTL",
        browser_authority_ttl_ms=5000,
    )

    assert runtime.write_transport is transport
    assert captured == {
        "client": canonical,
        "transport": "browser-owned",
        "provider": None,
        "browser_authority_policy": "IDLE_TTL",
        "browser_authority_ttl_ms": 5000,
    }


def test_default_runtime_assembly_keeps_legacy_call_shape_without_policy(monkeypatch):
    captured = {}
    transport = _PolicyTransport()

    def fake_assemble(client, **kwargs):
        captured["client"] = client
        captured.update(kwargs)
        return transport

    monkeypatch.setattr(product_runtime, "_assemble_default_write_transport", fake_assemble)
    canonical = _Canonical()

    ChatGPTProductRuntime(canonical)

    assert captured == {
        "client": canonical,
        "transport": "browser-owned",
        "provider": None,
    }


def test_assemble_product_runtime_forwards_runtime_default_to_owned_assembly(monkeypatch):
    captured = {}
    transport = _PolicyTransport()

    def fake_assemble(client, **kwargs):
        captured["client"] = client
        captured.update(kwargs)
        return transport

    monkeypatch.setattr(product_runtime, "_assemble_default_write_transport", fake_assemble)
    canonical = _Canonical()

    runtime = assemble_product_runtime(
        client=canonical,
        browser_authority_policy="TURN_SCOPED",
        browser_authority_ttl_ms=0,
    )

    assert runtime.write_transport is transport
    assert captured == {
        "client": canonical,
        "transport": "browser-owned",
        "provider": None,
        "browser_authority_policy": "TURN_SCOPED",
        "browser_authority_ttl_ms": 0,
    }


def test_injected_transport_rejects_browser_authority_runtime_defaults() -> None:
    transport = _PolicyTransport()

    with pytest.raises(
        ValueError,
        match="runtime defaults require runtime-owned transport assembly",
    ):
        ChatGPTProductRuntime(
            _Canonical(),
            write_transport=transport,
            browser_authority_policy="IDLE_TTL",
            browser_authority_ttl_ms=5000,
        )

    assert transport.send_calls == []


def test_assemble_with_injected_transport_rejects_browser_authority_runtime_defaults() -> None:
    transport = _PolicyTransport()

    with pytest.raises(
        ValueError,
        match="runtime defaults require runtime-owned transport assembly",
    ):
        assemble_product_runtime(
            client=_Canonical(),
            write_transport=transport,
            browser_authority_policy="TURN_SCOPED",
            browser_authority_ttl_ms=0,
        )

    assert transport.send_calls == []


def test_per_turn_send_text_forwards_turn_scoped_policy_when_transport_opts_in() -> None:
    transport = _PolicyTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send_text(
        "hello",
        conversation="c1",
        browser_authority_policy="TURN_SCOPED",
        browser_authority_ttl_ms=0,
    )

    assert transport.send_calls == [
        (
            "hello",
            {
                "conversation": "c1",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
                "browser_authority_policy": "TURN_SCOPED",
                "browser_authority_ttl_ms": 0,
            },
        )
    ]


def test_send_alias_forwards_idle_ttl_policy() -> None:
    transport = _PolicyTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send(
        "hello",
        browser_authority_policy="IDLE_TTL",
        browser_authority_ttl_ms=5000,
    )

    kwargs = transport.send_calls[0][1]
    assert kwargs["browser_authority_policy"] == "IDLE_TTL"
    assert kwargs["browser_authority_ttl_ms"] == 5000


def test_observed_send_forwards_browser_authority_override() -> None:
    transport = _PolicyTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    execution = runtime.send_text_observed(
        "hello",
        browser_authority_policy="TURN_SCOPED",
        browser_authority_ttl_ms=0,
    )

    kwargs = transport.observed_calls[0][1]
    assert kwargs["browser_authority_policy"] == "TURN_SCOPED"
    assert kwargs["browser_authority_ttl_ms"] == 0
    assert execution.provenance is not None
    assert execution.provenance.completion.canonical_completion_proven is True


def test_unsupported_transport_rejects_per_turn_policy_before_dispatch() -> None:
    transport = _PolicyTransport(supports_policy=False)
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    with pytest.raises(ValueError, match="overrides are unavailable"):
        runtime.send_text(
            "hello",
            browser_authority_policy="TURN_SCOPED",
            browser_authority_ttl_ms=0,
        )

    assert transport.send_calls == []


def test_no_override_does_not_widen_generic_transport_call_shape() -> None:
    transport = _PolicyTransport(supports_policy=False)
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    runtime.send_text("hello", conversation="c1")

    assert transport.send_calls == [
        (
            "hello",
            {
                "conversation": "c1",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]


def test_temporary_mode_denial_precedes_browser_authority_override_dispatch() -> None:
    transport = _PolicyTransport()
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=transport)

    with pytest.raises(ProductConversationModeUnavailableError):
        runtime.send_text(
            "hello",
            conversation_mode="temporary",
            browser_authority_policy="TURN_SCOPED",
            browser_authority_ttl_ms=0,
        )

    assert transport.send_calls == []


def test_product_runtime_governance_keeps_policy_resource_scoped_and_browser_opaque() -> None:
    runtime = ChatGPTProductRuntime(_Canonical(), write_transport=_PolicyTransport())

    governance = runtime.governance()

    assert governance["browser_authority_policy_high_level_surface"] is True
    assert governance["browser_authority_selected_transport_policy_support"] is True
    assert governance["browser_authority_policy_override_requires_transport_support"] is True
    assert governance["browser_authority_policy_contract_scope"] == "RESOURCE_LIFECYCLE_ONLY"
    assert governance["browser_authority_policy_changes_conversation_identity"] is False
    assert governance["browser_authority_policy_changes_conversation_mode"] is False
    assert governance["browser_authority_policy_changes_canonical_finality"] is False
    assert governance["browser_authority_policy_recreates_temporary_lifecycle"] is False
    assert governance["browser_authority_policy_exposes_browser_mechanics"] is False
    assert governance["browser_authority_runtime_tab_identity_required_by_caller"] is False
    assert governance["browser_authority_native_messaging_details_required_by_caller"] is False


def test_browser_owned_transport_passes_runtime_defaults_to_lower_runtime(monkeypatch) -> None:
    captured = {}

    class FakeLowerRuntime:
        def __init__(self, client, **kwargs):
            captured["client"] = client
            captured.update(kwargs)

        def governance(self):
            return {
                "browser_authority_default_policy": "PERSISTENT",
                "automatic_write_retry": False,
                "canonical_readback_required": True,
            }

    monkeypatch.setattr(
        browser_transport,
        "BrowserOwnedProductWriteRuntime",
        FakeLowerRuntime,
    )
    canonical = _Canonical()
    provider = object()

    transport = browser_transport.BrowserOwnedProductTransport(
        canonical,
        provider=provider,
        browser_authority_policy="IDLE_TTL",
        browser_authority_ttl_ms=5000,
    )

    assert captured == {
        "client": canonical,
        "provider": provider,
        "browser_authority_policy": "IDLE_TTL",
        "browser_authority_ttl_ms": 5000,
    }
    governance = transport.governance()
    assert governance["browser_authority_product_runtime_policy_supported"] is True
    assert governance["browser_authority_effective_runtime_default_policy"] == "IDLE_TTL"
    assert governance["browser_authority_effective_runtime_default_ttl_ms"] == 5000
    assert governance["browser_authority_runtime_default_policy_source"] == "RUNTIME_DEFAULT"
    assert governance["browser_authority_configured_runtime_ttl_ms"] == 5000
    assert governance["browser_authority_policy_exposes_runtime_tab_identity"] is False
    assert governance["browser_authority_policy_requires_native_messaging_details"] is False


def test_browser_owned_transport_default_remains_persistent_and_constructor_shape_stable(monkeypatch) -> None:
    captured = {}

    class FakeLowerRuntime:
        def __init__(self, client, **kwargs):
            captured["client"] = client
            captured.update(kwargs)

        def governance(self):
            return {
                "browser_authority_default_policy": "PERSISTENT",
                "automatic_write_retry": False,
                "canonical_readback_required": True,
            }

    monkeypatch.setattr(
        browser_transport,
        "BrowserOwnedProductWriteRuntime",
        FakeLowerRuntime,
    )
    canonical = _Canonical()
    provider = object()

    transport = browser_transport.BrowserOwnedProductTransport(
        canonical,
        provider=provider,
    )

    assert captured == {
        "client": canonical,
        "provider": provider,
    }
    governance = transport.governance()
    assert governance["browser_authority_default_policy"] == "PERSISTENT"
    assert governance["browser_authority_effective_runtime_default_policy"] == "PERSISTENT"
    assert governance["browser_authority_effective_runtime_default_ttl_ms"] is None
    assert governance["browser_authority_runtime_default_policy_source"] == "TRANSPORT_DEFAULT"
    assert governance["browser_authority_configured_runtime_ttl_ms"] is None
