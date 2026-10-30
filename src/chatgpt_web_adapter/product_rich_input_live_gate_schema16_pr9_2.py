from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema15_pr9_2 as _v15

SCHEMA = 16
PRODUCT_WRITE_BUDGET = _v15.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema16LiveProvider(_v15.ProductRichInputSchema15LiveProvider):
    """PR9.2 schema-16 support probe on top of the frozen schema-15 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-16 fields.
        # This tenth characterization-only RPC carries neither text nor paths.
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "characterizeRichInputSupport": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if response.get("request_id") != request_id:
            raise RuntimeError("PR9_2_SCHEMA16_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA16_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["durable_fence_read_deadline_bounded"] = response.get(
            "durableFenceReadDeadlineBounded"
        )
        support["runtime_tab_acquisition_deadline_bounded"] = response.get(
            "runtimeTabAcquisitionDeadlineBounded"
        )
        support["inherited_page_turn_post_write_teardown_non_blocking"] = response.get(
            "inheritedPageTurnPostWriteTeardownNonBlocking"
        )
        support["post_write_debugger_detach_best_effort"] = response.get(
            "postWriteDebuggerDetachBestEffort"
        )
        support["post_write_debugger_targets_probe_best_effort"] = response.get(
            "postWriteDebuggerTargetsProbeBestEffort"
        )
        support["post_write_teardown_can_rewrite_submitted_outcome"] = response.get(
            "postWriteTeardownCanRewriteSubmittedOutcome"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA16_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v15.SCHEMA
    _v15._validate_support(legacy)

    if support.get("durable_fence_read_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_DURABLE_FENCE_READ_DEADLINE_BOUND_NOT_PROVEN")
    if support.get("runtime_tab_acquisition_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_RUNTIME_TAB_ACQUISITION_DEADLINE_BOUND_NOT_PROVEN")
    if support.get("inherited_page_turn_post_write_teardown_non_blocking") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_PAGE_TURN_TEARDOWN_BOUNDARY_NOT_PROVEN")
    if support.get("post_write_debugger_detach_best_effort") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_DEBUGGER_DETACH_SEMANTICS_NOT_PROVEN")
    if support.get("post_write_debugger_targets_probe_best_effort") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_DEBUGGER_TARGETS_SEMANTICS_NOT_PROVEN")
    if support.get("post_write_teardown_can_rewrite_submitted_outcome") is not False:
        raise RuntimeError("PR9_2_POST_WRITE_TEARDOWN_OUTCOME_AUTHORITY_NOT_PROVEN")
