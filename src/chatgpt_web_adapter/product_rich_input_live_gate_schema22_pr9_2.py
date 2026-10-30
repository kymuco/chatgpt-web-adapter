from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema21_pr9_2 as _v21


SCHEMA = 22
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema22LiveProvider(_v21.ProductRichInputSchema21LiveProvider):
    """PR9.2 schema-22 attachment-owned composer-evidence probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Sixteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA22_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA22_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["attachment_evidence_role_groups_require_removal_control"] = response.get(
            "attachmentEvidenceRoleGroupsRequireRemovalControl"
        )
        support["composer_control_role_groups_excluded_from_attachment_evidence"] = response.get(
            "composerControlRoleGroupsExcludedFromAttachmentEvidence"
        )
        support["pre_stage_clean_uses_attachment_owned_evidence_only"] = response.get(
            "preStageCleanUsesAttachmentOwnedEvidenceOnly"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA22_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v21.SCHEMA
    _v21._validate_support(legacy)

    if support.get("attachment_evidence_role_groups_require_removal_control") is not True:
        raise RuntimeError("PR9_2_ATTACHMENT_ROLE_GROUP_OWNERSHIP_NOT_PROVEN")
    if support.get("composer_control_role_groups_excluded_from_attachment_evidence") is not True:
        raise RuntimeError("PR9_2_COMPOSER_CONTROL_GROUP_EXCLUSION_NOT_PROVEN")
    if support.get("pre_stage_clean_uses_attachment_owned_evidence_only") is not True:
        raise RuntimeError("PR9_2_ATTACHMENT_OWNED_CLEAN_PROOF_NOT_PROVEN")
