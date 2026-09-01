from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_capabilities import (
    FILES,
    IMAGES,
    MULTIMODAL_CONTINUATION,
    CapabilityState,
)
from chatgpt_web_adapter.product_model_profile_pr8_10 import ProductModelProfileProvider
from chatgpt_web_adapter.product_rich_input_capability_gate_pr9_4 import (
    gate_browser_owned_rich_input_capabilities,
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


class _CompatibleProvider(ProductModelProfileProvider):
    pass


class _RpcOverrideProvider(ProductModelProfileProvider):
    def _rpc(self, payload, *, timeout, on_event=None):
        raise AssertionError("capability tests must not call provider RPC")


def _assert_rich_input_available(transport: BrowserOwnedProductTransport) -> None:
    capabilities = transport.capabilities()
    for name in (IMAGES, FILES, MULTIMODAL_CONTINUATION):
        entry = capabilities.get(name)
        assert entry is not None
        assert entry.state is CapabilityState.AVAILABLE
        assert entry.evidence is not None
        assert "PR9.2 schema-29 authenticated live closure" in entry.evidence


def _assert_rich_input_conservative(transport: BrowserOwnedProductTransport) -> None:
    capabilities = transport.capabilities()
    assert capabilities.state(IMAGES) is CapabilityState.UNIMPLEMENTED
    assert capabilities.state(FILES) is CapabilityState.UNKNOWN
    assert capabilities.state(MULTIMODAL_CONTINUATION) is CapabilityState.UNIMPLEMENTED


def test_default_browser_owned_provider_freezes_live_proven_rich_input_capabilities() -> None:
    _assert_rich_input_available(BrowserOwnedProductTransport(_Client()))


def test_compatible_provider_subclass_inheriting_write_path_keeps_pr92_capability_authority() -> None:
    _assert_rich_input_available(
        BrowserOwnedProductTransport(_Client(), provider=_CompatibleProvider())
    )


def test_custom_legacy_provider_does_not_inherit_rich_input_capability_authority() -> None:
    _assert_rich_input_conservative(
        BrowserOwnedProductTransport(_Client(), provider=_LegacyProvider())
    )


def test_provider_overriding_rpc_does_not_inherit_pr92_live_proof() -> None:
    _assert_rich_input_conservative(
        BrowserOwnedProductTransport(_Client(), provider=_RpcOverrideProvider())
    )


def test_instance_replacing_send_text_does_not_inherit_pr92_live_proof() -> None:
    provider = _CompatibleProvider()
    provider.send_text = lambda *args, **kwargs: None
    _assert_rich_input_conservative(
        BrowserOwnedProductTransport(_Client(), provider=provider)
    )


def test_instance_replacing_rpc_does_not_inherit_pr92_live_proof() -> None:
    provider = _CompatibleProvider()
    provider._rpc = lambda *args, **kwargs: {}
    _assert_rich_input_conservative(
        BrowserOwnedProductTransport(_Client(), provider=provider)
    )


def test_pr94_capability_gate_installation_is_idempotent() -> None:
    current = BrowserOwnedProductTransport.capabilities
    assert gate_browser_owned_rich_input_capabilities(current) is current
    assert getattr(current, "__pr94_rich_input_capability_gate__", False) is True


def test_root_runtime_reports_pr92_rich_input_as_available_without_promoting_tools_connectors() -> None:
    runtime = adapter.assemble_product_runtime(client=_Client())
    capabilities = runtime.capabilities()

    assert capabilities.state(IMAGES) is CapabilityState.AVAILABLE
    assert capabilities.state(FILES) is CapabilityState.AVAILABLE
    assert capabilities.state(MULTIMODAL_CONTINUATION) is CapabilityState.AVAILABLE
    assert capabilities.state("web_search") is CapabilityState.AVAILABLE
    assert capabilities.state("tools_connectors") is CapabilityState.UNKNOWN
