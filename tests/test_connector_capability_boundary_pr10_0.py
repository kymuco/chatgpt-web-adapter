from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import (
    TOOLS_CONNECTORS,
    CapabilityState,
)


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


def test_pr100_observation_implementation_does_not_pregraduate_connector_capability() -> None:
    capabilities = BrowserOwnedProductTransport(_Client()).capabilities()

    connector_capability = capabilities.get(TOOLS_CONNECTORS)
    assert connector_capability is not None
    assert connector_capability.state is CapabilityState.UNKNOWN
    assert connector_capability.evidence is None
