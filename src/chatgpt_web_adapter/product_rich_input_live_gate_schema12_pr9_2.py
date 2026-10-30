from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema11_pr9_2 as _v11


SCHEMA = 12
PRODUCT_WRITE_BUDGET = _v11.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema12LiveProvider(_v11.ProductRichInputSchema11LiveProvider):
    """PR9.2 schema-12 support probe on top of the frozen schema-11 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-12 fields.
        # This sixth characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA12_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA12_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["poststage_debugger_setup_deadline_bounded"] = response.get(
            "postStageDebuggerSetupDeadlineBounded"
        )
        support["late_poststage_debugger_attach_auto_detached"] = response.get(
            "latePostStageDebuggerAttachAutoDetached"
        )
        support["send_readiness_wait_deadline_bounded"] = response.get(
            "sendReadinessWaitDeadlineBounded"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA12_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v11.SCHEMA
    _v11._validate_support(legacy)

    required = {
        "poststage_debugger_setup_deadline_bounded":
            "PR9_2_POSTSTAGE_DEBUGGER_SETUP_DEADLINE_NOT_PROVEN",
        "late_poststage_debugger_attach_auto_detached":
            "PR9_2_LATE_POSTSTAGE_DEBUGGER_ATTACH_DETACH_NOT_PROVEN",
        "send_readiness_wait_deadline_bounded":
            "PR9_2_SEND_READINESS_WAIT_DEADLINE_NOT_PROVEN",
    }
    for key, error in required.items():
        if support.get(key) is not True:
            raise RuntimeError(error)
