from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema22_pr9_2 as _v22

SCHEMA = 23
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema23LiveProvider(_v22.ProductRichInputSchema22LiveProvider):
    """PR9.2 schema-23 independent filename-evidence support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Seventeenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA23_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA23_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["attachment_evidence_role_groups_require_removal_control"] = (
            response.get("attachmentEvidenceRoleGroupsRequireRemovalControl")
        )
        support["attachment_filename_groups_independent_of_removal_controls"] = (
            response.get("attachmentFilenameGroupsIndependentOfRemovalControls")
        )
        support["composer_control_group_exclusion_uses_structure"] = response.get(
            "composerControlGroupExclusionUsesStructure"
        )
        support["unclassified_role_groups_fail_closed_as_attachment_evidence"] = (
            response.get("unclassifiedRoleGroupsFailClosedAsAttachmentEvidence")
        )
        support["composer_control_role_groups_excluded_from_attachment_evidence"] = (
            response.get("composerControlRoleGroupsExcludedFromAttachmentEvidence")
        )
        support["pre_stage_clean_uses_attachment_owned_evidence_only"] = response.get(
            "preStageCleanUsesAttachmentOwnedEvidenceOnly"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA23_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Schema 23 deliberately supersedes schema 22's
    # attachmentEvidenceRoleGroupsRequireRemovalControl=true claim, so validate
    # the complete immutable safety chain through schema 21 and then require the
    # new independent filename-channel contract explicitly.
    legacy = dict(support)
    legacy["schema"] = _v21.SCHEMA
    _v21._validate_support(legacy)

    if (
        support.get("attachment_evidence_role_groups_require_removal_control")
        is not False
    ):
        raise RuntimeError("PR9_2_SCHEMA23_REMOVAL_DEPENDENCY_NOT_REMOVED")
    if (
        support.get("attachment_filename_groups_independent_of_removal_controls")
        is not True
    ):
        raise RuntimeError("PR9_2_FILENAME_GROUP_INDEPENDENCE_NOT_PROVEN")
    if support.get("composer_control_group_exclusion_uses_structure") is not True:
        raise RuntimeError("PR9_2_STRUCTURAL_COMPOSER_GROUP_EXCLUSION_NOT_PROVEN")
    if (
        support.get("unclassified_role_groups_fail_closed_as_attachment_evidence")
        is not True
    ):
        raise RuntimeError("PR9_2_UNKNOWN_ROLE_GROUP_FAIL_CLOSED_NOT_PROVEN")
    if (
        support.get("composer_control_role_groups_excluded_from_attachment_evidence")
        is not True
    ):
        raise RuntimeError("PR9_2_COMPOSER_CONTROL_GROUP_EXCLUSION_NOT_PROVEN")
    if support.get("pre_stage_clean_uses_attachment_owned_evidence_only") is not True:
        raise RuntimeError("PR9_2_ATTACHMENT_OWNED_CLEAN_PROOF_NOT_PROVEN")
