from __future__ import annotations

import argparse
import json
import uuid

from .product_rich_input_live_gate_schema28_pr9_2 import ProductRichInputSchema28LiveProvider


def run_diagnostic(*, timeout: float = 30.0) -> dict[str, object]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema28LiveProvider()
    request_id = str(uuid.uuid4())
    response = provider._rpc(
        {
            "type": "turn",
            "request_id": request_id,
            "diagnosePr92CommittedIdentityStateSchema28": True,
            "timeoutMs": int(timeout * 1000),
        },
        timeout=timeout,
    )

    if response.get("request_id") != request_id:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_RESPONSE_MISMATCH")
    if response.get("ok") is not True:
        raise RuntimeError(
            "PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_FAILED:"
            f"{response.get('error') or 'unknown'}"
        )
    if response.get("diagnosticOnly") is not True or response.get("reconciliationOnly") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_MODE_NOT_PROVEN")
    if response.get("writePerformed") is not False or response.get("conversationWritePerformed") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_WRITE_STATE_INVALID")
    if response.get("attachmentStagingPerformed") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_STAGING_STATE_INVALID")
    if response.get("textInsertionPerformed") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_TEXT_STATE_INVALID")
    if response.get("protectedSubmitAttempted") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_SUBMIT_STATE_INVALID")
    if response.get("richInputSchemaVersion") != 28:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_SCHEMA_MISMATCH")
    if response.get("cleanupProven") is not True or response.get("durableFenceCleared") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_CLEANUP_NOT_PROVEN")
    if response.get("staleComposerReconciled") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_STALE_COMPOSER_NOT_RECONCILED")
    if response.get("routeConversationIdentityAuthoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_ROUTE_AUTHORITY_INVALID")
    if response.get("automaticWriteRetry") is not False or response.get("fallbackTransport") is not None:
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_FALLBACK_STATE_INVALID")

    fence_before = response.get("durableFencePresentBefore") is True
    cleanup_proof_authority = response.get("cleanupProofAuthority")
    fenced_tab_absent = response.get("fencedTabAbsentAfterCleanup")
    fence_absence_authority = response.get("fencedTabAbsenceAuthority")

    if fenced_tab_absent not in (True, False, None):
        raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_TAB_PRESENCE_STATE_INVALID")

    if fence_before:
        if response.get("cleanupAttempted") is not True:
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_CLEANUP_NOT_ATTEMPTED")
        if cleanup_proof_authority != "PRODUCTION_REQUIRE_CLEAN_ATTACHMENT_STATE":
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_CLEANUP_AUTHORITY_INVALID")
        if fenced_tab_absent is True:
            if fence_absence_authority != "POST_CLEANUP_TAB_ABSENCE_PROBE":
                raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_ABSENCE_AUTHORITY_INVALID")
        elif fenced_tab_absent is False:
            if fence_absence_authority != "POST_CLEANUP_TAB_PRESENCE_PROBE":
                raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_PRESENCE_AUTHORITY_INVALID")
        elif fence_absence_authority is not None:
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_UNKNOWN_TAB_AUTHORITY_INVALID")
    else:
        if response.get("cleanupAttempted") is not False:
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_UNEXPECTED_CLEANUP")
        if cleanup_proof_authority is not None:
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_UNEXPECTED_CLEANUP_AUTHORITY")
        if fenced_tab_absent is not None or fence_absence_authority is not None:
            raise RuntimeError("PR9_2_SCHEMA28_COMMITTED_IDENTITY_DIAGNOSTIC_UNEXPECTED_TAB_PROOF")

    return {
        "ok": True,
        "diagnostic_only": True,
        "reconciliation_only": True,
        "write_performed": False,
        "conversation_write_performed": False,
        "attachment_staging_performed": False,
        "text_insertion_performed": False,
        "protected_submit_attempted": False,
        "schema": 28,
        "durable_fence_present_before": fence_before,
        "cleanup_attempted": response.get("cleanupAttempted"),
        "cleanup_proven": True,
        "stale_composer_reconciled": True,
        "cleanup_proof_authority": cleanup_proof_authority,
        "durable_fence_cleared": True,
        "fenced_tab_absent_after_cleanup": fenced_tab_absent,
        "fenced_tab_absence_authority": fence_absence_authority,
        "observed_tab_state_before_cleanup": response.get("observedTabStateBeforeCleanup"),
        "observed_tab_id_before_cleanup": response.get("observedTabIdBeforeCleanup"),
        "observed_route_conversation_id_diagnostic": response.get(
            "observedRouteConversationIdDiagnostic"
        ),
        "observed_url_before_cleanup": response.get("observedUrlBeforeCleanup"),
        "route_sample_skipped_for_cleanup_reserve": response.get(
            "routeSampleSkippedForCleanupReserve"
        ),
        "observed_tab_state_after_cleanup": response.get("observedTabStateAfterCleanup"),
        "route_conversation_identity_authoritative": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR9.2 schema-28 committed-write identity/fence reconciliation diagnostic; "
            "performs no conversation write"
        )
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    report = run_diagnostic(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
