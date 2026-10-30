from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema23_pr9_2 as _v23


SCHEMA = 24
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema24LiveProvider(_v23.ProductRichInputSchema23LiveProvider):
    """PR9.2 schema-24 official-composer mount support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Eighteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA24_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA24_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["pre_stage_official_composer_mount_awaited"] = response.get(
            "preStageOfficialComposerMountAwaited"
        )
        support["pre_stage_official_composer_mount_wait_deadline_bounded"] = response.get(
            "preStageOfficialComposerMountWaitDeadlineBounded"
        )
        support["official_composer_mount_uses_production_attachment_evidence_reader"] = response.get(
            "officialComposerMountUsesProductionAttachmentEvidenceReader"
        )
        support["tab_complete_alone_can_prove_composer_mounted"] = response.get(
            "tabCompleteAloneCanProveComposerMounted"
        )
        support["missing_composer_before_mount_classified_dirty"] = response.get(
            "missingComposerBeforeMountClassifiedDirty"
        )
        support["mounted_attachment_evidence_still_fails_closed"] = response.get(
            "mountedAttachmentEvidenceStillFailsClosed"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA24_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v23.SCHEMA
    _v23._validate_support(legacy)

    if support.get("pre_stage_official_composer_mount_awaited") is not True:
        raise RuntimeError("PR9_2_SCHEMA24_COMPOSER_MOUNT_WAIT_NOT_PROVEN")
    if support.get("pre_stage_official_composer_mount_wait_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_SCHEMA24_COMPOSER_MOUNT_DEADLINE_NOT_PROVEN")
    if support.get("official_composer_mount_uses_production_attachment_evidence_reader") is not True:
        raise RuntimeError("PR9_2_SCHEMA24_PRODUCTION_MOUNT_EVIDENCE_NOT_PROVEN")
    if support.get("tab_complete_alone_can_prove_composer_mounted") is not False:
        raise RuntimeError("PR9_2_SCHEMA24_TAB_COMPLETE_MOUNT_AUTHORITY_NOT_REVOKED")
    if support.get("missing_composer_before_mount_classified_dirty") is not False:
        raise RuntimeError("PR9_2_SCHEMA24_TRANSIENT_MISSING_COMPOSER_STILL_DIRTY")
    if support.get("mounted_attachment_evidence_still_fails_closed") is not True:
        raise RuntimeError("PR9_2_SCHEMA24_ATTACHMENT_FAIL_CLOSED_NOT_PROVEN")
