"""Final-review transport binding contract (deterministic fixture proof).

A final-review verdict may only ride a transport submission whose canonical
request identity binds EXACTLY to the review target (repository, issueNumber,
pullRequestNumber, headSha, evidence digest). Every mismatch fails closed
with a stable ``:CODE`` error before any write and after any response. No
retry, no inference, no fallback, no partial delivery.

``ponytail:`` ceiling — this is the deterministic contract fixture for the CWA
final-review gate; a production ``FinalReviewTransport`` adopts it by calling
``bind_final_review_request`` pre-write (with a durably persisted replay set)
and ``verify_final_review_response`` post-write.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Collection

FINAL_REVIEW_VERDICTS = frozenset({"APPROVE", "REQUEST_CHANGES", "BLOCK"})
FINAL_REVIEW_FINALITY_STATES = frozenset({"FINAL"})
_ERROR_PREFIX = "FINAL_REVIEW_BINDING_REJECTED"
_HEX_DIGITS = frozenset("0123456789abcdef")
# Sentinel for review-REQUEST bindings (no verdict exists yet at bind time);
# the canonical payload simply omits the verdict field.
_NO_VERDICT = object()


class FinalReviewBindingError(Exception):
    """Fail-closed binding rejection carrying a stable ``:CODE`` message."""


def _code(reason: str) -> str:
    return f"{_ERROR_PREFIX}:{reason}"


def _require_hex(value: Any, lengths: tuple[int, ...], reason: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) not in lengths
        or any(char not in _HEX_DIGITS for char in value)
    ):
        raise FinalReviewBindingError(_code(reason))
    return value


def _require_text(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FinalReviewBindingError(_code(reason))
    return value


def _require_positive_int(value: Any, reason: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise FinalReviewBindingError(_code(reason))
    return value


def bind_final_review_request(
    repository: Any,
    issue_number: Any,
    pull_request_number: Any,
    head_sha: Any,
    evidence_digest: Any,
    verdict: Any = _NO_VERDICT,
    *,
    expected_repository: str,
    expected_issue_number: int,
    expected_pull_request_number: int,
    current_head_sha: str,
    known_request_ids: Collection[str],
) -> dict[str, Any]:
    """Validate + bind one final-review request; returns the binding evidence.

    ``verdict`` may be omitted for review-REQUEST bindings (the verdict only
    exists after the reply); the canonical payload then has no verdict field.
    Fail-closed order: field shape -> target mismatch -> stale headSha ->
    malformed verdict -> replay.
    """
    _require_text(repository, "FIELD_MALFORMED:repository")
    _require_positive_int(issue_number, "FIELD_MALFORMED:issueNumber")
    _require_positive_int(pull_request_number, "FIELD_MALFORMED:pullRequestNumber")
    _require_hex(head_sha, (40, 64), "FIELD_MALFORMED:headSha")
    _require_hex(evidence_digest, (64,), "FIELD_MALFORMED:evidenceDigest")

    if (
        repository != expected_repository
        or issue_number != expected_issue_number
        or pull_request_number != expected_pull_request_number
    ):
        raise FinalReviewBindingError(_code("TARGET_MISMATCH"))

    if head_sha != _require_hex(
        current_head_sha, (40, 64), "FIELD_MALFORMED:currentHeadSha"
    ):
        raise FinalReviewBindingError(_code("HEAD_SHA_STALE"))

    if verdict is not _NO_VERDICT and verdict not in FINAL_REVIEW_VERDICTS:
        raise FinalReviewBindingError(_code("VERDICT_MALFORMED"))

    payload = {
        "repository": repository,
        "issueNumber": issue_number,
        "pullRequestNumber": pull_request_number,
        "headSha": head_sha,
        "evidenceDigest": evidence_digest,
    }
    if verdict is not _NO_VERDICT:
        payload["verdict"] = verdict
    canonical_request_id = canonical_request_identity(payload)
    if canonical_request_id in known_request_ids:
        raise FinalReviewBindingError(_code("REPLAY"))

    return {
        "canonicalRequestId": canonical_request_id,
        "canonicalPayload": payload,
    }


def canonical_request_identity(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_final_review_response(
    binding: dict[str, Any],
    *,
    response_digest: Any,
    finality: Any,
) -> dict[str, Any]:
    """Post-write verification; the response must echo the bound identity and
    carry unambiguous finality. Any mismatch fails closed after delivery and
    must be surfaced, never repaired silently."""
    _require_hex(response_digest, (64,), "RESPONSE_MISMATCH")
    if response_digest != binding.get("canonicalRequestId"):
        raise FinalReviewBindingError(_code("RESPONSE_MISMATCH"))
    if finality not in FINAL_REVIEW_FINALITY_STATES:
        raise FinalReviewBindingError(_code("FINALITY_AMBIGUOUS"))
    return {"verified": True, "canonicalRequestId": response_digest}
