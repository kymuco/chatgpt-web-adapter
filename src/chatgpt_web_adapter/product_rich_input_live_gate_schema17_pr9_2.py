from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema16_pr9_2 as _v16


SCHEMA = 17
PRODUCT_WRITE_BUDGET = _v16.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema17LiveProvider(_v16.ProductRichInputSchema16LiveProvider):
    """PR9.2 schema-17 support probe on top of the frozen schema-16 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-17 fields.
        # This eleventh characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA17_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA17_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["page_turn_prewrite_setup_deadline_bounded"] = response.get(
            "pageTurnPrewriteSetupDeadlineBounded"
        )
        support["late_page_turn_debugger_attach_auto_detached"] = response.get(
            "latePageTurnDebuggerAttachAutoDetached"
        )
        support["post_write_response_body_deadline_bounded"] = response.get(
            "postWriteResponseBodyDeadlineBounded"
        )
        support["post_write_composer_readiness_deadline_bounded"] = response.get(
            "postWriteComposerReadinessDeadlineBounded"
        )
        support["post_write_final_tab_read_deadline_bounded"] = response.get(
            "postWriteFinalTabReadDeadlineBounded"
        )
        support["post_write_optional_reads_non_authoritative"] = response.get(
            "postWriteOptionalReadsNonAuthoritative"
        )
        support["post_write_optional_reads_can_rewrite_submitted_outcome"] = response.get(
            "postWriteOptionalReadsCanRewriteSubmittedOutcome"
        )
        support["post_write_rpc_return_reserve_ms"] = response.get(
            "postWriteRpcReturnReserveMs"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA17_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v16.SCHEMA
    _v16._validate_support(legacy)

    if support.get("page_turn_prewrite_setup_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_PAGE_TURN_PREWRITE_SETUP_DEADLINE_BOUND_NOT_PROVEN")
    if support.get("late_page_turn_debugger_attach_auto_detached") is not True:
        raise RuntimeError("PR9_2_LATE_PAGE_TURN_DEBUGGER_ATTACH_RELEASE_NOT_PROVEN")
    if support.get("post_write_response_body_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_RESPONSE_BODY_BOUND_NOT_PROVEN")
    if support.get("post_write_composer_readiness_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_COMPOSER_READINESS_BOUND_NOT_PROVEN")
    if support.get("post_write_final_tab_read_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_FINAL_TAB_READ_BOUND_NOT_PROVEN")
    if support.get("post_write_optional_reads_non_authoritative") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_OPTIONAL_READ_AUTHORITY_NOT_PROVEN")
    if support.get("post_write_optional_reads_can_rewrite_submitted_outcome") is not False:
        raise RuntimeError("PR9_2_POST_WRITE_OPTIONAL_READ_OUTCOME_AUTHORITY_NOT_PROVEN")
    reserve = support.get("post_write_rpc_return_reserve_ms")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve <= 0:
        raise RuntimeError("PR9_2_POST_WRITE_RPC_RETURN_RESERVE_NOT_PROVEN")
