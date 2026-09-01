from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .browser_owned_product_transport import BrowserOwnedProductTransport
from .product_capabilities import (
    FILES,
    IMAGES,
    MULTIMODAL_CONTINUATION,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from .product_model_profile_pr8_10 import ProductModelProfileProvider

_PR94_RICH_INPUT_CAPABILITY_GATE_MARKER = "__pr94_rich_input_capability_gate__"
_PR94_RICH_INPUT_CAPABILITY_NAMES = frozenset(
    {IMAGES, FILES, MULTIMODAL_CONTINUATION}
)
_PR94_RICH_INPUT_LIVE_EVIDENCE = (
    "PR9.2 schema-29 authenticated live closure: image new chat, general file new chat, "
    "and multimodal continuation each produced attachment-dependent answers with exact "
    "attachment count, validated-click request-body correlation, CANONICAL_READBACK "
    "finality, no automatic write retry, and no fallback transport"
)


def _provider_uses_proven_pr92_rich_input_path(provider: Any) -> bool:
    """Return whether a provider preserves the live-proven PR9.2 write path.

    The PR9.2 live provider subclasses ProductModelProfileProvider only to add
    characterization RPCs; the actual write/RPC implementation is inherited unchanged.
    A custom provider, or a subclass overriding either send_text or _rpc, must not inherit
    rich-input capability authority merely because it shares the browser-owned transport.
    """

    if not isinstance(provider, ProductModelProfileProvider):
        return False
    return (
        getattr(type(provider), "send_text", None) is ProductModelProfileProvider.send_text
        and getattr(type(provider), "_rpc", None) is ProductModelProfileProvider._rpc
    )


def gate_browser_owned_rich_input_capabilities(
    capabilities: Callable[..., ProductCapabilities],
) -> Callable[..., ProductCapabilities]:
    """Graduate PR9.2 rich-input capabilities only on the proven provider path."""

    if getattr(capabilities, _PR94_RICH_INPUT_CAPABILITY_GATE_MARKER, False):
        return capabilities

    @wraps(capabilities)
    def gated(
        self: BrowserOwnedProductTransport,
        *args: Any,
        **kwargs: Any,
    ) -> ProductCapabilities:
        declared = capabilities(self, *args, **kwargs)
        if not isinstance(declared, ProductCapabilities):
            raise TypeError(
                "BrowserOwnedProductTransport.capabilities() must return ProductCapabilities"
            )

        provider = getattr(self, "provider", None)
        if not _provider_uses_proven_pr92_rich_input_path(provider):
            return declared

        changed = False
        entries: list[ProductCapability] = []
        for entry in declared.entries:
            if (
                entry.name in _PR94_RICH_INPUT_CAPABILITY_NAMES
                and entry.state is not CapabilityState.AVAILABLE
            ):
                changed = True
                entries.append(
                    ProductCapability(
                        name=entry.name,
                        state=CapabilityState.AVAILABLE,
                        owner=entry.owner,
                        evidence=_PR94_RICH_INPUT_LIVE_EVIDENCE,
                    )
                )
            else:
                entries.append(entry)

        if not changed:
            return declared
        return ProductCapabilities.from_entries(
            transport=declared.transport,
            product_semantics=declared.product_semantics,
            entries=entries,
        )

    setattr(gated, _PR94_RICH_INPUT_CAPABILITY_GATE_MARKER, True)
    return gated


def install_browser_owned_rich_input_capability_gate() -> None:
    current = BrowserOwnedProductTransport.capabilities
    BrowserOwnedProductTransport.capabilities = gate_browser_owned_rich_input_capabilities(
        current
    )
