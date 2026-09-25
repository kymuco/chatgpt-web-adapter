from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.product_capabilities import (
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_transport import ProductRuntimeHealth


class _Canonical:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Transport:
    def __init__(self, *, transport_id: str, product_semantics: str) -> None:
        self.transport_id = transport_id
        self.product_semantics = product_semantics

    def health(self, conversation=None):
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=True,
            reason="READY",
            conversation_id=conversation,
            canonical_status="completed" if conversation else None,
            canonical_read_checked=conversation is not None,
            read_plane="PROVIDER_CANONICAL",
            session_plane="PROVIDER_SESSION",
            write_plane="PROVIDER_WRITE",
        )

    def capabilities(self):
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            product_semantics=self.product_semantics,
            entries=(
                ProductCapability(
                    name="text_turns",
                    state=CapabilityState.AVAILABLE,
                    owner=CapabilityOwner.TRANSPORT,
                    evidence="provider-boundary fixture",
                ),
            ),
        )

    def send_text(self, text, **kwargs):
        return SimpleNamespace(text=text)

    def send_text_observed(self, text, **kwargs):
        raise AssertionError("provider boundary inspection must not execute a write")

    def governance(self):
        return {
            "product_semantics": self.product_semantics,
            "automatic_write_retry": False,
            "fallback_transport": None,
            "ambiguous_write_requires_reconciliation": True,
            "incremental_observation_is_canonical_finality": False,
        }


class _SyntheticProviderRuntime:
    provider_id = "deepseek"
    transport = "deepseek-web"

    def __init__(self) -> None:
        self.write_transport = _Transport(
            transport_id=self.transport,
            product_semantics="ordinary-deepseek",
        )

    def health(self, conversation=None):
        return self.write_transport.health(conversation)

    def capabilities(self):
        return self.write_transport.capabilities()

    def governance(self):
        raw = dict(self.write_transport.governance())
        raw.update(
            {
                "provider_id": self.provider_id,
                "transport": self.transport,
                "canonical_interface": "CanonicalConversationClient",
                "write_transport_interface": "ProductWriteTransport",
                "capability_model": "ProductCapabilities",
                "provenance_model": "ProductExecutionProvenance",
            }
        )
        return raw


def test_chatgpt_runtime_declares_provider_identity() -> None:
    transport = _Transport(
        transport_id="browser-owned",
        product_semantics=adapter.ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    )
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=transport,
    )

    boundary = adapter.product_provider_boundary(runtime)

    assert runtime.provider_id == adapter.CHATGPT_PRODUCT_PROVIDER_ID == "chatgpt"
    assert boundary.schema == adapter.PRODUCT_PROVIDER_BOUNDARY_SCHEMA == 1
    assert boundary.provider_id == "chatgpt"
    assert boundary.product_semantics == "ordinary-chatgpt"
    assert boundary.transport == "browser-owned"


def test_provider_boundary_accepts_non_chatgpt_semantics_without_special_case() -> None:
    boundary = adapter.product_provider_boundary(_SyntheticProviderRuntime())

    assert boundary.provider_id == "deepseek"
    assert boundary.product_semantics == "ordinary-deepseek"
    assert boundary.transport == "deepseek-web"
    assert boundary.canonical_interface == "CanonicalConversationClient"
    assert boundary.write_transport_interface == "ProductWriteTransport"
    assert boundary.automatic_write_retry is False
    assert boundary.fallback_transport is None
    assert boundary.ambiguous_write_requires_reconciliation is True
    assert boundary.incremental_observation_is_canonical_finality is False


def test_provider_boundary_rejects_runtime_and_capability_semantics_mismatch() -> None:
    runtime = _SyntheticProviderRuntime()
    original = runtime.governance

    def governance():
        payload = dict(original())
        payload["product_semantics"] = "ordinary-other"
        return payload

    runtime.governance = governance

    with pytest.raises(RuntimeError, match="product semantics mismatch"):
        adapter.product_provider_boundary(runtime)


def test_provider_boundary_rejects_raw_transport_fallback() -> None:
    runtime = _SyntheticProviderRuntime()
    original = runtime.write_transport.governance

    def governance():
        payload = dict(original())
        payload["fallback_transport"] = "other"
        return payload

    runtime.write_transport.governance = governance

    with pytest.raises(RuntimeError, match="raw fallback_transport=None"):
        adapter.product_provider_boundary(runtime)


def test_provider_boundary_source_has_no_provider_wire_assumptions() -> None:
    from chatgpt_web_adapter import product_provider

    source = __import__("inspect").getsource(product_provider)

    assert "ORDINARY_CHATGPT_PRODUCT_SEMANTICS" not in source
    assert "BROWSER_OWNED_PRODUCT_TRANSPORT" not in source
    assert "browser-owned" not in source
    assert "ordinary-deepseek" not in source
    assert "deepseek-web" not in source
