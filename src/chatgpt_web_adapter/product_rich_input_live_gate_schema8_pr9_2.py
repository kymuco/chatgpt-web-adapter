from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7


SCHEMA = 8
PRODUCT_WRITE_BUDGET = _v7.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema8LiveProvider(_v7.ProductRichInputLiveProvider):
    """PR9.2 schema-8 support probe on top of the frozen schema-7 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        # First preserve every schema-7 field and its proven parsing semantics.
        support = super().rich_input_support(timeout=timeout)

        # The schema-7 provider intentionally knows nothing about later support
        # fields. A second *zero-write* characterization RPC reads only the four
        # schema-8 closure claims. No text or attachment path is supplied.
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
            raise RuntimeError("PR9_2_SCHEMA8_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA8_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support.update(
            {
                "pre_stage_composer_attachment_clean": response.get(
                    "preStageComposerAttachmentClean"
                ),
                "exact_composer_attachment_set_required": response.get(
                    "exactComposerAttachmentSetRequired"
                ),
                "destructive_cleanup_authority_revalidated_at_close": response.get(
                    "destructiveCleanupAuthorityRevalidatedAtClose"
                ),
                "destructive_cleanup_ownership_change_fails_closed": response.get(
                    "destructiveCleanupOwnershipChangeFailsClosed"
                ),
            }
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA8_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Reuse every schema-7 safety assertion after pinning only the historical
    # schema discriminator expected by that frozen validator.
    legacy = dict(support)
    legacy["schema"] = _v7.SCHEMA
    _v7._validate_support(legacy)

    if support.get("pre_stage_composer_attachment_clean") is not True:
        raise RuntimeError("PR9_2_PRE_STAGE_COMPOSER_ATTACHMENT_CLEAN_NOT_PROVEN")
    if support.get("exact_composer_attachment_set_required") is not True:
        raise RuntimeError("PR9_2_EXACT_COMPOSER_ATTACHMENT_SET_NOT_PROVEN")
    if support.get("destructive_cleanup_authority_revalidated_at_close") is not True:
        raise RuntimeError("PR9_2_DESTRUCTIVE_CLEANUP_REVALIDATION_NOT_PROVEN")
    if support.get("destructive_cleanup_ownership_change_fails_closed") is not True:
        raise RuntimeError(
            "PR9_2_DESTRUCTIVE_CLEANUP_OWNERSHIP_CHANGE_FAIL_CLOSED_NOT_PROVEN"
        )
