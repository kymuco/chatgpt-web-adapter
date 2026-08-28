from __future__ import annotations

import argparse
import json
import uuid

from .product_rich_input_live_gate_schema23_pr9_2 import ProductRichInputSchema23LiveProvider


def run_diagnostic(*, timeout: float = 10.0) -> dict[str, object]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema23LiveProvider()
    request_id = str(uuid.uuid4())
    response = provider._rpc(
        {
            "type": "turn",
            "request_id": request_id,
            "diagnosePr92ComposerEvidence": True,
            "timeoutMs": int(timeout * 1000),
        },
        timeout=timeout,
    )
    if response.get("request_id") != request_id:
        raise RuntimeError("PR9_2_COMPOSER_DIAGNOSTIC_RESPONSE_MISMATCH")
    if response.get("ok") is not True:
        raise RuntimeError(
            f"PR9_2_COMPOSER_DIAGNOSTIC_FAILED:{response.get('error') or 'unknown'}"
        )
    if response.get("diagnosticOnly") is not True:
        raise RuntimeError("PR9_2_COMPOSER_DIAGNOSTIC_ONLY_NOT_PROVEN")
    if response.get("writePerformed") is not False:
        raise RuntimeError("PR9_2_COMPOSER_DIAGNOSTIC_WRITE_STATE_INVALID")
    if response.get("attachmentStagingPerformed") is not False:
        raise RuntimeError("PR9_2_COMPOSER_DIAGNOSTIC_STAGING_STATE_INVALID")
    if response.get("protectedSubmitAttempted") is not False:
        raise RuntimeError("PR9_2_COMPOSER_DIAGNOSTIC_SUBMIT_STATE_INVALID")

    return {
        "ok": True,
        "diagnostic_only": True,
        "write_performed": False,
        "attachment_staging_performed": False,
        "protected_submit_attempted": False,
        "schema": response.get("richInputSchemaVersion"),
        "tab_id": response.get("tabId"),
        "production_clean_proof": response.get("productionCleanProof"),
        "evidence": response.get("evidence"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 zero-write official-composer attachment-evidence diagnostic"
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    report = run_diagnostic(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
