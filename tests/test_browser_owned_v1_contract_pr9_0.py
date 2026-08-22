from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport


class _Canonical:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _NoWriteProvider:
    """Construction-only provider; contract inspection must never perform a write."""

    def send_text(self, *args, **kwargs):
        raise AssertionError("PR9.0 contract inspection must not perform a product write")


def test_real_browser_owned_transport_declares_schema1_finality_governance() -> None:
    transport = BrowserOwnedProductTransport(
        _Canonical(),
        provider=_NoWriteProvider(),
    )

    governance = transport.governance()

    assert governance["incremental_observation_is_canonical_finality"] is False
    assert governance["streaming_canonical_finality_authoritative"] is True
    assert governance["automatic_write_retry"] is False
    assert governance["ambiguous_write_requires_reconciliation"] is True


def test_real_browser_owned_runtime_satisfies_frozen_schema1_contract_without_write() -> None:
    transport = BrowserOwnedProductTransport(
        _Canonical(),
        provider=_NoWriteProvider(),
    )
    runtime = adapter.ChatGPTProductRuntime(
        _Canonical(),
        write_transport=transport,
    )

    contract = adapter.product_runtime_contract(runtime)
    payload = contract.to_dict()

    assert payload["schema"] == adapter.PRODUCT_RUNTIME_CONTRACT_SCHEMA == 1
    assert payload["transport"] == "browser-owned"
    assert payload["transport_support_tier"] == "PRODUCTION"
    assert payload["product_semantics"] == "ordinary-chatgpt"
    assert payload["interfaces"] == {
        "canonical": "CanonicalConversationClient",
        "write_transport": "ProductWriteTransport",
    }
    assert payload["invariants"]["automatic_write_retry"] is False
    assert payload["invariants"]["fallback_transport"] is None
    assert payload["invariants"]["ambiguous_write_requires_reconciliation"] is True
    assert payload["invariants"]["incremental_observation_is_canonical_finality"] is False
    assert payload["invariants"]["browser_implementation_required_by_caller"] is False
