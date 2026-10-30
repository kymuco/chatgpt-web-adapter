from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema9_pr9_2 as _v9

SCHEMA = 10
PRODUCT_WRITE_BUDGET = _v9.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema10LiveProvider(_v9.ProductRichInputSchema9LiveProvider):
    """PR9.2 schema-10 support probe on top of the frozen schema-9 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Earlier frozen gates deliberately cannot interpret later fields. This
        # fourth characterization-only RPC carries no text or attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA10_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA10_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["official_composer_required_for_attachment_evidence"] = response.get(
            "officialComposerRequiredForAttachmentEvidence"
        )
        support["exact_basename_association_required"] = response.get(
            "exactBasenameAssociationRequired"
        )
        support["prestage_debugger_setup_deadline_bounded"] = response.get(
            "preStageDebuggerSetupDeadlineBounded"
        )
        support["late_prestage_debugger_attach_auto_detached"] = response.get(
            "latePreStageDebuggerAttachAutoDetached"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA10_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v9.SCHEMA
    _v9._validate_support(legacy)

    required = {
        "official_composer_required_for_attachment_evidence": "PR9_2_OFFICIAL_COMPOSER_ATTACHMENT_EVIDENCE_NOT_PROVEN",
        "exact_basename_association_required": "PR9_2_EXACT_BASENAME_ASSOCIATION_NOT_PROVEN",
        "prestage_debugger_setup_deadline_bounded": "PR9_2_PRESTAGE_DEBUGGER_SETUP_DEADLINE_NOT_PROVEN",
        "late_prestage_debugger_attach_auto_detached": "PR9_2_LATE_PRESTAGE_DEBUGGER_ATTACH_DETACH_NOT_PROVEN",
    }
    for key, error in required.items():
        if support.get(key) is not True:
            raise RuntimeError(error)
