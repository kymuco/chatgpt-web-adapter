from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.product_capabilities import (
    ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    CapabilityState,
    ProductCapabilities,
)
from chatgpt_web_adapter.product_contract import (
    STABLE_PRODUCT_RUNTIME_OPERATIONS,
    ProductRuntimeContract,
)
from chatgpt_web_adapter.product_support import ProductTransportSupportTier
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


class _UnsafeFallbackTransport:
    transport_id = "browser-owned"

    def __init__(
        self,
        *,
        fallback_transport=None,
        legacy_direct_write_fallback=False,
    ) -> None:
        self._fallback_transport = fallback_transport
        self._legacy_direct_write_fallback = legacy_direct_write_fallback

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
            write_plane="TEST_WRITE",
        )

    def capabilities(self):
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(),
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
            "product_semantics": ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
            "automatic_write_retry": False,
            "fallback_transport": self._fallback_transport,
            "legacy_direct_write_fallback": self._legacy_direct_write_fallback,
            "ambiguous_write_requires_reconciliation": True,
            "incremental_observation_is_canonical_finality": False,
        }


class _MissingFallbackDeclarationTransport(_UnsafeFallbackTransport):
    def __init__(self, missing_key: str) -> None:
        super().__init__()
        self._missing_key = missing_key

    def governance(self):
        payload = super().governance()
        payload.pop(self._missing_key)
        return payload


def _direct_contract_kwargs(*, transport: str = "future-browserless") -> dict:
    return {
        "product_semantics": ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
        "transport": transport,
        "canonical_interface": "CanonicalConversationClient",
        "write_transport_interface": "ProductWriteTransport",
        "operations": STABLE_PRODUCT_RUNTIME_OPERATIONS,
        "capability_states": tuple(state.value for state in CapabilityState),
        "automatic_write_retry": False,
        "fallback_transport": None,
        "legacy_direct_write_fallback": False,
        "ambiguous_write_requires_reconciliation": True,
        "incremental_observation_is_canonical_finality": False,
        "browser_implementation_required_by_caller": False,
    }


def test_inspector_rejects_raw_fallback_before_runtime_governance_masks_it() -> None:
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=_UnsafeFallbackTransport(fallback_transport="legacy"),
    )

    # The high-level runtime view deliberately normalizes its own fallback policy.
    assert runtime.governance()["fallback_transport"] is None

    with pytest.raises(RuntimeError, match="fallback_transport=None"):
        adapter.product_runtime_contract(runtime)


def test_inspector_rejects_raw_legacy_fallback_before_runtime_normalization() -> None:
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=_UnsafeFallbackTransport(legacy_direct_write_fallback=True),
    )

    assert runtime.governance()["legacy_direct_write_fallback"] is False

    with pytest.raises(RuntimeError, match="legacy_direct_write_fallback=False"):
        adapter.product_runtime_contract(runtime)


@pytest.mark.parametrize(
    ("missing_key", "message"),
    (
        ("fallback_transport", "explicit fallback_transport=None"),
        ("legacy_direct_write_fallback", "legacy_direct_write_fallback=False"),
    ),
)
def test_inspector_requires_explicit_raw_no_fallback_declarations(
    missing_key: str,
    message: str,
) -> None:
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=_MissingFallbackDeclarationTransport(missing_key),
    )

    # Runtime-level defaults must not substitute for missing transport evidence.
    assert runtime.governance()["fallback_transport"] is None
    assert runtime.governance()["legacy_direct_write_fallback"] is False

    with pytest.raises(RuntimeError, match=message):
        adapter.product_runtime_contract(runtime)


def test_direct_contract_construction_derives_schema_and_support_tier() -> None:
    contract = ProductRuntimeContract(**_direct_contract_kwargs())

    assert contract.schema == adapter.PRODUCT_RUNTIME_CONTRACT_SCHEMA == 1
    assert contract.transport == "future-browserless"
    assert contract.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL
    assert contract.legacy_direct_write_fallback is False


def test_direct_contract_cannot_self_supply_schema_or_support_tier() -> None:
    kwargs = _direct_contract_kwargs()

    with pytest.raises(TypeError, match="schema"):
        ProductRuntimeContract(**kwargs, schema=999)

    with pytest.raises(TypeError, match="transport_support_tier"):
        ProductRuntimeContract(
            **kwargs,
            transport_support_tier=ProductTransportSupportTier.PRODUCTION,
        )


def test_direct_contract_requires_legacy_fallback_invariant() -> None:
    kwargs = _direct_contract_kwargs()
    kwargs.pop("legacy_direct_write_fallback")

    with pytest.raises(TypeError, match="legacy_direct_write_fallback"):
        ProductRuntimeContract(**kwargs)


def test_direct_contract_rejects_legacy_fallback() -> None:
    kwargs = _direct_contract_kwargs(transport="browser-owned")
    kwargs["legacy_direct_write_fallback"] = True

    with pytest.raises(RuntimeError, match="legacy_direct_write_fallback=False"):
        ProductRuntimeContract(**kwargs)


def test_direct_contract_constructor_rejects_unsafe_invariants() -> None:
    kwargs = _direct_contract_kwargs(transport="browser-owned")
    kwargs["automatic_write_retry"] = True

    with pytest.raises(RuntimeError, match="automatic_write_retry=False"):
        ProductRuntimeContract(**kwargs)
