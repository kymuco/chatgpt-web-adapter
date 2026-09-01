from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import (
    TOOLS_CONNECTORS,
    WEB_SEARCH,
    CapabilityOwner,
    CapabilityState,
)


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _LegacyProvider:
    def status(self):
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=77,
        )

    def send_text(self, *args, **kwargs):
        raise AssertionError("capability tests must not send")


def test_default_browser_owned_provider_graduates_live_proven_web_search() -> None:
    transport = BrowserOwnedProductTransport(_Client())

    capabilities = transport.capabilities()
    web_search = capabilities.get(WEB_SEARCH)

    assert web_search is not None
    assert web_search.state is CapabilityState.AVAILABLE
    assert web_search.owner is CapabilityOwner.TRANSPORT
    assert web_search.evidence is not None
    assert "PR9.3 live web-search observation gate" in web_search.evidence
    assert "canonical SOURCE and CITATION" in web_search.evidence
    assert "CANONICAL_READBACK" in web_search.evidence
    assert capabilities.state(TOOLS_CONNECTORS) is CapabilityState.UNKNOWN


def test_legacy_provider_without_revision_safe_observation_remains_unknown() -> None:
    transport = BrowserOwnedProductTransport(_Client(), provider=_LegacyProvider())

    capabilities = transport.capabilities()

    assert capabilities.state(WEB_SEARCH) is CapabilityState.UNKNOWN
    assert capabilities.get(WEB_SEARCH).evidence is None
    assert capabilities.state(TOOLS_CONNECTORS) is CapabilityState.UNKNOWN
