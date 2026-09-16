from __future__ import annotations

import hmac
import threading
from typing import Any

from .product_model_profile_pr8_10 import ProductModelProfileProvider


class CommitBoundProductModelProfileProvider(ProductModelProfileProvider):
    """Expose a fresh Browser Authority Lease only when the product write starts.

    The browser-owned runtime issues a lease before entering the lower product
    client. Existing-conversation submissions perform canonical baseline reads
    before the provider write. Those reads are prewrite observations and must not
    present the fresh lease to the browser extension before that lease has reached
    ``executeNativeTurn`` and become part of extension authority state.

    Keep the newly issued lease pending in Python until ``_send_text_request`` is
    entered. From that point through postwrite canonical readback, the normal
    BrowserNativeTurnProvider lease surface remains unchanged.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pending_browser_authority_context = threading.local()

    def set_browser_authority_lease(self, lease_id: str) -> None:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("browser authority lease_id is required")
        self._pending_browser_authority_context.lease_id = lease_id.strip()

    def clear_browser_authority_lease(self) -> None:
        if hasattr(self._pending_browser_authority_context, "lease_id"):
            del self._pending_browser_authority_context.lease_id
        super().clear_browser_authority_lease()

    def _pending_browser_authority_lease_id(self) -> str | None:
        value = getattr(self._pending_browser_authority_context, "lease_id", None)
        return value if isinstance(value, str) and value else None

    def _browser_authority_write_boundary_entered(self, lease_id: str) -> bool:
        """Return whether this exact staged lease reached the provider write boundary."""

        if not isinstance(lease_id, str) or not lease_id.strip():
            return False
        current = self._current_browser_authority_lease_id()
        return current is not None and hmac.compare_digest(current, lease_id.strip())

    def _activate_pending_browser_authority_lease(self) -> None:
        lease_id = self._pending_browser_authority_lease_id()
        if lease_id is not None:
            super().set_browser_authority_lease(lease_id)

    def _send_text_request(self, *args: Any, **kwargs: Any):
        # This is the exact boundary immediately before BrowserNativeTurnProvider
        # constructs and delegates the lease-bearing product turn. Canonical
        # baseline reads happen before this method is entered.
        self._activate_pending_browser_authority_lease()
        return super()._send_text_request(*args, **kwargs)


__all__ = ["CommitBoundProductModelProfileProvider"]
