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
from chatgpt_web_adapter.product_contract import build_product_runtime_contract
from chatgpt_web_adapter.product_transport import ProductRuntimeExecution, ProductRuntimeHealth


class _Canonical:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Transport:
    transport_id = "browser-owned"

    def health(self, conversation=None):
        return ProductRuntimeHealth(
            transport=self.transport_id,
            ready=True,
            reason="READY",
            conversation_id=conversation,
            canonical_status="completed" if conversation else None,
            canonical_read_checked=conversation is not None,
            read_plane="CANONICAL",
            session_plane="CANONICAL_SESSION",
            write_plane="BROWSER_OWNED",
        )

    def capabilities(self):
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(
                ProductCapability(
                    name="text_turns",
                    state=CapabilityState.AVAILABLE,
                    owner=CapabilityOwner.TRANSPORT,
                    evidence="contract fixture",
                ),
            ),
        )

    def send_text(self, text, **kwargs):
        return SimpleNamespace(text=text)

    def send_text_observed(self, text, **kwargs):
        response = SimpleNamespace(text=text)
        return ProductRuntimeExecution(
            transport=self.transport_id,
            response=response,
            observation=SimpleNamespace(source="fixture"),
        )

    def governance(self):
        return {
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "ambiguous_write_requires_reconciliation": True,
        }


def test_browser_owned_is_frozen_production_transport() -> None:
    assert adapter.PRODUCT_RUNTIME_CONTRACT_SCHEMA == 1
    assert adapter.product_transport_support_tier("browser-owned") is (
        adapter.ProductTransportSupportTier.PRODUCTION
    )


def test_unknown_future_transport_defaults_to_experimental() -> None:
    assert adapter.product_transport_support_tier("browserless-request") is (
        adapter.ProductTransportSupportTier.EXPERIMENTAL
    )


def test_capability_state_and_transport_support_tier_are_orthogonal() -> None:
    production = ProductCapabilities.from_entries(
        transport="browser-owned",
        entries=(
            ProductCapability(
                name="text_turns",
                state=CapabilityState.AVAILABLE,
                owner=CapabilityOwner.TRANSPORT,
            ),
        ),
    ).to_dict()
    experimental = ProductCapabilities.from_entries(
        transport="browserless-request",
        entries=(
            ProductCapability(
                name="text_turns",
                state=CapabilityState.AVAILABLE,
                owner=CapabilityOwner.TRANSPORT,
            ),
        ),
    ).to_dict()

    assert production["transport_support_tier"] == "PRODUCTION"
    assert production["capabilities"]["text_turns"]["state"] == "AVAILABLE"
    assert experimental["transport_support_tier"] == "EXPERIMENTAL"
    assert experimental["capabilities"]["text_turns"]["state"] == "AVAILABLE"


def test_runtime_health_serializes_contract_schema_and_support_tier() -> None:
    payload = _Transport().health("conversation-1").to_dict()

    assert payload["runtime_contract_schema"] == 1
    assert payload["transport"] == "browser-owned"
    assert payload["transport_support_tier"] == "PRODUCTION"


def test_runtime_contract_freezes_standalone_sdk_invariants() -> None:
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=_Transport(),
    )

    contract = adapter.product_runtime_contract(runtime)
    payload = contract.to_dict()

    assert isinstance(contract, adapter.ProductRuntimeContract)
    assert payload["schema"] == 1
    assert payload["runtime"] == "ChatGPTProductRuntime"
    assert payload["product_semantics"] == "ordinary-chatgpt"
    assert payload["transport"] == "browser-owned"
    assert payload["transport_support_tier"] == "PRODUCTION"
    assert payload["interfaces"] == {
        "canonical": "CanonicalConversationClient",
        "write_transport": "ProductWriteTransport",
    }
    assert payload["capability_states"] == [
        "AVAILABLE",
        "UNSUPPORTED",
        "UNKNOWN",
        "UNIMPLEMENTED",
    ]
    assert payload["invariants"] == {
        "automatic_write_retry": False,
        "fallback_transport": None,
        "ambiguous_write_requires_reconciliation": True,
        "incremental_observation_is_canonical_finality": False,
        "browser_implementation_required_by_caller": False,
    }
    assert "send_text_observed" in payload["operations"]
    assert "governance" in payload["operations"]


def test_contract_fails_closed_if_transport_governance_violates_no_retry() -> None:
    capabilities = ProductCapabilities.from_entries(
        transport="browser-owned",
        entries=(),
    )
    governance = {
        "automatic_write_retry": True,
        "fallback_transport": None,
        "legacy_direct_write_fallback": False,
        "ambiguous_write_requires_reconciliation": True,
        "runtime_depends_on_concrete_browser_transport": False,
    }

    with pytest.raises(RuntimeError, match="automatic_write_retry=False"):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=capabilities,
            governance=governance,
        )


def test_contract_fails_closed_if_hidden_fallback_is_present() -> None:
    capabilities = ProductCapabilities.from_entries(
        transport="browser-owned",
        entries=(),
    )
    governance = {
        "automatic_write_retry": False,
        "fallback_transport": "legacy",
        "legacy_direct_write_fallback": False,
        "ambiguous_write_requires_reconciliation": True,
        "runtime_depends_on_concrete_browser_transport": False,
    }

    with pytest.raises(RuntimeError, match="fallback_transport=None"):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=capabilities,
            governance=governance,
        )
