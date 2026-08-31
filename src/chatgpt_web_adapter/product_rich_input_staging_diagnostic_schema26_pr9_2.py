from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from .product_rich_input_live_gate_schema26_pr9_2 import ProductRichInputSchema26LiveProvider


def run_diagnostic(*, timeout: float = 45.0) -> dict[str, object]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema26LiveProvider()
    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema26-stage-probe-") as temp_dir:
        image_path, _, _ = _v7._write_fixtures(Path(temp_dir))
        request_id = str(uuid.uuid4())
        response = provider._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "diagnosePr92StagedAttachmentEvidence": True,
                "attachmentPaths": [str(image_path)],
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )

    if response.get("request_id") != request_id:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_RESPONSE_MISMATCH")
    if response.get("ok") is not True:
        raise RuntimeError(
            f"PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_FAILED:{response.get('error') or 'unknown'}"
        )
    if response.get("diagnosticOnly") is not True or response.get("stagingOnly") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_MODE_NOT_PROVEN")
    if response.get("fileUploadPerformed") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_UPLOAD_NOT_PROVEN")
    if response.get("writePerformed") is not False or response.get("conversationWritePerformed") is not False:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_WRITE_STATE_INVALID")
    if response.get("textInsertionPerformed") is not False:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_TEXT_STATE_INVALID")
    if response.get("protectedSubmitAttempted") is not False:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_SUBMIT_STATE_INVALID")
    if response.get("richInputSchemaVersion") != 26:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_SCHEMA_MISMATCH")
    if response.get("attachmentCount") != 1:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_ATTACHMENT_COUNT_MISMATCH")

    evidence = response.get("pageOwnedEvidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_EVIDENCE_MISSING")
    if evidence.get("ready") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_READY_NOT_PROVEN")
    if evidence.get("exactAttachmentSet") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_EXACT_SET_NOT_PROVEN")
    if evidence.get("crossEvidenceChannelExact") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_CROSS_CHANNEL_NOT_PROVEN")
    if evidence.get("indexedRemovalUiPrefixRequiresIndependentFilenameGroup") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_CORROBORATION_NOT_PROVEN")

    normalization = response.get("schema26RemovalNormalizationProof")
    if not isinstance(normalization, dict) or normalization.get("singleAttachmentCrossChannelExact") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_NORMALIZATION_NOT_PROVEN")
    if response.get("cleanupProven") is not True or response.get("durableFenceCleared") is not True:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_CLEANUP_NOT_PROVEN")
    if response.get("automaticWriteRetry") is not False or response.get("fallbackTransport") is not None:
        raise RuntimeError("PR9_2_SCHEMA26_STAGING_DIAGNOSTIC_FALLBACK_STATE_INVALID")

    return {
        "ok": True,
        "diagnostic_only": True,
        "staging_only": True,
        "file_upload_performed": True,
        "conversation_write_performed": False,
        "text_insertion_performed": False,
        "protected_submit_attempted": False,
        "schema": 26,
        "tab_id": response.get("tabId"),
        "expected_basenames": response.get("expectedBasenames"),
        "page_owned_evidence": evidence,
        "raw_evidence": response.get("rawEvidence"),
        "schema26_removal_normalization_proof": normalization,
        "cleanup_proven": True,
        "durable_fence_cleared": True,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 schema-26 staging-only attachment-evidence diagnostic; uploads one fixture but performs no conversation write"
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    report = run_diagnostic(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
