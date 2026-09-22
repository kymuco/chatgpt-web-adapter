from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import subprocess
import time
from typing import Any, Callable

from chatgpt_web_adapter import ChatGPTWebClient

if __package__:
    from .pr13_1_conversation_files_identity_probe import probe_conversation_files
    from .pr13_1_conversation_files_live_gate import conversation_id_from_selector
    from .pr13_1_conversation_files_stability_gate import _target_record
    from .pr13_3_artifact_bytes_integrity_probe import (
        _extract_resolution_locator,
        _resolver_payload,
        characterize_integrity,
        probe_locator_bytes,
    )
else:
    from pr13_1_conversation_files_identity_probe import probe_conversation_files
    from pr13_1_conversation_files_live_gate import conversation_id_from_selector
    from pr13_1_conversation_files_stability_gate import _target_record
    from pr13_3_artifact_bytes_integrity_probe import (
        _extract_resolution_locator,
        _resolver_payload,
        characterize_integrity,
        probe_locator_bytes,
    )

PROMOTION_SCHEMA = "CWA_PR13_4_LONGITUDINAL_ARTIFACT_IDENTITY_PROMOTION_GATE_V1"
BASELINE_EVIDENCE_COMMIT = "eebd48cef2896a285331896741e3ba0225e5cc5f"
MIN_LONGITUDINAL_AGE_SECONDS = 4 * 60 * 60
EXPECTED_FILENAME = "cwa_pr13_1_identity_probe.txt"
EXPECTED_SIZE_BYTES = 45
EXPECTED_ARTIFACT_SHA256 = (
    "d0bb354d72fad3715f5348740d75dd644435165f68034f54f7974c834cbe9f1d"
)


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError("BASELINE_IDENTITY_FINGERPRINT_REQUIRED")
    return normalized


def _identity_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _baseline_commit_age_seconds(*, head: str, now_epoch: float | None = None) -> int:
    merge_base = _git_output("merge-base", BASELINE_EVIDENCE_COMMIT, head)
    if merge_base != BASELINE_EVIDENCE_COMMIT:
        raise RuntimeError("BASELINE_EVIDENCE_COMMIT_NOT_ANCESTOR")
    observed_not_later_than = int(
        _git_output("show", "-s", "--format=%ct", BASELINE_EVIDENCE_COMMIT)
    )
    now = time.time() if now_epoch is None else now_epoch
    age = int(now - observed_not_later_than)
    if age < 0:
        raise RuntimeError("BASELINE_EVIDENCE_COMMIT_IN_FUTURE")
    return age


def _new_client(timeout: float) -> ChatGPTWebClient:
    return ChatGPTWebClient(
        auto_login=False,
        auto_sentinel=False,
        timeout=timeout,
    )


def _base_report(
    *,
    head: str,
    expected_head: str,
    tracked_clean: bool,
    baseline_age_seconds: int | None,
) -> dict[str, Any]:
    age_met = (
        baseline_age_seconds is not None
        and baseline_age_seconds >= MIN_LONGITUDINAL_AGE_SECONDS
    )
    return {
        "schema": PROMOTION_SCHEMA,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head == expected_head,
        "tracked_clean": tracked_clean,
        "baseline_evidence_commit": BASELINE_EVIDENCE_COMMIT,
        "baseline_age_seconds": baseline_age_seconds,
        "minimum_longitudinal_age_seconds": MIN_LONGITUDINAL_AGE_SECONDS,
        "baseline_age_requirement_met": age_met,
        "expected_filename": EXPECTED_FILENAME,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_artifact_sha256": EXPECTED_ARTIFACT_SHA256,
        "request_count": 0,
        "fresh_client_count": 0,
        "identity_discovery_request_count": 0,
        "resolution_request_count": 0,
        "locator_fetch_request_count": 0,
        "target_record_present": False,
        "identity_key": None,
        "baseline_identity_fingerprint_exported": False,
        "observed_identity_fingerprint_exported": False,
        "identity_values_exported": False,
        "locator_values_exported": False,
        "artifact_bytes_exported": False,
        "response_body_exported": False,
        "identity_fingerprint_matches": False,
        "longitudinal_identity_stability_proven": False,
        "stable_product_identity_proven": False,
        "indefinite_identity_stability_proven": False,
        "artifact_bytes_proven": False,
        "artifact_integrity_proven": False,
        "identity_bound_byte_retrieval_proven": False,
        "download_authority_granted": False,
        "production_handoff_promoted": False,
        "artifact_disk_write_attempted": False,
        "materialization_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
    }


