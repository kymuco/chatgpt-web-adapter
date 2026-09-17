from __future__ import annotations

import threading
from typing import Any

from . import browser_owned_product_transport_core as _core
from .browser_authority_commit_provider import CommitBoundProductModelProfileProvider
from .browser_authority_commit_runtime import CommitBoundBrowserOwnedProductWriteRuntime
from .browser_authority_lease import (
    BrowserAuthorityPolicy,
    resolve_browser_authority_policy,
)
from .browser_context_canonical import (
    BrowserContextCanonicalClient as _LegacyBrowserContextCanonicalClient,
)
from .browser_context_canonical_v2 import BrowserContextCanonicalClientV2
from .browser_native_provider import BrowserNativeTurnProvider
from .browser_owned_submission_lifecycle import BrowserOwnedSubmissionLifecycle
from .product_rich_input_capability_gate_pr9_4 import (
    gate_browser_owned_rich_input_capabilities,
)
from .product_transport import require_canonical_conversation_client
from .product_web_search_capability_gate_pr9_3 import (
    gate_browser_owned_web_search_capability,
)
from .temporary_product_runtime_pr8_13 import TemporaryProductWriteRuntime

# Preserve the long-standing public-module test/integration seam while composing
# the stricter commit-bound runtime by default.
BrowserOwnedProductWriteRuntime = CommitBoundBrowserOwnedProductWriteRuntime


class BrowserOwnedProductTransport(_core.BrowserOwnedProductTransport):
    """Browser-owned transport with statically composed proven capabilities."""

    def __init__(
        self,
        canonical_client: Any,
        *,
        provider: BrowserNativeTurnProvider | None = None,
        browser_authority_policy: BrowserAuthorityPolicy | str | None = None,
        browser_authority_ttl_ms: int | None = None,
    ) -> None:
        # Keep constructor ownership in the public module. Besides making the
        # composition point explicit, this preserves the long-standing test and
        # integration seam where BrowserOwnedProductWriteRuntime can be replaced
        # on chatgpt_web_adapter.browser_owned_product_transport.
        source_canonical = require_canonical_conversation_client(canonical_client)
        if provider is None:
            provider = CommitBoundProductModelProfileProvider()
        self.provider = provider
        self._browser_context_canonical_enabled = isinstance(
            self.provider,
            BrowserNativeTurnProvider,
        )
        self.canonical_client = (
            source_canonical
            if isinstance(source_canonical, _LegacyBrowserContextCanonicalClient)
            or not self._browser_context_canonical_enabled
            else BrowserContextCanonicalClientV2(source_canonical, self.provider)
        )
        self._model_profile_selection_supported = callable(
            getattr(self.provider, "require_profile", None)
        )
        self._browser_authority_runtime_policy = browser_authority_policy
        self._browser_authority_runtime_ttl_ms = browser_authority_ttl_ms
        self._browser_authority_default_resolution = resolve_browser_authority_policy(
            runtime_policy=browser_authority_policy,
            runtime_ttl_ms=browser_authority_ttl_ms,
        )

        runtime_kwargs: dict[str, Any] = {"provider": self.provider}
        runtime_kwargs.update(
            _core._authority_override_kwargs(
                browser_authority_policy=browser_authority_policy,
                browser_authority_ttl_ms=browser_authority_ttl_ms,
            )
        )
        self._runtime = BrowserOwnedProductWriteRuntime(
            self.canonical_client,
            **runtime_kwargs,
        )
        self._submission_dispatch_lock = threading.RLock()
        self._submission_lifecycle = BrowserOwnedSubmissionLifecycle(self._runtime)
        self._temporary_runtime = TemporaryProductWriteRuntime(self.provider)

    capabilities = gate_browser_owned_rich_input_capabilities(
        gate_browser_owned_web_search_capability(
            _core.BrowserOwnedProductTransport.capabilities
        )
    )


def __getattr__(name: str) -> Any:
    """Delegate untouched implementation details to the frozen legacy core."""

    return getattr(_core, name)
