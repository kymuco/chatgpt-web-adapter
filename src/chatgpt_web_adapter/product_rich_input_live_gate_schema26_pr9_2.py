from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema25_pr9_2 as _v25

SCHEMA = 26
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema26LiveProvider(_v25.ProductRichInputSchema25LiveProvider):
    """PR9.2 schema-26 ambiguity-safe indexed removal-label support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Twentieth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA26_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA26_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["indexed_removal_ui_prefix_requires_independent_filename_group"] = (
            response.get("indexedRemovalUiPrefixRequiresIndependentFilenameGroup")
        )
        support["removal_only_indexed_ui_prefix_normalization_allowed"] = response.get(
            "removalOnlyIndexedUiPrefixNormalizationAllowed"
        )
        support["literal_post_action_removal_basename_preserved"] = response.get(
            "literalPostActionRemovalBasenamePreserved"
        )
        support[
            "ambiguous_indexed_removal_label_fails_closed_without_filename_group"
        ] = response.get("ambiguousIndexedRemovalLabelFailsClosedWithoutFilenameGroup")
        support["indexed_removal_candidate_still_compared_exactly"] = response.get(
            "indexedRemovalCandidateStillComparedExactly"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA26_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v25.SCHEMA
    _v25._validate_support(legacy)

    if (
        support.get("indexed_removal_ui_prefix_requires_independent_filename_group")
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA26_INDEXED_REMOVAL_CORROBORATION_NOT_PROVEN")
    if support.get("removal_only_indexed_ui_prefix_normalization_allowed") is not False:
        raise RuntimeError(
            "PR9_2_SCHEMA26_REMOVAL_ONLY_INDEXED_NORMALIZATION_NOT_REVOKED"
        )
    if support.get("literal_post_action_removal_basename_preserved") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_LITERAL_REMOVAL_BASENAME_NOT_PRESERVED")
    if (
        support.get(
            "ambiguous_indexed_removal_label_fails_closed_without_filename_group"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA26_AMBIGUOUS_INDEXED_REMOVAL_NOT_FAIL_CLOSED")
    if support.get("indexed_removal_candidate_still_compared_exactly") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_INDEXED_REMOVAL_EXACTNESS_NOT_PROVEN")
