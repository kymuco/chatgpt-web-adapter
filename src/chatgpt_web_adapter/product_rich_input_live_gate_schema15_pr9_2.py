from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema14_pr9_2 as _v14


SCHEMA = 15
PRODUCT_WRITE_BUDGET = _v14.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema15LiveProvider(_v14.ProductRichInputSchema14LiveProvider):
    """PR9.2 schema-15 support probe on top of the frozen schema-14 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-15 fields.
        # This ninth characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA15_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA15_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["pre_stage_successful_debugger_detach_deadline_bounded"] = response.get(
            "preStageSuccessfulDebuggerDetachDeadlineBounded"
        )
        support["post_stage_successful_debugger_detach_deadline_bounded"] = (
            response.get("postStageSuccessfulDebuggerDetachDeadlineBounded")
        )
        support["debugger_ownership_handoff_completed_before_next_attach"] = (
            response.get("debuggerOwnershipHandoffCompletedBeforeNextAttach")
        )
        support["failure_path_debugger_detach_best_effort"] = response.get(
            "failurePathDebuggerDetachBestEffort"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA15_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v14.SCHEMA
    _v14._validate_support(legacy)

    if support.get("pre_stage_successful_debugger_detach_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_PRESTAGE_SUCCESSFUL_DETACH_BOUND_NOT_PROVEN")
    if (
        support.get("post_stage_successful_debugger_detach_deadline_bounded")
        is not True
    ):
        raise RuntimeError("PR9_2_POSTSTAGE_SUCCESSFUL_DETACH_BOUND_NOT_PROVEN")
    if (
        support.get("debugger_ownership_handoff_completed_before_next_attach")
        is not True
    ):
        raise RuntimeError("PR9_2_DEBUGGER_OWNERSHIP_HANDOFF_NOT_PROVEN")
    if support.get("failure_path_debugger_detach_best_effort") is not True:
        raise RuntimeError("PR9_2_FAILURE_PATH_DETACH_SEMANTICS_NOT_PROVEN")