def run_promotion_gate(
    *,
    conversation_id: str,
    baseline_identity_fingerprint: str,
    expected_head: str,
    timeout: float,
    client_factory: Callable[[float], Any] = _new_client,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    baseline_fingerprint = _normalize_sha256(baseline_identity_fingerprint)

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _git_output("status", "--porcelain", "--untracked-files=no") == ""
    try:
        baseline_age = _baseline_commit_age_seconds(head=head, now_epoch=now_epoch)
    except Exception as exc:
        report = _base_report(
            head=head,
            expected_head=expected_head,
            tracked_clean=tracked_clean,
            baseline_age_seconds=None,
        )
        report.update(
            {
                "characterization": "BASELINE_EVIDENCE_TIME_GATE_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report = _base_report(
        head=head,
        expected_head=expected_head,
        tracked_clean=tracked_clean,
        baseline_age_seconds=baseline_age,
    )
    if head != expected_head or not tracked_clean:
        report["characterization"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report
    if baseline_age < MIN_LONGITUDINAL_AGE_SECONDS:
        report["characterization"] = "LONGITUDINAL_INTERVAL_NOT_YET_PROVEN"
        return report

    client = client_factory(timeout)
    report["fresh_client_count"] = 1
    try:
        discovery = probe_conversation_files(client, conversation_id)
    except Exception as exc:
        report.update(
            {
                "request_count": 1,
                "identity_discovery_request_count": 1,
                "characterization": "IDENTITY_DISCOVERY_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["request_count"] = 1
    report["identity_discovery_request_count"] = 1
    report["identity_discovery_characterization"] = discovery.get("characterization")
    target = _target_record(discovery, EXPECTED_FILENAME)
    if target is None:
        report["characterization"] = "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN"
        return report

    file_id = target["explicit_identity"]
    identity_key = target["explicit_identity_key"]
    report["target_record_present"] = True
    report["identity_key"] = identity_key
    if identity_key != "file_id":
        report["characterization"] = "PRODUCT_IDENTITY_KEY_CHANGED"
        return report

    current_fingerprint = _identity_fingerprint(file_id)
    fingerprint_matches = hmac.compare_digest(current_fingerprint, baseline_fingerprint)
    report["identity_fingerprint_matches"] = fingerprint_matches
    if not fingerprint_matches:
        report["characterization"] = "LONGITUDINAL_IDENTITY_FINGERPRINT_MISMATCH"
        return report

    try:
        resolution_status, resolution_payload = _resolver_payload(
            client,
            conversation_id=conversation_id,
            file_id=file_id,
        )
    except Exception as exc:
        report.update(
            {
                "request_count": 2,
                "resolution_request_count": 1,
                "characterization": "LONGITUDINAL_RESOLUTION_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["request_count"] = 2
    report["resolution_request_count"] = 1
    report["resolution_status_code"] = resolution_status
    if not 200 <= resolution_status < 300:
        report["characterization"] = "LONGITUDINAL_RESOLUTION_NOT_PROVEN"
        return report

    locator_key, locator = _extract_resolution_locator(resolution_payload)
    report["resolution_locator_field_present"] = locator is not None
    report["resolution_locator_key"] = locator_key
    if locator is None:
        report["characterization"] = "LONGITUDINAL_RESOLUTION_NOT_PROVEN"
        return report

    try:
        byte_report = probe_locator_bytes(
            client,
            conversation_id=conversation_id,
            locator=locator,
        )
    except Exception as exc:
        report.update(
            {
                "request_count": 3,
                "locator_fetch_request_count": 1,
                "download_attempted": True,
                "characterization": "LONGITUDINAL_LOCATOR_FETCH_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["locator_origin_class"] = byte_report.get("locator_origin_class")
    if byte_report.get("request_count") != 1:
        report["characterization"] = byte_report.get(
            "characterization",
            "LONGITUDINAL_LOCATOR_FETCH_NOT_PROVEN",
        )
        return report

    integrity = characterize_integrity(
        byte_report,
        expected_size=EXPECTED_SIZE_BYTES,
        expected_sha256=EXPECTED_ARTIFACT_SHA256,
    )
    integrity_proven = integrity.get("artifact_integrity_proven") is True
    report.update(
        {
            "request_count": 3,
            "locator_fetch_request_count": 1,
            "locator_fetch_status_code": integrity.get("locator_fetch_status_code"),
            "locator_origin_class": integrity.get("locator_origin_class"),
            "observed_size_bytes": integrity.get("observed_size_bytes"),
            "observed_artifact_sha256": integrity.get("observed_sha256"),
            "size_matches": integrity.get("size_matches"),
            "sha256_matches": integrity.get("sha256_matches"),
            "artifact_bytes_proven": integrity.get("artifact_bytes_proven") is True,
            "artifact_integrity_proven": integrity_proven,
            "identity_bound_byte_retrieval_proven": integrity.get(
                "identity_bound_byte_retrieval_proven"
            )
            is True,
            "download_attempted": True,
        }
    )
    if not integrity_proven:
        report["characterization"] = "LONGITUDINAL_ARTIFACT_INTEGRITY_NOT_PROVEN"
        return report

    report.update(
        {
            "longitudinal_identity_stability_proven": True,
            "stable_product_identity_proven": True,
            "stability_scope": "KNOWN_GENERATED_ARTIFACT_ACROSS_AT_LEAST_4H",
            "characterization": "LONGITUDINAL_ARTIFACT_IDENTITY_PROMOTION_PROVEN",
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the current generated-artifact file_id against the private "
            "PR13.1 R2 fingerprint after a fixed longitudinal interval, then prove "
            "that the same identity still resolves to the exact expected bytes."
        )
    )
    parser.add_argument(
        "--conversation",
        required=True,
        help="Raw conversation id or https://chatgpt.com/.../c/<conversation-id> URL.",
    )
    parser.add_argument(
        "--baseline-identity-fingerprint",
        required=True,
        help=(
            "The first_identity_fingerprint from the authenticated PR13.1 R2 output. "
            "It is consumed privately and never emitted in the report."
        ),
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    try:
        conversation_id = conversation_id_from_selector(args.conversation)
        report = run_promotion_gate(
            conversation_id=conversation_id,
            baseline_identity_fingerprint=args.baseline_identity_fingerprint,
            expected_head=args.expected_head,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    completed = {
        "LONGITUDINAL_ARTIFACT_IDENTITY_PROMOTION_PROVEN",
        "LONGITUDINAL_INTERVAL_NOT_YET_PROVEN",
        "LONGITUDINAL_IDENTITY_FINGERPRINT_MISMATCH",
        "PRODUCT_IDENTITY_KEY_CHANGED",
        "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN",
        "LONGITUDINAL_RESOLUTION_NOT_PROVEN",
        "LONGITUDINAL_ARTIFACT_INTEGRITY_NOT_PROVEN",
        "LOCATOR_ORIGIN_REJECTED",
        "LOCATOR_REDIRECT_NOT_FOLLOWED",
        "LOCATOR_BYTE_FETCH_HTTP_ERROR",
    }
    return 0 if report.get("characterization") in completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
