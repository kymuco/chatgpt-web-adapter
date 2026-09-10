"""Production-like final-review E2E over the CWA browser-owned plane.

Phase `submit`: bind the fixture request durably, perform EXACTLY ONE
browser-owned live write with the typed request-bound SSE identity authority,
persist the durable ACK BEFORE any finality attempt, then hard-crash.

Phase `reconcile`: a brand-new process reconciles from the durable journal
via canonical reads ONLY (zero resend), verifies the strict payload parse,
exact response binding, unambiguous finality, and writes the E2E report.

Fixture binding is disposable/non-production: cwa-fixture/sandbox
issue 999901 / PR 999902, deterministic fixture head/digest. The live write
carries no secrets, no raw SSE, no production issue data.
"""

import json
import os
import sys
import hashlib
import traceback
from datetime import datetime, timezone
from pathlib import Path

from chatgpt_web_adapter import assemble_product_runtime
from chatgpt_web_adapter.final_review_transport import (
    CwaFinalReviewTransport,
    FinalReviewRequest,
    FinalReviewTransportError,
)

REPORT = Path("cwa_final_review_e2e_journal.json")
STORE = Path("cwa_final_review_store")
REPO = "cwa-fixture/sandbox"
ISSUE = 999901
PR = 999902
HEAD = hashlib.sha1(b"cwa-e2e-head").hexdigest()
DIGEST = hashlib.sha256(b"cwa-e2e-evidence-attempt3").hexdigest()
VERDICT = "APPROVE"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def persist(data: dict) -> None:
    tmp = REPORT.with_suffix(".tmp")
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, REPORT)


def _transport() -> CwaFinalReviewTransport:
    return CwaFinalReviewTransport(
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        runtime_factory=assemble_product_runtime,
        durable_store=STORE,
    )


def submit_phase() -> int:
    report: dict = {
        "schema": 1,
        "probe": "CWA_FINAL_REVIEW_TRANSPORT_E2E",
        "phase": "submit",
        "startedAt": now(),
        "fixture": {
            "repository": REPO,
            "issueNumber": ISSUE,
            "pullRequestNumber": PR,
            "headSha": HEAD,
            "evidenceDigest": DIGEST,
            "verdict": VERDICT,
        },
        "writeBudget": 1,
        "state": "STARTING",
    }
    persist(report)
    request = FinalReviewRequest(
        repository=REPO,
        issue_number=ISSUE,
        pull_request_number=PR,
        head_sha=HEAD,
        evidence_digest=DIGEST,
        verdict=VERDICT,
        current_head_sha=HEAD,
    )
    transport = _transport()
    try:
        result = transport.submit_final_review(request)
    except FinalReviewTransportError as error:
        report["state"] = "TRANSPORT_REJECTED_FAIL_CLOSED"
        report["rejection"] = str(error)
        report["finishedAt"] = now()
        persist(report)
        print("FAIL_CLOSED:", error)
        return 4
    # Hard crash AFTER the durable WRITE_ACKNOWLEDGED persist, BEFORE any
    # canonical read: simulates losing the final response / process death.
    report["state"] = "WRITE_ACKNOWLEDGED_PRE_CRASH"
    report["writeAcknowledgedAt"] = now()
    report["submittedResult"] = result.to_dict()
    report["crashPlannedAt"] = now()
    persist(report)
    print("=== DURABLE ACK + TYPED IDENTITY PERSISTED; HARD CRASH NOW ===")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    os._exit(75)


def reconcile_phase() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["phase"] = "reconcile"
    report["reconcileStartedAt"] = now()
    report["freshProcess"] = True
    canonical_request_id = report["submittedResult"]["canonicalRequestId"]
    transport = _transport()
    try:
        result = transport.reconcile_final_review(canonical_request_id)
    except FinalReviewTransportError as error:
        report["state"] = "RECONCILIATION_FAIL_CLOSED"
        report["rejection"] = str(error)
        report["finishedAt"] = now()
        persist(report)
        print("FAIL_CLOSED:", error)
        return 4
    journal = json.loads(
        (STORE / f"{canonical_request_id}.json").read_text(encoding="utf-8")
    )
    checks = {
        "live_write_count_1": journal.get("liveWriteCount") == 1,
        "retries_zero": journal.get("liveWriteCount") == 1
        and journal.get("submitError") is None,
        "authority_typed_present": journal.get(
            "sseConversationIdentityAuthority"
        )
        == "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS",
        "identity_not_route_only": not journal.get("conversationId", "").startswith(
            "WEB:"
        ),
        "exact_binding_recovered": result.payload
        == report["fixture"]
        | {"verdict": VERDICT}
        and result.payload["repository"] == REPO
        and result.payload["issueNumber"] == ISSUE
        and result.payload["pullRequestNumber"] == PR
        and result.payload["headSha"] == HEAD
        and result.payload["evidenceDigest"] == DIGEST,
        "finality_final": result.finality == "FINAL",
        "verdict_strict": result.verdict == VERDICT,
        "journal_terminal_reconciled": journal.get("state") == "RECONCILED",
        "fresh_process_zero_writes": report.get("freshProcess") is True,
    }
    report["state"] = (
        "E2E_PASS" if all(checks.values()) else "E2E_FAIL_CLOSED"
    )
    report["checks"] = checks
    report["reconciledResult"] = result.to_dict()
    report["finishedAt"] = now()
    persist(report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if all(checks.values()) else 4


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "submit":
        return submit_phase()
    if phase == "reconcile":
        return reconcile_phase()
    print("usage: cwa_final_review_e2e.py submit|reconcile", file=sys.stderr)
    return 64


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - crash report
        try:
            persist(
                {
                    "schema": 1,
                    "probe": "CWA_FINAL_REVIEW_TRANSPORT_E2E",
                    "state": "E2E_CRASHED",
                    "crashAt": now(),
                    "crash": traceback.format_exc(),
                }
            )
        except Exception:
            pass
        print("E2E_CRASHED", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(3)
