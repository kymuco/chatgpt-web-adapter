from __future__ import annotations

from typing import Any

from .browser_authority_instant_effort_selection_parsers_pr8_8 import parse_selection_record, parse_support
from .browser_authority_instant_latency_pr8_8 import InstantModeLatencyProvider

SCHEMA = 1


class InstantEffortSelectionProvider(InstantModeLatencyProvider):
    """Usable Instant provider backed by the current reasoning-effort slider UI."""

    def instant_effort_selection_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        response = self._characterization_rpc(
            {"characterizeInstantEffortSelectionSupport": True}, timeout=timeout
        )
        return parse_support(response)

    def instant_effort_selection_for_lease(
        self, lease_id: str, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        response = self._characterization_rpc(
            {
                "characterizeInstantSelectionRecord": True,
                "expectedBrowserAuthorityLeaseId": lease_id.strip(),
            },
            timeout=timeout,
        )
        return parse_selection_record(response)
