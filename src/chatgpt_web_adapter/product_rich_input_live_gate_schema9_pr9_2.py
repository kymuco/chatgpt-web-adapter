from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema8_pr9_2 as _v8


SCHEMA = 9
PRODUCT_WRITE_BUDGET = _v8.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema9LiveProvider(_v8.ProductRichInputSchema8LiveProvider):
    """PR9.2 schema-9 support probe on top of the frozen schema-8 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Schema 8 deliberately cannot interpret later support fields. Read the
        # schema-9 claim with another characterization-only RPC. No text or
        # attachment path is supplied, so this remains a zero-write preflight.
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
            raise RuntimeError("PR9_2_SCHEMA9_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA9_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["cross_evidence_channel_exactness"] = response.get(
            "crossEvidenceChannelExactness"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA9_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Reuse every schema-8 assertion after pinning only the historical schema
    # discriminator expected by its frozen validator.
    legacy = dict(support)
    legacy["schema"] = _v8.SCHEMA
    _v8._validate_support(legacy)

    if support.get("cross_evidence_channel_exactness") is not True:
        raise RuntimeError("PR9_2_CROSS_EVIDENCE_CHANNEL_EXACTNESS_NOT_PROVEN")
