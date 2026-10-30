from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema24_pr9_2 as _v24


SCHEMA = 25
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema25LiveProvider(_v24.ProductRichInputSchema24LiveProvider):
    """PR9.2 schema-25 indexed removal-label support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Nineteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA25_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA25_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["indexed_removal_ui_prefix_normalization_supported"] = response.get(
            "indexedRemovalUiPrefixNormalizationSupported"
        )
        support["indexed_removal_ui_prefix_requires_known_noun_ordinal_and_colon"] = (
            response.get("indexedRemovalUiPrefixRequiresKnownNounOrdinalAndColon")
        )
        support["indexed_removal_ui_prefix_basename_compared_exactly"] = response.get(
            "indexedRemovalUiPrefixBasenameComparedExactly"
        )
        support["unknown_removal_ui_metadata_still_fails_closed"] = response.get(
            "unknownRemovalUiMetadataStillFailsClosed"
        )
        support["removal_normalization_shared_by_production_and_diagnostic"] = (
            response.get("removalNormalizationSharedByProductionAndDiagnostic")
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA25_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v24.SCHEMA
    _v24._validate_support(legacy)

    if support.get("indexed_removal_ui_prefix_normalization_supported") is not True:
        raise RuntimeError("PR9_2_SCHEMA25_INDEXED_REMOVAL_NORMALIZATION_NOT_PROVEN")
    if (
        support.get("indexed_removal_ui_prefix_requires_known_noun_ordinal_and_colon")
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA25_INDEXED_REMOVAL_PREFIX_BOUNDARY_NOT_PROVEN")
    if support.get("indexed_removal_ui_prefix_basename_compared_exactly") is not True:
        raise RuntimeError("PR9_2_SCHEMA25_EXACT_REMOVAL_BASENAME_NOT_PROVEN")
    if support.get("unknown_removal_ui_metadata_still_fails_closed") is not True:
        raise RuntimeError(
            "PR9_2_SCHEMA25_UNKNOWN_REMOVAL_METADATA_FAIL_CLOSED_NOT_PROVEN"
        )
    if (
        support.get("removal_normalization_shared_by_production_and_diagnostic")
        is not True
    ):
        raise RuntimeError("PR9_2_SCHEMA25_SHARED_REMOVAL_NORMALIZER_NOT_PROVEN")
