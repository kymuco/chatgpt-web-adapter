from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema10_pr9_2 as _v10

SCHEMA = 11
PRODUCT_WRITE_BUDGET = _v10.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema11LiveProvider(_v10.ProductRichInputSchema10LiveProvider):
    """PR9.2 schema-11 support probe on top of the frozen schema-10 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately know nothing about schema-11 fields.
        # This fifth characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA11_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA11_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["structured_removal_control_basename_parsing"] = response.get(
            "structuredRemovalControlBasenameParsing"
        )
        support["attachment_evidence_reads_deadline_bounded"] = response.get(
            "attachmentEvidenceReadsDeadlineBounded"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA11_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v10.SCHEMA
    _v10._validate_support(legacy)

    if support.get("structured_removal_control_basename_parsing") is not True:
        raise RuntimeError("PR9_2_STRUCTURED_REMOVAL_BASENAME_NOT_PROVEN")
    if support.get("attachment_evidence_reads_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_ATTACHMENT_EVIDENCE_READ_DEADLINE_NOT_PROVEN")
