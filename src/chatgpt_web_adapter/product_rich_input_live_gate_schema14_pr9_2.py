from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema13_pr9_2 as _v13


SCHEMA = 14
PRODUCT_WRITE_BUDGET = _v13.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema14LiveProvider(_v13.ProductRichInputSchema13LiveProvider):
    """PR9.2 schema-14 support probe on top of the frozen schema-13 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-14 fields.
        # This eighth characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA14_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA14_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["rich_input_model_profile_combination_supported"] = response.get(
            "richInputModelProfileCombinationSupported"
        )
        support["rich_input_model_profile_combination_fails_before_staging"] = response.get(
            "richInputModelProfileCombinationFailsBeforeStaging"
        )
        support["rich_input_model_profile_combination_fails_before_write"] = response.get(
            "richInputModelProfileCombinationFailsBeforeWrite"
        )
        support["pr810_raw_prewrite_selector_excluded_from_rich_input"] = response.get(
            "pr810RawPrewriteSelectorExcludedFromRichInput"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA14_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v13.SCHEMA
    _v13._validate_support(legacy)

    if support.get("rich_input_model_profile_combination_supported") is not False:
        raise RuntimeError("PR9_2_RICH_INPUT_MODEL_PROFILE_COMBINATION_SCOPE_NOT_PROVEN")
    if support.get("rich_input_model_profile_combination_fails_before_staging") is not True:
        raise RuntimeError("PR9_2_RICH_INPUT_MODEL_PROFILE_PRESTAGING_GUARD_NOT_PROVEN")
    if support.get("rich_input_model_profile_combination_fails_before_write") is not True:
        raise RuntimeError("PR9_2_RICH_INPUT_MODEL_PROFILE_PREWRITE_GUARD_NOT_PROVEN")
    if support.get("pr810_raw_prewrite_selector_excluded_from_rich_input") is not True:
        raise RuntimeError("PR9_2_PR810_RAW_PREWRITE_SELECTOR_EXCLUSION_NOT_PROVEN")
