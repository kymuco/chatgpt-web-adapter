"""Final-review transport binding contract (deterministic fixture proof).

A final-review verdict may only ride a transport submission whose canonical
request identity binds EXACTLY to the review target. Issue #169 identity v3 is
the immutable 7-tuple:

    requestId + repository + issueNumber + headSha
               + reviewAttemptId + conversationId + promptHash

(pullRequestNumber and evidenceDigest remain bound in the canonical payload;
the requestId is the sha256 of the whole canonical payload, so the 7-tuple is
transitively pinned). Every mismatch fails closed with a stable ``:CODE``
error before any write and after any response. No retry, no inference, no
fallback, no partial delivery.

IMMUTABILITY INVARIANT (Issue #169, locked): the canonical request identity is
frozen at PREPARED and never recomputed through terminal/reconciliation. The
identity ``conversationId`` is the PRE-SUBMIT expected conversation identity,
or the canonical ``NO_PREASSIGNED_CONVERSATION`` sentinel when no conversation
exists yet. A runtime/server-assigned conversationId or turnExchangeId
observed after the write is CORRELATED EVIDENCE bound onto the immutable
requestId - it never replaces the request identity.

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
IDENTITY_SCHEMA_VERSION = 3
# Canonical sentinel for a request that has no pre-submit expected
# conversation. Post-write observed conversation ids are correlated EVIDENCE
# on the journal, never a reason to recompute the request identity.
NO_PREASSIGNED_CONVERSATION = "NO_PREASSIGNED_CONVERSATION"
_ERROR_PREFIX = "FINAL_REVIEW_BINDING_REJECTED"
_HEX_DIGITS = frozenset("0123456789abcdef")
# Sentinel for review-REQUEST bindings (no verdict exists yet at bind time);
# the canonical payload simply omits the verdict field.
_NO_VERDICT = object()


class FinalReviewBindingError(Exception):
    """Fail-closed binding rejection carrying a stable ``:CODE`` message.

    On REPLAY the already-bound ``canonical_request_id`` is attached so every
    continuation resolves the durable journal through the IMMUTABLE identity
    instead of recomputing it from possibly drifted inputs.
    """

    canonical_request_id: str | None = None


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


def prompt_identity_hash(text: str) -> str:
    """promptHash component of the identity v3 7-tuple: sha256 over the exact
    UTF-8 request text committed to the composer (the durable journal copy),
    never over a post-composer round-trip."""
    if not isinstance(text, str):
        raise FinalReviewBindingError(_code("FIELD_MALFORMED:promptHash"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_expected_conversation(value: Any) -> str:
    if value is None:
        return NO_PREASSIGNED_CONVERSATION
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FinalReviewBindingError(_code("FIELD_MALFORMED:conversationId"))
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
    review_attempt_id: Any = "1",
    expected_conversation_id: Any = None,
    prompt_sha256: Any = None,
) -> dict[str, Any]:
    """Validate + bind one final-review request; returns the binding evidence.

    ``verdict`` may be omitted for review-REQUEST bindings (the verdict only
    exists after the reply); the canonical payload then has no verdict field.
    ``review_attempt_id``/``expected_conversation_id``/``prompt_sha256`` carry
    the identity v3 fields; the expected conversation defaults to the
    canonical ``NO_PREASSIGNED_CONVERSATION`` sentinel.
    Fail-closed order: field shape -> target mismatch -> stale headSha ->
    malformed verdict -> replay.
    """
    _require_text(repository, "FIELD_MALFORMED:repository")
    _require_positive_int(issue_number, "FIELD_MALFORMED:issueNumber")
    _require_positive_int(pull_request_number, "FIELD_MALFORMED:pullRequestNumber")
    _require_hex(head_sha, (40, 64), "FIELD_MALFORMED:headSha")
    _require_hex(evidence_digest, (64,), "FIELD_MALFORMED:evidenceDigest")
    _require_text(review_attempt_id, "FIELD_MALFORMED:reviewAttemptId")
    expected_conversation = _normalize_expected_conversation(expected_conversation_id)
    if prompt_sha256 is not None:
        _require_hex(prompt_sha256, (64,), "FIELD_MALFORMED:promptHash")

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
        "reviewAttemptId": review_attempt_id,
        "conversationId": expected_conversation,
    }
    if prompt_sha256 is None and verdict is not _NO_VERDICT:
        # Verdict mode has no free prompt: promptHash pins the canonical
        # verdict payload itself (sha256 over the identity core + verdict).
        prompt_sha256 = hashlib.sha256(
            json.dumps(
                {**payload, "verdict": verdict},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
    if prompt_sha256 is None:
        raise FinalReviewBindingError(_code("FIELD_MALFORMED:promptHash"))
    payload["promptHash"] = prompt_sha256
    if verdict is not _NO_VERDICT:
        payload["verdict"] = verdict
    canonical_request_id = canonical_request_identity(payload)
    if canonical_request_id in known_request_ids:
        error = FinalReviewBindingError(_code("REPLAY"))
        # Continuation must resolve the durable journal through the bound
        # identity carried on the error - never by recomputing identity from
        # inputs that may have drifted since PREPARED.
        error.canonical_request_id = canonical_request_id
        raise error

    return {
        "identitySchema": IDENTITY_SCHEMA_VERSION,
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
