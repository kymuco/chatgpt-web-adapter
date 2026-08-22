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
            "product_semantics": "ordinary-chatgpt",
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "ambiguous_write_requires_reconciliation": True,
            "incremental_observation_is_canonical_finality": False,
        }


def _capabilities(transport: str = "browser-owned") -> ProductCapabilities:
    return ProductCapabilities.from_entries(
        transport=transport,
        entries=(),
    )


def _conforming_governance(
    *,
    transport: str = "browser-owned",
) -> dict[str, object]:
    return {
        "transport": transport,
        "product_semantics": "ordinary-chatgpt",
        "canonical_interface": "CanonicalConversationClient",
        "write_transport_interface": "ProductWriteTransport",
        "automatic_write_retry": False,
        "fallback_transport": None,
        "legacy_direct_write_fallback": False,
        "ambiguous_write_requires_reconciliation": True,
        "incremental_observation_is_canonical_finality": False,
        "runtime_depends_on_concrete_browser_transport": False,
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


def test_contract_metadata_is_derived_not_caller_self_declared() -> None:
    with pytest.raises(TypeError, match="transport_support_tier"):
        ProductCapabilities(
            transport="browser-owned",
            product_semantics="ordinary-chatgpt",
            entries=(),
            transport_support_tier="EXPERIMENTAL",
        )

    # Health stays on the released 0.2 constructor/schema rather than becoming
    # another authority source for contract/support metadata.
    with pytest.raises(TypeError, match="runtime_contract_schema"):
        ProductRuntimeHealth(
            transport="browser-owned",
            ready=True,
            reason="READY",
            conversation_id=None,
            canonical_status=None,
            canonical_read_checked=False,
            read_plane="CANONICAL",
            session_plane="CANONICAL_SESSION",
            write_plane="BROWSER_OWNED",
            runtime_contract_schema=999,
        )


def test_runtime_health_serialization_remains_frozen_to_0_2_shape() -> None:
    payload = _Transport().health("conversation-1").to_dict()

    assert payload["transport"] == "browser-owned"
    assert "runtime_contract_schema" not in payload
    assert "transport_support_tier" not in payload


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


def test_contract_fails_closed_if_incremental_observation_claims_finality() -> None:
    governance = _conforming_governance()
    governance["incremental_observation_is_canonical_finality"] = True

    with pytest.raises(
        RuntimeError,
        match="incremental_observation_is_canonical_finality=False",
    ):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


def test_contract_fails_closed_if_incremental_finality_evidence_is_missing() -> None:
    governance = _conforming_governance()
    governance.pop("incremental_observation_is_canonical_finality")

    with pytest.raises(
        RuntimeError,
        match="incremental_observation_is_canonical_finality=False",
    ):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


def test_contract_fails_closed_if_transport_governance_violates_no_retry() -> None:
    governance = _conforming_governance()
    governance["automatic_write_retry"] = True

    with pytest.raises(RuntimeError, match="automatic_write_retry=False"):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


def test_contract_fails_closed_if_hidden_fallback_is_present() -> None:
    governance = _conforming_governance()
    governance["fallback_transport"] = "legacy"

    with pytest.raises(RuntimeError, match="fallback_transport=None"):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


def test_contract_fails_closed_if_fallback_declaration_is_missing() -> None:
    governance = _conforming_governance()
    governance.pop("fallback_transport")

    with pytest.raises(RuntimeError, match="explicit fallback_transport=None"):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("canonical_interface", "ConcreteCanonicalClient"),
        ("write_transport_interface", "ConcreteBrowserWriter"),
    ),
)
def test_contract_fails_closed_if_interface_boundary_drifts(
    field: str,
    value: str,
) -> None:
    governance = _conforming_governance()
    governance[field] = value

    with pytest.raises(RuntimeError, match=field):
        build_product_runtime_contract(
            transport="browser-owned",
            capabilities=_capabilities(),
            governance=governance,
        )


def test_runtime_inspector_requires_every_frozen_operation() -> None:
    runtime = SimpleNamespace(
        transport="browser-owned",
        capabilities=lambda: _capabilities(),
        governance=lambda: _conforming_governance(),
    )

    with pytest.raises(TypeError, match="operation surface"):
        adapter.product_runtime_contract(runtime)
