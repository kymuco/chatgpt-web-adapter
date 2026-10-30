from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema24_pr9_2 as _v24
from . import product_rich_input_live_gate_schema26_pr9_2 as _v26


SCHEMA = 27
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema27LiveProvider(_v26.ProductRichInputSchema26LiveProvider):
    """PR9.2 schema-27 bidirectional indexed-removal ambiguity support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Twenty-first characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA27_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA27_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["indexed_removal_ambiguity_bidirectional_fail_closed"] = response.get(
            "indexedRemovalAmbiguityBidirectionalFailClosed"
        )
        support[
            "indexed_removal_literal_interpretation_requires_independent_filename_group"
        ] = response.get(
            "indexedRemovalLiteralInterpretationRequiresIndependentFilenameGroup"
        )
        support[
            "indexed_removal_stripped_interpretation_requires_independent_filename_group"
        ] = response.get(
            "indexedRemovalStrippedInterpretationRequiresIndependentFilenameGroup"
        )
        support["indexed_removal_removal_only_authority_allowed"] = response.get(
            "indexedRemovalRemovalOnlyAuthorityAllowed"
        )
        support["unindexed_removal_literal_semantics_preserved"] = response.get(
            "unindexedRemovalLiteralSemanticsPreserved"
        )
        support[
            "indexed_removal_interpretation_selected_by_exact_filename_group_only"
        ] = response.get("indexedRemovalInterpretationSelectedByExactFilenameGroupOnly")
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA27_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Schemas 25 and 26 are superseded parser experiments. Do not require their
    # semantic claims as prerequisites for the final ambiguity-safe contract.
    # Preserve the complete reviewed authority chain through schema 24, then require
    # the replacement schema-27 semantics below.
    legacy = dict(support)
    legacy["schema"] = _v24.SCHEMA
    _v24._validate_support(legacy)

    if support.get("indexed_removal_ambiguity_bidirectional_fail_closed") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_BIDIRECTIONAL_AMBIGUITY_NOT_FAIL_CLOSED")
    if (
        support.get(
            "indexed_removal_literal_interpretation_requires_independent_filename_group"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA27_LITERAL_INDEXED_CORROBORATION_NOT_PROVEN")
    if (
        support.get(
            "indexed_removal_stripped_interpretation_requires_independent_filename_group"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA27_STRIPPED_INDEXED_CORROBORATION_NOT_PROVEN")
    if support.get("indexed_removal_removal_only_authority_allowed") is not False:
        raise RuntimeError("PR9_2_SCHEMA27_INDEXED_REMOVAL_ONLY_AUTHORITY_NOT_REVOKED")
    if support.get("unindexed_removal_literal_semantics_preserved") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_UNINDEXED_LITERAL_SEMANTICS_NOT_PRESERVED")
    if (
        support.get(
            "indexed_removal_interpretation_selected_by_exact_filename_group_only"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA27_INDEXED_INTERPRETATION_SELECTOR_NOT_PROVEN")
