from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema20_pr9_2 as _v20

SCHEMA = 21
PRODUCT_WRITE_BUDGET = _v20.PRODUCT_WRITE_BUDGET
_EXPECTED_ARM_BOUNDARY = "AFTER_ALL_VALIDATION_IMMEDIATELY_BEFORE_BUTTON_CLICK"


class ProductRichInputSchema21LiveProvider(_v20.ProductRichInputSchema20LiveProvider):
    """PR9.2 schema-21 validated-click-boundary submit-arm probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Fifteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA21_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA21_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["protected_submit_arm_boundary"] = response.get(
            "protectedSubmitArmBoundary"
        )
        support["protected_submit_arm_after_all_validation"] = response.get(
            "protectedSubmitArmAfterAllValidation"
        )
        support["pre_validation_submit_arm_possible"] = response.get(
            "preValidationSubmitArmPossible"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA21_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v20.SCHEMA
    _v20._validate_support(legacy)

    if support.get("protected_submit_arm_boundary") != _EXPECTED_ARM_BOUNDARY:
        raise RuntimeError("PR9_2_VALIDATED_CLICK_ARM_BOUNDARY_NOT_PROVEN")
    if support.get("protected_submit_arm_after_all_validation") is not True:
        raise RuntimeError("PR9_2_SUBMIT_ARM_AFTER_VALIDATION_NOT_PROVEN")
    if support.get("pre_validation_submit_arm_possible") is not False:
        raise RuntimeError("PR9_2_PRE_VALIDATION_SUBMIT_ARM_NOT_DENIED")
