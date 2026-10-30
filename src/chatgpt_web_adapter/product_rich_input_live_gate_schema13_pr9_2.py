from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema12_pr9_2 as _v12


SCHEMA = 13
PRODUCT_WRITE_BUDGET = _v12.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema13LiveProvider(_v12.ProductRichInputSchema12LiveProvider):
    """PR9.2 schema-13 support probe on top of the frozen schema-12 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-13 fields.
        # This seventh characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA13_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA13_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["attachment_staging_primitive_deadline_bounded"] = response.get(
            "attachmentStagingPrimitiveDeadlineBounded"
        )
        support["staging_debugger_setup_deadline_bounded"] = response.get(
            "stagingDebuggerSetupDeadlineBounded"
        )
        support["staging_composer_readiness_deadline_bounded"] = response.get(
            "stagingComposerReadinessDeadlineBounded"
        )
        support["staging_file_input_lookup_deadline_bounded"] = response.get(
            "stagingFileInputLookupDeadlineBounded"
        )
        support["staging_fence_persistence_deadline_bounded"] = response.get(
            "stagingFencePersistenceDeadlineBounded"
        )
        support["staging_file_selection_deadline_bounded"] = response.get(
            "stagingFileSelectionDeadlineBounded"
        )
        support["staging_post_selection_cleanup_deadline_bounded"] = response.get(
            "stagingPostSelectionCleanupDeadlineBounded"
        )
        support["late_staging_debugger_attach_auto_detached"] = response.get(
            "lateStagingDebuggerAttachAutoDetached"
        )
        support["late_file_selection_fails_closed_behind_durable_fence"] = response.get(
            "lateFileSelectionFailsClosedBehindDurableFence"
        )
        support["post_selection_cleanup_best_effort_after_timeout"] = response.get(
            "postSelectionCleanupBestEffortAfterTimeout"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA13_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v12.SCHEMA
    _v12._validate_support(legacy)

    required = {
        "attachment_staging_primitive_deadline_bounded":
            "PR9_2_ATTACHMENT_STAGING_PRIMITIVE_DEADLINE_NOT_PROVEN",
        "staging_debugger_setup_deadline_bounded":
            "PR9_2_STAGING_DEBUGGER_SETUP_DEADLINE_NOT_PROVEN",
        "staging_composer_readiness_deadline_bounded":
            "PR9_2_STAGING_COMPOSER_READINESS_DEADLINE_NOT_PROVEN",
        "staging_file_input_lookup_deadline_bounded":
            "PR9_2_STAGING_FILE_INPUT_LOOKUP_DEADLINE_NOT_PROVEN",
        "staging_fence_persistence_deadline_bounded":
            "PR9_2_STAGING_FENCE_PERSISTENCE_DEADLINE_NOT_PROVEN",
        "staging_file_selection_deadline_bounded":
            "PR9_2_STAGING_FILE_SELECTION_DEADLINE_NOT_PROVEN",
        "staging_post_selection_cleanup_deadline_bounded":
            "PR9_2_STAGING_POST_SELECTION_CLEANUP_DEADLINE_NOT_PROVEN",
        "late_staging_debugger_attach_auto_detached":
            "PR9_2_LATE_STAGING_DEBUGGER_ATTACH_DETACH_NOT_PROVEN",
        "late_file_selection_fails_closed_behind_durable_fence":
            "PR9_2_LATE_FILE_SELECTION_FENCE_NOT_PROVEN",
        "post_selection_cleanup_best_effort_after_timeout":
            "PR9_2_POST_SELECTION_CLEANUP_FALLBACK_NOT_PROVEN",
    }
    for key, error in required.items():
        if support.get(key) is not True:
            raise RuntimeError(error)
