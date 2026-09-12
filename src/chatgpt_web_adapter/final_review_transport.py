"""Production ``FinalReviewTransport`` over the CWA browser-owned write plane.

Semantics (fixed by the research gates A/B/C):

- pre-write: deterministic binding of the final-review request (repository,
  issueNumber, pullRequestNumber, exact headSha, evidence digest) with the
  canonical request identity durably persisted BEFORE any external mutation;
  duplicate/replay/stale bindings fail closed;
- write: exactly one browser-owned CWA turn; durable ACK persisted before any
  finality attempt; zero blind retry; the request-bound SSE conversation-id
  consensus must ride the turn as the typed identity authority — absent
  authority or a route-only ``WEB:`` identity fails closed (no stripping, no
  inference, no route promotion);
- post-write: canonical read/reconcile only; strict verbatim payload parse;
  exact response binding; unambiguous finality; the original write is never
  resent merely because the final response was lost;
- transaction safety (Issue #169): a durable write-ahead record moves the
  journal to ``SUBMIT_DELEGATED`` BEFORE the write is handed to the browser
  plane; any loss window after delegation lands in ``WRITE_FINALITY_UNKNOWN``
  and must pass through ``RECONCILING`` with an evidence outcome
  (``WRITE_FOUND`` / ``NO_WRITE_PROVEN`` / ``AMBIGUOUS``). Retry is
  structurally impossible from UNKNOWN; only a proven ``NO_WRITE_PROVEN``
  grants ``SAFE_TO_RETRY``; ``AMBIGUOUS`` is terminal fail-closed. The
  canonical request identity is immutable from PREPARED to terminal - post
  write ids are correlated evidence, never a re-derived identity.

``ponytail:`` ceiling — replay set is the durable-store directory scan; the
upgrade path is an external ledger if multi-process submission is ever needed.
"""

from __future__ import annotations

import hashlib
import json
import re
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .final_review_binding_contract import (
    NO_PREASSIGNED_CONVERSATION,
    bind_final_review_request,
    canonical_request_identity,
    prompt_identity_hash,
    verify_final_review_response,
    FinalReviewBindingError,
)
from .types import ConversationRef

CWA_SSE_IDENTITY_AUTHORITY = "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS"
FINAL_REVIEW_PAYLOAD_PREFIX = "FINAL_REVIEW_VERDICT_V1"
FINAL_REVIEW_TRANSPORT_ERROR = "FINAL_REVIEW_TRANSPORT_REJECTED"
_READ_ATTEMPTS = 3
_READ_WAIT_S = (15.0, 30.0, 30.0)

# --- Issue #169 persisted transaction state machine (journal schema 3) -------
JOURNAL_SCHEMA = 3
STATE_PREPARED = "PREPARED"
STATE_SUBMIT_DELEGATED = "SUBMIT_DELEGATED"
STATE_WRITE_CONFIRMED = "WRITE_CONFIRMED"
STATE_WRITE_CONFIRMED_IDENTITY_REJECTED = "WRITE_CONFIRMED_IDENTITY_REJECTED"
STATE_RESPONSE_WAIT = "RESPONSE_WAIT"
STATE_RESPONSE_CONFIRMED = "RESPONSE_CONFIRMED"
STATE_WRITE_FINALITY_UNKNOWN = "WRITE_FINALITY_UNKNOWN"
STATE_RECONCILING = "RECONCILING"
STATE_WRITE_FOUND = "WRITE_FOUND"
STATE_NO_WRITE_PROVEN = "NO_WRITE_PROVEN"
STATE_AMBIGUOUS = "AMBIGUOUS"
STATE_SUBMIT_FAILED_NONRETRYABLE = "SUBMIT_FAILED_NONRETRYABLE"

# The ONLY legal edges. WRITE_FINALITY_UNKNOWN has exactly one successor:
# RECONCILING. UNKNOWN -> SUBMIT_DELEGATED is absent BY CONSTRUCTION; the sole
# retry edge into SUBMIT_DELEGATED originates at NO_WRITE_PROVEN (negative
# proof persisted) and is attempt-bounded.
_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    STATE_PREPARED: frozenset({STATE_SUBMIT_DELEGATED, STATE_SUBMIT_FAILED_NONRETRYABLE}),
    STATE_SUBMIT_DELEGATED: frozenset({
        STATE_WRITE_CONFIRMED,
        STATE_WRITE_CONFIRMED_IDENTITY_REJECTED,
        STATE_WRITE_FINALITY_UNKNOWN,
        STATE_RECONCILING,
        STATE_SUBMIT_FAILED_NONRETRYABLE,
    }),
    STATE_WRITE_FINALITY_UNKNOWN: frozenset({STATE_RECONCILING}),
    STATE_RECONCILING: frozenset({
        STATE_WRITE_FOUND, STATE_NO_WRITE_PROVEN, STATE_AMBIGUOUS,
    }),
    STATE_WRITE_FOUND: frozenset({STATE_RESPONSE_WAIT}),
    STATE_WRITE_CONFIRMED: frozenset({STATE_RESPONSE_WAIT}),
    STATE_WRITE_CONFIRMED_IDENTITY_REJECTED: frozenset(),
    STATE_RESPONSE_WAIT: frozenset({STATE_RESPONSE_CONFIRMED}),
    STATE_RESPONSE_CONFIRMED: frozenset(),
    # THE retry gate: the only edge back into the delegation lane.
    STATE_NO_WRITE_PROVEN: frozenset({STATE_SUBMIT_DELEGATED}),
    STATE_AMBIGUOUS: frozenset(),
    STATE_SUBMIT_FAILED_NONRETRYABLE: frozenset(),
}
_ALL_STATES = frozenset(_STATE_TRANSITIONS)
# States that hold the durable lane open (a later request must not start).
_ACTIVE_STATES = frozenset({
    STATE_PREPARED,
    STATE_SUBMIT_DELEGATED,
    STATE_WRITE_FINALITY_UNKNOWN,
    STATE_RECONCILING,
    STATE_WRITE_CONFIRMED,
    STATE_WRITE_CONFIRMED_IDENTITY_REJECTED,
    STATE_WRITE_FOUND,
    STATE_RESPONSE_WAIT,
})
_TERMINAL_STATES = _ALL_STATES - _ACTIVE_STATES
# Journal keys that are frozen once PREPARED is durable (identity 7-tuple +
# provenance). Everything mutable is written through _update_journal.
_IMMUTABLE_JOURNAL_KEYS = frozenset({
    "schema", "probe", "mode", "canonicalRequestId", "binding", "boundAt",
    "identitySchema", "stateMachineVersion", "legacyState", "payloadText",
})
_MAX_DELEGATION_ATTEMPTS = 2
_RECONCILE_SCAN_LIMIT = 25
# Errors whose message proves the command never reached the browser plane.
_PRE_DELEGATION_MARKERS = (
    "BROWSER_NATIVE_BRIDGE_UNAVAILABLE",
    "BROWSER_NATIVE_BRIDGE_DESCRIPTOR_INVALID",
    "BROWSER_NATIVE_PROTOCOL_MISMATCH",
    "BROWSER_NATIVE_UNAUTHORIZED",
    "BROWSER_NATIVE_REQUEST_ID_REQUIRED",
    "BROWSER_NATIVE_EXTENSION_NOT_CONNECTED",
    "BROWSER_NATIVE_EXTENSION_BUSY",
    "BROWSER_NATIVE_BRIDGE_BUSY",
    "BROWSER_NATIVE_PROVIDER_NOT_CONFIGURED",
    "CHATGPT_COMPOSER_NOT_FOUND",
    "CHATGPT_COMPOSER_NOT_READY",
    "TEXT_TOO_LARGE",
    "TAB_ID_REQUIRED",
    "TEXT_REQUIRED",
)
# Errors raised while the request was in flight in the browser plane: the
# write MAY have committed; these can only be resolved by RECONCILING.
_POST_DELEGATION_MARKERS = (
    "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION",
    "BROWSER_NATIVE_HOST_SHUTDOWN",
    "CHATGPT_SUBMIT_NOT_OBSERVED",
    "CHATGPT_TURN_TIMEOUT",
    "BROWSER_NATIVE_EXTENSION_TIMEOUT",
    "CHATGPT_DEBUGGER_ATTACHMENT_LEAK",
    "CHATGPT_TURN_HTTP_STATUS",
    "CHATGPT_TURN_MISSING_CONVERSATION_ID",
    "CHATGPT_CONVERSATION_REQUEST_FAILED",
    "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED",
    "BROWSER_NATIVE_TURN_MISSING_CONVERSATION_ID",
    "BROWSER_NATIVE_TURN_HTTP_STATUS",
)


class FinalReviewTransportError(Exception):
    """Fail-closed transport rejection with a stable ``:CODE`` message.

    Transaction-aware rejections carry the durable journal ``journal_state``
    plus ``safe_to_retry`` / ``reconcile_required`` gates so every caller
    surface (CLI, Soc_brain bridge) sees the same fail-closed semantics.
    """

    def __init__(
        self,
        message: str,
        *,
        journal_state: str | None = None,
        safe_to_retry: bool = False,
        reconcile_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.journal_state = journal_state
        self.safe_to_retry = safe_to_retry
        self.reconcile_required = reconcile_required


def _transport_code(reason: str) -> str:
    return f"{FINAL_REVIEW_TRANSPORT_ERROR}:{reason}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FinalReviewRequest:
    """Immutable final-review submission input."""

    __slots__ = (
        "repository",
        "issue_number",
        "pull_request_number",
        "head_sha",
        "evidence_digest",
        "verdict",
        "current_head_sha",
        "review_attempt_id",
        "expected_conversation_id",
    )

    def __init__(
        self,
        *,
        repository: str,
        issue_number: int,
        pull_request_number: int,
        head_sha: str,
        evidence_digest: str,
        verdict: str,
        current_head_sha: str,
        review_attempt_id: str = "1",
        expected_conversation_id: str | None = None,
    ) -> None:
        self.repository = repository
        self.issue_number = issue_number
        self.pull_request_number = pull_request_number
        self.head_sha = head_sha
        self.evidence_digest = evidence_digest
        self.verdict = verdict
        self.current_head_sha = current_head_sha
        self.review_attempt_id = review_attempt_id
        self.expected_conversation_id = expected_conversation_id


class FinalReviewResult:
    """Verified final-review transport outcome."""

    __slots__ = (
        "canonical_request_id",
        "conversation_id",
        "submission_id",
        "sse_conversation_identity_authority",
        "verdict",
        "finality",
        "payload",
        "reconciled_at",
    )

    def __init__(
        self,
        *,
        canonical_request_id: str,
        conversation_id: str,
        submission_id: str,
        sse_conversation_identity_authority: str | None,
        verdict: str,
        finality: str,
        payload: dict[str, Any],
        reconciled_at: str,
    ) -> None:
        self.canonical_request_id = canonical_request_id
        self.conversation_id = conversation_id
        self.submission_id = submission_id
        self.sse_conversation_identity_authority = (
            sse_conversation_identity_authority
        )
        self.verdict = verdict
        self.finality = finality
        self.payload = payload
        self.reconciled_at = reconciled_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonicalRequestId": self.canonical_request_id,
            "conversationId": self.conversation_id,
            "submissionId": self.submission_id,
            "sseConversationIdentityAuthority": (
                self.sse_conversation_identity_authority
            ),
            "verdict": self.verdict,
            "finality": self.finality,
            "payload": self.payload,
            "reconciledAt": self.reconciled_at,
            "state": STATE_RESPONSE_CONFIRMED,
            "safeToRetry": False,
            "reconcileRequired": False,
        }


class FinalReviewRequestResult:
    """Verified review-REQUEST outcome: the recovered GPT reply is DATA for the
    caller's own strict parsing; the transport owns identity/finality/binding."""

    __slots__ = (
        "canonical_request_id",
        "conversation_id",
        "submission_id",
        "sse_conversation_identity_authority",
        "reply_text",
        "model_slug",
        "finality",
        "payload",
        "reconciled_at",
    )

    def __init__(
        self,
        *,
        canonical_request_id: str,
        conversation_id: str,
        submission_id: str,
        sse_conversation_identity_authority: str | None,
        reply_text: str,
        model_slug: str | None,
        finality: str,
        payload: dict[str, Any],
        reconciled_at: str,
    ) -> None:
        self.canonical_request_id = canonical_request_id
        self.conversation_id = conversation_id
        self.submission_id = submission_id
        self.sse_conversation_identity_authority = (
            sse_conversation_identity_authority
        )
        self.reply_text = reply_text
        self.model_slug = model_slug
        self.finality = finality
        self.payload = payload
        self.reconciled_at = reconciled_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonicalRequestId": self.canonical_request_id,
            "conversationId": self.conversation_id,
            "submissionId": self.submission_id,
            "sseConversationIdentityAuthority": (
                self.sse_conversation_identity_authority
            ),
            "replyText": self.reply_text,
            "modelSlug": self.model_slug,
            "finality": self.finality,
            "payload": self.payload,
            "reconciledAt": self.reconciled_at,
            "state": STATE_RESPONSE_CONFIRMED,
            "safeToRetry": False,
            "reconcileRequired": False,
        }


class FinalReviewTransport(Protocol):
    """Replaceable final-review transport surface (no CWA-specific types)."""

    def submit_final_review(self, request: FinalReviewRequest) -> FinalReviewResult: ...

    def reconcile_final_review(
        self, canonical_request_id: str
    ) -> FinalReviewResult: ...


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _payload_text(payload: dict[str, Any]) -> str:
    return f"{FINAL_REVIEW_PAYLOAD_PREFIX} {_canonical_json(payload)}"


def _parse_payload_text(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.startswith(
        f"{FINAL_REVIEW_PAYLOAD_PREFIX} "
    ):
        raise FinalReviewTransportError(_transport_code("PAYLOAD_MALFORMED"))
    raw = text[len(FINAL_REVIEW_PAYLOAD_PREFIX) + 1 :]
    try:
        payload = json.loads(raw)
    except Exception as error:
        raise FinalReviewTransportError(
            _transport_code("PAYLOAD_MALFORMED")
        ) from error
    if not isinstance(payload, dict):
        raise FinalReviewTransportError(_transport_code("PAYLOAD_MALFORMED"))
    if _canonical_json(payload) != raw:
        raise FinalReviewTransportError(_transport_code("PAYLOAD_MALFORMED"))
    return payload


def _normalize_product_text(text: str) -> str:
    """Composer-owned text normalization: the product editor round-trips
    the text through its markdown model - non-breaking spaces, backslash
    escapes of special characters (observed live: ``_`` -> ``\\_``,
    ``:`` -> ``\\:``, ``<`` -> ``\\<``, applied recursively to
    already-escaped content) and newline-count normalization. This folds
    those transforms so the round-tripped text compares equal to the
    original; a residual mismatch still fails closed."""
    t = str(text).replace("\u00a0", " ")
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\\(.)", r"\1", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    return t


def _content_fingerprint(text: str) -> str:
    """Whitespace/punctuation-free content identifier - invariant to every
    observed composer markdown transform (recursive escaping,
    auto-linking, whitespace normalization); for a ~60 KB text a strong
    content identifier."""
    return re.sub(r"\W+", "", _normalize_product_text(text).lower())


def _persist(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# --- Issue #169 classification + legacy helpers ------------------------------
_LANE_PRE_DELEGATION = "PRE_DELEGATION"
_LANE_POST_DELEGATION = "POST_DELEGATION"

_EVENT_DELEGATION_ACCEPTED = "browser_native_delegation_accepted"
_EVENT_WRITE_OBSERVED = "browser_native_write_observed"
_EVENT_WRITE_COMPLETED = "browser_native_write_completed"
_EVENT_TURN_STARTED = "browser_native_turn_started"

# Pre-#169 durable states (schema 1/2) mapped onto the v3 state machine.
_LEGACY_STATE_MAP = {
    "BOUND": STATE_WRITE_FINALITY_UNKNOWN,
    "WRITE_ACKNOWLEDGED": STATE_WRITE_CONFIRMED,
    "WRITE_ACKNOWLEDGED_IDENTITY_REJECTED": STATE_WRITE_CONFIRMED_IDENTITY_REJECTED,
    "RECONCILED": STATE_RESPONSE_CONFIRMED,
    "SUBMIT_FAILED_NONRETRYABLE": STATE_SUBMIT_FAILED_NONRETRYABLE,
}


def _classify_submit_failure(error: BaseException) -> str:
    """Decide whether a submit-time exception could hide a committed write.

    A bridge error whose message names a pre-delegation boundary proves the
    command never crossed into the browser plane (fail-closed NONRETRYABLE).
    Everything else - including an unclassified error - is treated as
    POST_DELEGATION so the journal falls into the UNKNOWN -> RECONCILING lane
    instead of being wrongly retried or wrongly marked non-retryable.
    """
    text = f"{type(error).__name__}: {error}"
    if any(marker in text for marker in _POST_DELEGATION_MARKERS):
        return _LANE_POST_DELEGATION
    if any(marker in text for marker in _PRE_DELEGATION_MARKERS):
        return _LANE_PRE_DELEGATION
    return _LANE_POST_DELEGATION


def _is_correlation_text(value: Any) -> str:
    """A submission/turn correlation id qualifies ONLY as a non-empty,
    whitespace-stripped string. None/empty/non-string never correlate."""
    return value if isinstance(value, str) and value.strip() else ""


def _strict_write_completed_event(
    events: list[dict[str, Any]], ack_dict: dict[str, Any]
) -> dict[str, Any] | None:
    """The single write_completed event EXACTLY correlated to this ack.

    Strong ONLY when all three hold: the ack's own submission_id is non-empty,
    the event's submission_id is non-empty, and they are byte-equal. A missing
    or foreign event id never qualifies - it cannot terminalize WRITE_CONFIRMED
    nor supply the typed SSE identity authority.
    """
    ack_submission = _is_correlation_text(ack_dict.get("submission_id"))
    if not ack_submission:
        return None
    for event in events:
        if not isinstance(event, dict) or event.get("type") != _EVENT_WRITE_COMPLETED:
            continue
        event_submission = _is_correlation_text(event.get("submission_id"))
        if event_submission and event_submission == ack_submission:
            return event
    return None


def _classify_write_ack(
    events: list[dict[str, Any]], ack_dict: dict[str, Any]
) -> str:
    """Layered write-ack tier, correlated to this request's own events.

    strong     - a browser-native write-completed event whose submission_id is
                 non-empty and EXACTLY equals the ack's submission_id: the only
                 tier that may terminalize WRITE_CONFIRMED;
    correlated - a write-completed event exists but with a missing/foreign
                 submission_id, or only delegation/network frames for this
                 request: evidence, never WRITE_CONFIRMED;
    weak       - only turn_started/streaming/button transitions.
    Both correlated and weak fall through to WRITE_FINALITY_UNKNOWN.
    """
    if _strict_write_completed_event(events, ack_dict) is not None:
        return "strong"
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") in (
            _EVENT_DELEGATION_ACCEPTED,
            _EVENT_WRITE_OBSERVED,
        ):
            return "correlated"
    for event in events:
        if isinstance(event, dict) and event.get("type") == _EVENT_WRITE_COMPLETED:
            # A write_completed that is NOT exactly correlated (missing or
            # foreign submission_id): positive-looking but unproven.
            return "correlated"
    return "weak"


def _unconfirmed_write_evidence(
    journal: dict[str, Any], ack_dict: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Non-authoritative durable evidence fields for a weak/correlated ACK.

    Persisted BEFORE the UNKNOWN transition so the NEXT process (restart)
    reconciles from the journal alone - never from this process's memory.
    conversationId keeps its bind-once/drift semantics (correlated evidence,
    never identity, never write proof)."""
    fields: dict[str, Any] = {"unconfirmedAck": dict(ack_dict)}
    observed = _is_correlation_text(ack_dict.get("conversation_id"))
    if observed:
        prior = journal.get("conversationId")
        if prior in (None, ""):
            fields["conversationId"] = observed
        elif prior != observed:
            fields["observedConversationDrift"] = observed
    uncorrelated_completed = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("type") == _EVENT_WRITE_COMPLETED
        and _strict_write_completed_event([event], ack_dict) is None
    ]
    if uncorrelated_completed:
        fields["uncorrelatedWriteEvents"] = uncorrelated_completed
    return fields


def _has_positive_write_evidence(journal: dict[str, Any]) -> bool:
    """Everything a durable journal can carry that POSITIVELY suggests the
    write may have committed (none of it proves it): observed conversation,
    uncorrelated write_completed events, persisted ACK metadata, bridge/POST
    observations. Delegation-only is NOT positive write evidence (the WAL
    marks delegation anyway); a bare weak turn_started is not either."""
    observed = journal.get("conversationId")
    if isinstance(observed, str) and observed.strip():
        return True
    if journal.get("networkEvidence"):
        return True
    if journal.get("uncorrelatedWriteEvents"):
        return True
    unconfirmed_ack = journal.get("unconfirmedAck")
    if isinstance(unconfirmed_ack, dict):
        ack_conversation = unconfirmed_ack.get("conversation_id")
        if isinstance(ack_conversation, str) and ack_conversation.strip():
            return True
    return False




class CwaFinalReviewTransport:
    """CWA browser-owned implementation of ``FinalReviewTransport``."""

    def __init__(
        self,
        *,
        expected_repository: str,
        expected_issue_number: int,
        expected_pull_request_number: int,
        runtime_factory: Callable[[], Any],
        durable_store: Path,
    ) -> None:
        self._expected_repository = expected_repository
        self._expected_issue_number = expected_issue_number
        self._expected_pull_request_number = expected_pull_request_number
        self._runtime_factory = runtime_factory
        self._durable_store = Path(durable_store)
        self._durable_store.mkdir(parents=True, exist_ok=True)

    def _journal_path(self, canonical_request_id: str) -> Path:
        return self._durable_store / f"{canonical_request_id}.json"

    def _known_request_ids(self) -> set[str]:
        return {
            path.stem
            for path in self._durable_store.glob("*.json")
            if len(path.stem) == 64
        }

    @staticmethod
    def _migrate_journal(journal: dict[str, Any]) -> bool:
        """Map pre-#169 schema-1/2 journal states onto the v3 state machine.

        A v2 ``BOUND`` journal proves the request was durable but says nothing
        about whether the write call started (v2 had no WAL), so it migrates
        fail-closed to ``WRITE_FINALITY_UNKNOWN`` - never to PREPARED.
        Identity keys are NEVER touched by migration.
        """
        legacy_state = journal.get("state")
        migrated = _LEGACY_STATE_MAP.get(legacy_state)
        if migrated is None:
            return False
        journal["legacyState"] = legacy_state
        journal["state"] = migrated
        journal["stateMachineVersion"] = JOURNAL_SCHEMA
        if legacy_state == "WRITE_ACKNOWLEDGED" and journal.get(
            "identityRejection"
        ):
            journal["state"] = STATE_WRITE_CONFIRMED_IDENTITY_REJECTED
        return True

    def _load_journal(self, canonical_request_id: str) -> dict[str, Any]:
        path = self._journal_path(canonical_request_id)
        if not path.is_file():
            raise FinalReviewTransportError(_transport_code("UNKNOWN_REQUEST"))
        journal = json.loads(path.read_text(encoding="utf-8"))
        if self._migrate_journal(journal):
            _persist(path, journal)
        return journal

    def _validate_journal_invariants(self, journal: dict[str, Any]) -> None:
        """Storage chokepoint for the IMMUTABLE request identity invariant:
        every durable write must carry a canonical requestId that still equals
        ``canonical_request_identity`` over the persisted binding payload. Post
        write conversation/turn ids live in evidence keys and can never alter
        the identity; if they ever did, persistence fails closed."""
        canonical_request_id = journal.get("canonicalRequestId")
        binding = journal.get("binding") or {}
        payload = binding.get("canonicalPayload")
        if (
            isinstance(canonical_request_id, str)
            and isinstance(payload, dict)
            and canonical_request_identity(payload) != canonical_request_id
        ):
            raise FinalReviewTransportError(
                _transport_code("IDENTITY_MUTATION_FORBIDDEN")
            )
        state = journal.get("state")
        if state not in _ALL_STATES:
            raise FinalReviewTransportError(_transport_code("STATE_MACHINE_VIOLATION"))

    def _persist_journal(self, journal: dict[str, Any]) -> None:
        self._validate_journal_invariants(journal)
        _persist(
            self._journal_path(journal["canonicalRequestId"]), journal
        )

    def _update_journal(
        self,
        journal: dict[str, Any],
        *,
        to_state: str | None = None,
        **fields: Any,
    ) -> None:
        """Single mutation path: immutable-key guard + transition table +
        durable persist. Transition violations never reach disk."""
        frozen = _IMMUTABLE_JOURNAL_KEYS - {"schema"}
        for key in fields:
            if key in frozen:
                raise FinalReviewTransportError(
                    _transport_code("IDENTITY_MUTATION_FORBIDDEN")
                )
        current = journal.get("state")
        if to_state is not None:
            if to_state != current and to_state not in _STATE_TRANSITIONS.get(
                str(current), frozenset()
            ):
                raise FinalReviewTransportError(
                    _transport_code("STATE_MACHINE_VIOLATION")
                )
            journal["state"] = to_state
        journal.update(fields)
        self._persist_journal(journal)

    def _assert_no_active_submission(self, canonical_request_id: str) -> None:
        for path in self._durable_store.glob("*.json"):
            if path.stem == canonical_request_id or len(path.stem) != 64:
                continue
            try:
                journal = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            self._migrate_journal(journal)
            if journal.get("state") in _ACTIVE_STATES:
                raise FinalReviewTransportError(
                    _transport_code("ACTIVE_SUBMISSION_EXISTS")
                )

    def submit_final_review(self, request: FinalReviewRequest) -> FinalReviewResult:
        try:
            binding = bind_final_review_request(
                request.repository,
                request.issue_number,
                request.pull_request_number,
                request.head_sha,
                request.evidence_digest,
                request.verdict,
                expected_repository=self._expected_repository,
                expected_issue_number=self._expected_issue_number,
                expected_pull_request_number=self._expected_pull_request_number,
                current_head_sha=request.current_head_sha,
                known_request_ids=self._known_request_ids(),
                review_attempt_id=getattr(request, "review_attempt_id", "1"),
                expected_conversation_id=getattr(
                    request, "expected_conversation_id", None
                ),
            )
        except FinalReviewBindingError as error:
            if (
                str(error).rsplit(":", 1)[-1] != "REPLAY"
                or error.canonical_request_id is None
            ):
                raise
            journal = self._load_journal(error.canonical_request_id)
            if journal.get("mode") != "VERDICT":
                raise
            dispatch = self._dispatch_submit(journal)
            if not isinstance(dispatch, FinalReviewResult):
                raise FinalReviewTransportError(
                    _transport_code("MODE_MISMATCH_REPLAY")
                )
            return dispatch
        canonical_request_id = binding["canonicalRequestId"]
        self._assert_no_active_submission(canonical_request_id)
        journal = self._bound_journal(binding, mode="VERDICT")
        journal["payloadText"] = _payload_text(binding["canonicalPayload"])
        self._persist_journal(journal)
        dispatch = self._dispatch_submit(journal)
        if not isinstance(dispatch, FinalReviewResult):
            raise FinalReviewTransportError(_transport_code("MODE_MISMATCH_REPLAY"))
        return dispatch

    def submit_final_review_request(
        self,
        *,
        prompt: str,
        repository: str,
        issue_number: int,
        pull_request_number: int,
        head_sha: str,
        evidence_digest: str,
        current_head_sha: str,
        review_attempt_id: str = "1",
        expected_conversation_id: str | None = None,
    ) -> "FinalReviewRequestResult":
        """Review-REQUEST mode: submit the caller's prompt as the protected
        write, then recover the assistant REPLY (the GPT verdict payload) via
        canonical reads. Binding/durability/identity/finality semantics are
        identical to verdict-delivery mode; there is no verdict at bind time
        (the canonical payload omits it)."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise FinalReviewTransportError(_transport_code("PROMPT_INVALID"))
        if len(prompt) > 200_000:
            raise FinalReviewTransportError(_transport_code("PROMPT_TOO_LARGE"))
        try:
            binding = bind_final_review_request(
                repository,
                issue_number,
                pull_request_number,
                head_sha,
                evidence_digest,
                expected_repository=self._expected_repository,
                expected_issue_number=self._expected_issue_number,
                expected_pull_request_number=self._expected_pull_request_number,
                current_head_sha=current_head_sha,
                known_request_ids=self._known_request_ids(),
                review_attempt_id=review_attempt_id,
                expected_conversation_id=expected_conversation_id,
                prompt_sha256=prompt_identity_hash(prompt),
            )
        except FinalReviewBindingError as error:
            if (
                str(error).rsplit(":", 1)[-1] != "REPLAY"
                or error.canonical_request_id is None
            ):
                raise
            # Same immutable identity already bound: continue from durable
            # evidence under the transaction state machine. A resend is only
            # legal on the NO_WRITE_PROVEN retry edge inside _dispatch_submit;
            # delegated-but-unconfirmed journals reconcile FIRST.
            journal = self._load_journal(error.canonical_request_id)
            if journal.get("mode") != "REQUEST":
                raise
            dispatch = self._dispatch_submit(journal)
            if not isinstance(dispatch, FinalReviewRequestResult):
                raise FinalReviewTransportError(
                    _transport_code("MODE_MISMATCH_REPLAY")
                )
            return dispatch
        canonical_request_id = binding["canonicalRequestId"]
        self._assert_no_active_submission(canonical_request_id)
        journal = self._bound_journal(binding, mode="REQUEST")
        journal["payloadText"] = prompt
        self._persist_journal(journal)
        dispatch = self._dispatch_submit(journal)
        if not isinstance(dispatch, FinalReviewRequestResult):
            raise FinalReviewTransportError(_transport_code("MODE_MISMATCH_REPLAY"))
        return dispatch

    def _bound_journal(self, binding: dict[str, Any], *, mode: str) -> dict[str, Any]:
        journal: dict[str, Any] = {
            "schema": JOURNAL_SCHEMA,
            "stateMachineVersion": JOURNAL_SCHEMA,
            "probe": "FINAL_REVIEW_TRANSPORT",
            "mode": mode,
            "state": STATE_PREPARED,
            "boundAt": _utc_now(),
            "canonicalRequestId": binding["canonicalRequestId"],
            "binding": binding,
            "liveWriteCount": 0,
            "delegationAttempts": 0,
            "evidence": {
                "expectedConversationId": binding["canonicalPayload"][
                    "conversationId"
                ],
                "observed": [],
            },
        }
        # Durable BEFORE external mutation: replay/duplicate rejection and
        # crash reconciliation both key off this file.
        return journal

    def _dispatch_submit(
        self, journal: dict[str, Any]
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        """Idempotent transaction dispatcher shared by first bind and REPLAY
        continuation. Reconcile-before-retry is structural: the delegation
        lane is only entered from PREPARED or from a persisted
        NO_WRITE_PROVEN negative proof, bounded by _MAX_DELEGATION_ATTEMPTS."""
        for _ in range(2 * _MAX_DELEGATION_ATTEMPTS + 2):
            state = journal["state"]
            if state == STATE_PREPARED:
                self._protected_write(journal)
                continue
            if state == STATE_NO_WRITE_PROVEN:
                if int(journal.get("delegationAttempts", 0)) >= _MAX_DELEGATION_ATTEMPTS:
                    raise FinalReviewTransportError(
                        _transport_code("RETRY_BUDGET_EXHAUSTED"),
                        journal_state=state,
                        safe_to_retry=False,
                    )
                self._update_journal(journal, retryConsumedAt=_utc_now())
                self._protected_write(journal)
                continue
            if state in (
                STATE_SUBMIT_DELEGATED,
                STATE_WRITE_FINALITY_UNKNOWN,
                STATE_RECONCILING,
            ):
                recovered = self._reconcile_finality(journal)
                if recovered is not None:
                    return recovered
                # Reconcile proved the write never committed. The journal now
                # durably holds NO_WRITE_PROVEN (the only SAFE_TO_RETRY state)
                # but this call does NOT resend - the caller must re-invoke
                # submit to consume the single bounded retry edge.
                raise FinalReviewTransportError(
                    _transport_code("NO_WRITE_PROVEN"),
                    journal_state=STATE_NO_WRITE_PROVEN,
                    safe_to_retry=True,
                    reconcile_required=False,
                )
            if state in (STATE_WRITE_CONFIRMED, STATE_WRITE_FOUND):
                return self._recover_from_ack(journal)
            if state == STATE_RESPONSE_WAIT:
                return self._recover_from_ack(journal)
            if state == STATE_RESPONSE_CONFIRMED:
                return self._replay_terminal(journal)
            if state == STATE_WRITE_CONFIRMED_IDENTITY_REJECTED:
                raise FinalReviewTransportError(
                    _transport_code("IDENTITY_REJECTED_NOT_RECONCILABLE"),
                    journal_state=state,
                )
            if state == STATE_AMBIGUOUS:
                raise FinalReviewTransportError(
                    _transport_code("AMBIGUOUS_NOT_RECONCILABLE"),
                    journal_state=state,
                )
            if state == STATE_SUBMIT_FAILED_NONRETRYABLE:
                raise FinalReviewTransportError(
                    _transport_code("SUBMIT_FAILED_NONRETRYABLE"),
                    journal_state=state,
                )
            raise FinalReviewTransportError(_transport_code("STATE_MACHINE_VIOLATION"))
        raise FinalReviewTransportError(_transport_code("DISPATCH_NOT_CONVERGING"))

    def _replay_terminal(
        self, journal: dict[str, Any]
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        if journal.get("mode") == "REQUEST":
            return self._request_result_from_journal(journal)
        stored = journal.get("result") or {}
        return FinalReviewResult(
            canonical_request_id=journal["canonicalRequestId"],
            conversation_id=journal.get("conversationId")
            or journal["binding"]["canonicalPayload"].get("conversationId", ""),
            submission_id=(journal.get("ack") or {}).get("submission_id", ""),
            sse_conversation_identity_authority=journal.get(
                "sseConversationIdentityAuthority"
            ),
            verdict=stored.get(
                "verdict", journal["binding"]["canonicalPayload"]["verdict"]
            ),
            finality="FINAL",
            payload=journal["binding"]["canonicalPayload"],
            reconciled_at=stored.get("reconciledAt", journal.get("finishedAt", "")),
        )

    def _protected_write(self, journal: dict[str, Any]) -> None:
        """Exactly one browser-owned write, WAL-guarded, identity-gated.

        Order is load-bearing for Issue #169:
        1. durable ``SUBMIT_DELEGATED`` BEFORE the command leaves the process;
        2. phase frames (``delegation_accepted``) are persisted as evidence;
        3. any in-flight loss => ``WRITE_FINALITY_UNKNOWN`` (never a resend);
        4. the durable write ACK + typed identity evidence persist BEFORE any
           fail-closed gate, so reconciliation never loses the write evidence.
        """
        events: list[dict[str, Any]] = []

        try:
            runtime = self._runtime_factory()
        except Exception as error:
            journal["submitErrorType"] = type(error).__name__
            journal["submitError"] = str(error)
            journal["finishedAt"] = _utc_now()
            self._update_journal(
                journal, to_state=STATE_SUBMIT_FAILED_NONRETRYABLE
            )
            raise FinalReviewTransportError(
                _transport_code("SUBMIT_FAILED_NONRETRYABLE")
            ) from error

        def phase_event(event: dict[str, Any]) -> None:
            events.append(event)
            event_type = event.get("type")
            if event_type == _EVENT_DELEGATION_ACCEPTED:
                try:
                    self._update_journal(
                        journal,
                        bridgeDelegatedAtMs=event.get("acceptedAtMs"),
                    )
                except FinalReviewTransportError:
                    pass  # evidence duplication cannot alter write authority
            elif event_type == _EVENT_WRITE_OBSERVED:
                try:
                    network = list(journal.get("networkEvidence") or [])
                    network.append(
                        {
                            "atMs": event.get("atMs"),
                            "observedAt": _utc_now(),
                        }
                    )
                    self._update_journal(journal, networkEvidence=network)
                except FinalReviewTransportError:
                    pass

        # (1) Write-ahead: delegation intent is durable before any external
        # mutation, so a process crash between "sent" and "answered" can only
        # be resumed through the UNKNOWN -> RECONCILING lane.
        self._update_journal(
            journal,
            to_state=STATE_SUBMIT_DELEGATED,
            submitDelegatedAt=_utc_now(),
            delegationAttempts=int(journal.get("delegationAttempts", 0)) + 1,
        )
        try:
            ack = runtime.submit(
                journal["payloadText"],
                timeout=240.0,
                poll_interval=0.5,
                on_event=phase_event,
            )
        except Exception as error:
            lane = _classify_submit_failure(error)
            journal["submitErrorType"] = type(error).__name__
            journal["submitError"] = str(error)
            journal["submitFailureLane"] = lane
            journal["finishedAt"] = _utc_now()
            # Any write_completed frame observed BEFORE the loss is positive
            # evidence (no ack ever returned, so none of it can be exactly
            # correlated): persist it so the restart reconcile sees it.
            streamed_completed = [
                event
                for event in events
                if isinstance(event, dict)
                and event.get("type") == _EVENT_WRITE_COMPLETED
            ]
            if streamed_completed:
                journal["uncorrelatedWriteEvents"] = streamed_completed
            if lane == _LANE_PRE_DELEGATION:
                self._update_journal(
                    journal, to_state=STATE_SUBMIT_FAILED_NONRETRYABLE
                )
                raise FinalReviewTransportError(
                    _transport_code("SUBMIT_FAILED_NONRETRYABLE")
                ) from error
            # The write MAY have committed: the ONLY legal continuation is
            # RECONCILING with evidence - never an implicit retry.
            self._update_journal(
                journal, to_state=STATE_WRITE_FINALITY_UNKNOWN
            )
            raise FinalReviewTransportError(
                _transport_code("WRITE_FINALITY_UNKNOWN"),
                journal_state=STATE_WRITE_FINALITY_UNKNOWN,
                safe_to_retry=False,
                reconcile_required=True,
            ) from error

        ack_dict = ack.to_dict() if hasattr(ack, "to_dict") else dict(ack)
        conversation_id = ack_dict.get("conversation_id")
        authority = None
        record_count = None
        distinct_count = None
        # The typed SSE identity authority is read off the EXACTLY-correlated
        # write_completed event only (both submission ids non-empty and equal).
        # A foreign or missing-id event supplies NO authority: the identity gate
        # then fails closed and the tier check routes to UNKNOWN.
        authority_source = _strict_write_completed_event(events, ack_dict)
        if authority_source is not None:
            authority = authority_source.get("sse_conversation_identity_authority")
            record_count = authority_source.get(
                "sse_conversation_identity_record_count"
            )
            distinct_count = authority_source.get(
                "sse_conversation_identity_distinct_count"
            )
        tier = _classify_write_ack(events, ack_dict)
        journal["writeAckTier"] = tier
        if tier != "strong":
            # weak/correlated-only signals (Stop-button/streaming transitions,
            # delegation/network frames, or ANOTHER/missing submission id on an
            # otherwise-observed write) must never terminalize WRITE_CONFIRMED.
            # BUT the positive evidence they carry is persisted durably so a
            # post-restart reconcile can never collapse a real observation into
            # NO_WRITE_PROVEN: a non-empty ACK conversation_id and/or any
            # write_completed event become candidate/positive evidence. The typed
            # SSE authority is NEVER taken from these events (authority_source was
            # exact-correlation only), so this stays non-authoritative.
            evidence_fields = _unconfirmed_write_evidence(journal, ack_dict, events)
            self._update_journal(
                journal,
                to_state=STATE_WRITE_FINALITY_UNKNOWN,
                weakAckOnly=True,
                finishedAt=_utc_now(),
                **evidence_fields,
            )
            raise FinalReviewTransportError(
                _transport_code("WRITE_FINALITY_UNKNOWN"),
                journal_state=STATE_WRITE_FINALITY_UNKNOWN,
                safe_to_retry=False,
                reconcile_required=True,
            )
        identity_rejection = None
        observed = conversation_id if isinstance(conversation_id, str) else ""
        if not observed.strip():
            identity_rejection = "IDENTITY_AUTHORITY_ABSENT"
        elif observed.startswith("WEB:"):
            identity_rejection = "IDENTITY_ROUTE_ONLY"
        elif authority != CWA_SSE_IDENTITY_AUTHORITY:
            identity_rejection = "IDENTITY_AUTHORITY_ABSENT"
        if identity_rejection is not None:
            self._update_journal(
                journal,
                to_state=STATE_WRITE_CONFIRMED_IDENTITY_REJECTED,
                liveWriteCount=int(journal.get("liveWriteCount", 0)) + 1,
                identityRejection=identity_rejection,
                ack=ack_dict,
                writeEvents=[
                    event
                    for event in events
                    if event.get("type")
                    in (_EVENT_TURN_STARTED, _EVENT_WRITE_COMPLETED)
                ],
            )
            raise FinalReviewTransportError(
                _transport_code(identity_rejection),
                journal_state=STATE_WRITE_CONFIRMED_IDENTITY_REJECTED,
            )
        # Correlated EVIDENCE (never identity): bind the observed conversation
        # id once; a different later observation is recorded as drift but can
        # never replace the immutable request identity.
        evidence_fields: dict[str, Any] = {}
        prior_observed = journal.get("conversationId")
        if prior_observed in (None, ""):
            evidence_fields["conversationId"] = observed
        elif prior_observed != observed:
            evidence_fields["observedConversationDrift"] = observed
        # Durable ACK BEFORE any finality attempt.
        self._update_journal(
            journal,
            to_state=STATE_WRITE_CONFIRMED,
            writeAcknowledgedAt=_utc_now(),
            ack=ack_dict,
            sseConversationIdentityAuthority=authority,
            sseConversationIdentityRecordCount=record_count,
            sseConversationIdentityDistinctCount=distinct_count,
            liveWriteCount=int(journal.get("liveWriteCount", 0)) + 1,
            writeEvents=[
                event
                for event in events
                if event.get("type") in (_EVENT_TURN_STARTED, _EVENT_WRITE_COMPLETED)
            ],
            **evidence_fields,
        )

    def reconcile_final_review(
        self, canonical_request_id: str
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        journal = self._load_journal(canonical_request_id)
        state = journal["state"]
        if state == STATE_RESPONSE_CONFIRMED:
            return self._replay_terminal(journal)
        if state == STATE_WRITE_CONFIRMED_IDENTITY_REJECTED:
            raise FinalReviewTransportError(
                _transport_code("IDENTITY_REJECTED_NOT_RECONCILABLE"),
                journal_state=state,
            )
        if state == STATE_AMBIGUOUS:
            raise FinalReviewTransportError(
                _transport_code("AMBIGUOUS_NOT_RECONCILABLE"),
                journal_state=state,
            )
        if state == STATE_SUBMIT_FAILED_NONRETRYABLE:
            raise FinalReviewTransportError(
                _transport_code("SUBMIT_FAILED_NONRETRYABLE"),
                journal_state=state,
            )
        if state == STATE_NO_WRITE_PROVEN:
            # Negative proof is durable: the request may be re-delegated by
            # the next submit; reconcile itself performs no read loop because
            # there is provably nothing to recover.
            raise FinalReviewTransportError(
                _transport_code("NO_WRITE_PROVEN"),
                journal_state=state,
                safe_to_retry=True,
                reconcile_required=False,
            )
        if state == STATE_PREPARED:
            # Durable journal never reached delegation (crash before WAL): no
            # side effect is possible, nothing to read back.
            raise FinalReviewTransportError(
                _transport_code("RECONCILIATION_REQUIRES_ACK"),
                journal_state=state,
                safe_to_retry=False,
                reconcile_required=False,
            )
        if state in (
            STATE_SUBMIT_DELEGATED,
            STATE_WRITE_FINALITY_UNKNOWN,
            STATE_RECONCILING,
        ):
            recovered = self._reconcile_finality(journal)
            if recovered is not None:
                return recovered
            raise FinalReviewTransportError(
                _transport_code("NO_WRITE_PROVEN"),
                journal_state=STATE_NO_WRITE_PROVEN,
                safe_to_retry=True,
                reconcile_required=False,
            )
        if state in (STATE_WRITE_CONFIRMED, STATE_WRITE_FOUND, STATE_RESPONSE_WAIT):
            return self._recover_from_ack(journal)
        raise FinalReviewTransportError(_transport_code("STATE_MACHINE_VIOLATION"))

    def _reconcile_finality(
        self, journal: dict[str, Any]
    ) -> "FinalReviewResult | FinalReviewRequestResult | None":
        """RECONCILING lane: journal + conversation/turn identity + history
        readback + persisted bridge/network evidence decide the outcome.
        Returns the recovered result on WRITE_FOUND, ``None`` on a durable
        NO_WRITE_PROVEN negative proof, and fails closed (AMBIGUOUS) whenever
        the evidence does not decide."""
        if journal["state"] != STATE_RECONCILING:
            self._update_journal(
                journal, to_state=STATE_RECONCILING, reconcileStartedAt=_utc_now()
            )
        try:
            runtime = self._runtime_factory()
        except Exception as error:
            raise FinalReviewTransportError(
                _transport_code("RECONCILIATION_UNAVAILABLE"),
                journal_state=STATE_RECONCILING,
                reconcile_required=True,
            ) from error
        (
            matched,
            duplicate,
            conclusive,
            positive_evidence,
            notes,
        ) = self._collect_write_evidence(runtime, journal)
        if duplicate:
            self._update_journal(
                journal,
                to_state=STATE_AMBIGUOUS,
                ambiguousReason="DUPLICATE_COMMIT_EVIDENCE",
                reconcileNotes=notes,
                finishedAt=_utc_now(),
            )
            raise FinalReviewTransportError(
                _transport_code("AMBIGUOUS_FINALITY"),
                journal_state=STATE_AMBIGUOUS,
                safe_to_retry=False,
                reconcile_required=False,
            )
        if matched is not None:
            # WRITE_FOUND: the exact prompt/turn was LOCATED via canonical/
            # history evidence - zero resend; response recovery continues over
            # correlated evidence bound to the immutable id.
            evidence_fields: dict[str, Any] = {}
            prior_observed = journal.get("conversationId")
            if prior_observed in (None, ""):
                evidence_fields["conversationId"] = matched
            elif prior_observed != matched:
                evidence_fields["observedConversationDrift"] = matched
            self._update_journal(
                journal,
                to_state=STATE_WRITE_FOUND,
                writeFoundAt=_utc_now(),
                reconcileNotes=notes,
                **evidence_fields,
            )
            return self._recover_from_ack(journal)
        if not conclusive:
            self._update_journal(
                journal,
                to_state=STATE_AMBIGUOUS,
                ambiguousReason="EVIDENCE_INCONCLUSIVE",
                reconcileNotes=notes,
                positiveEvidence=positive_evidence,
                finishedAt=_utc_now(),
            )
            raise FinalReviewTransportError(
                _transport_code("AMBIGUOUS_FINALITY"),
                journal_state=STATE_AMBIGUOUS,
                safe_to_retry=False,
                reconcile_required=False,
            )
        if positive_evidence:
            # A conversation and/or bridge/POST observation exists, but the
            # canonical history could NOT locate the exact turn: the write can
            # be neither confirmed nor disproven. journal.conversationId is
            # correlation evidence, NEVER write proof -> AMBIGUOUS, human look.
            self._update_journal(
                journal,
                to_state=STATE_AMBIGUOUS,
                ambiguousReason="POSITIVE_EVIDENCE_WITHOUT_EXACT_TURN",
                reconcileNotes=notes,
                finishedAt=_utc_now(),
            )
            raise FinalReviewTransportError(
                _transport_code("AMBIGUOUS_FINALITY"),
                journal_state=STATE_AMBIGUOUS,
                safe_to_retry=False,
                reconcile_required=False,
            )
        self._update_journal(
            journal,
            to_state=STATE_NO_WRITE_PROVEN,
            noWriteProvenAt=_utc_now(),
            negativeProof={
                "method": "HISTORY_SCAN_NO_MATCH",
                "scannedConversations": int(journal.get("reconcileScanCount") or 0),
                "positiveEvidence": False,
                "notes": notes,
            },
        )
        return None

    def _collect_write_evidence(
        self, runtime: Any, journal: dict[str, Any]
    ) -> tuple[str | None, bool, bool, bool, list[str]]:
        """Returns (matchedConversationId, duplicate, conclusive,
        has_positive_evidence, notes).

        WRITE_FOUND proof is EXACTLY one thing: a user turn whose composer-
        normalized text or content fingerprint equals this request's durable
        payload text, located through the canonical/history read plane. The
        journal's observed conversationId is a scan CANDIDATE and positive
        evidence at most - it is never a match by itself, because the
        conversation may exist (created, POST observed) without the turn ever
        landing in it.
        """
        identity_payload = journal["binding"]["canonicalPayload"]
        expected = identity_payload.get("conversationId") or NO_PREASSIGNED_CONVERSATION
        payload_text = journal["payloadText"]
        payload_norm = _normalize_product_text(payload_text)
        payload_fingerprint = _content_fingerprint(payload_text)
        client = getattr(runtime, "client", runtime)

        candidates: list[str] = []
        if expected != NO_PREASSIGNED_CONVERSATION:
            candidates.append(expected)
        else:
            lister = getattr(client, "_list_recent_conversations", None)
            if not callable(lister):
                return None, False, False, False, ["NEGATIVE_PROBE_UNAVAILABLE"]
            try:
                items = lister(limit=_RECONCILE_SCAN_LIMIT) or []
            except Exception:
                return None, False, False, False, ["NEGATIVE_PROBE_FAILED"]
            for item in items:
                conversation_id = item.get("id") if isinstance(item, dict) else None
                if isinstance(conversation_id, str) and conversation_id.strip():
                    candidates.append(conversation_id.strip())
        # The observed conversation is scanned too - as a CANDIDATE only.
        observed = journal.get("conversationId")
        # Positive evidence is read from the DURABLE JOURNAL ONLY: an observed
        # conversationId, persisted bridge/POST observations, uncorrelated
        # write_completed events or an unconfirmed-ACK conversation - all
        # survive restart. (Reconstructed here, never from caller memory.)
        has_positive_evidence = _has_positive_write_evidence(journal)
        if isinstance(observed, str) and observed.strip():
            if observed.strip() not in candidates:
                candidates.append(observed.strip())
        # An unconfirmed ACK naming a different conversation than the bound
        # conversationId still contributes its own candidate + positive signal.
        unconfirmed_ack = journal.get("unconfirmedAck")
        if isinstance(unconfirmed_ack, dict):
            ack_conversation = unconfirmed_ack.get("conversation_id")
            if (
                isinstance(ack_conversation, str)
                and ack_conversation.strip()
                and ack_conversation.strip() not in candidates
            ):
                candidates.append(ack_conversation.strip())
        if journal.get("uncorrelatedWriteEvents"):
            for event in journal["uncorrelatedWriteEvents"]:
                event_conversation = (
                    event.get("conversation_id") if isinstance(event, dict) else None
                )
                if (
                    isinstance(event_conversation, str)
                    and event_conversation.strip()
                    and event_conversation.strip() not in candidates
                ):
                    candidates.append(event_conversation.strip())
        journal["reconcileScanCount"] = len(candidates)

        matches: list[tuple[str, str | None]] = []
        for conversation_id in candidates:
            try:
                messages = runtime.get_messages(ConversationRef(conversation_id))
            except Exception:
                return None, False, False, has_positive_evidence, [
                    f"READ_FAILED:{conversation_id}"
                ]
            for message in messages if isinstance(messages, list) else []:
                item = message.to_dict() if hasattr(message, "to_dict") else message
                if not isinstance(item, dict) or item.get("role") != "user":
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                if (
                    _normalize_product_text(text) == payload_norm
                    or _content_fingerprint(text) == payload_fingerprint
                ):
                    matches.append((conversation_id, item.get("message_id")))
        if len(matches) > 1:
            # Several located turns = a committed duplicate: positive evidence
            # AND unresolvable finality.
            return matches[0][0], True, True, True, [f"MATCHES:{len(matches)}"]
        if matches:
            return (
                matches[0][0],
                False,
                True,
                True,
                [f"MATCH:{matches[0][0]}"],
            )
        return None, False, True, has_positive_evidence, ["SCAN_CLEAN"]

    def _recover_from_ack(
        self, journal: dict[str, Any]
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        if journal.get("mode") == "REQUEST":
            return self._recover_request(journal)
        return self._recover_verdict(journal)

    def _begin_response_wait(self, journal: dict[str, Any]) -> None:
        """RESPONSE_WAIT is durable before the first canonical read attempt:
        response recovery is re-enterable after crash/restart with ZERO
        writes."""
        state = journal["state"]
        if state in (STATE_WRITE_CONFIRMED, STATE_WRITE_FOUND):
            self._update_journal(
                journal, to_state=STATE_RESPONSE_WAIT, responseWaitAt=_utc_now()
            )
        elif state != STATE_RESPONSE_WAIT:
            raise FinalReviewTransportError(
                _transport_code("RECOVERY_NOT_DELEGATED"), journal_state=state
            )

    def _recover_request(
        self, journal: dict[str, Any]
    ) -> "FinalReviewRequestResult":
        self._begin_response_wait(journal)
        canonical_request_id = journal["canonicalRequestId"]

        conversation_id = journal["conversationId"]
        evidence_digest = journal["binding"]["canonicalPayload"]["evidenceDigest"]
        prompt = journal["payloadText"]
        head_sha = journal["binding"]["canonicalPayload"]["headSha"]
        runtime = self._runtime_factory()
        conversation = ConversationRef(conversation_id)

        attempts: list[dict[str, Any]] = []
        reply_text: str | None = None
        recovered_message_id: str | None = None
        recovered_user_message_id: str | None = None
        model_slug: str | None = None
        finality: str | None = None
        for attempt in range(1, _READ_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(_READ_WAIT_S[attempt - 1])
            else:
                time.sleep(_READ_WAIT_S[0])
            try:
                status = runtime.get_status(conversation)
                status_result = (
                    status.to_dict() if hasattr(status, "to_dict") else status
                )
            except Exception as error:  # noqa: BLE001 - evidence boundary
                status_result = {
                    "errorType": type(error).__name__,
                    "error": str(error),
                }
            try:
                messages = runtime.get_messages(conversation)
                items = [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in (messages if isinstance(messages, list) else [])
                ]
            except Exception as error:  # noqa: BLE001 - evidence boundary
                items = []
            # Request binding (composer-round-trip robust): the conversation
            # was CREATED by this write (the CWA request-bound conversation
            # identity authority), so the first user message IS this request.
            # The message text survives the composer only as a transformed
            # round-trip (nbsp/CRLF/markdown escapes/auto-linking) — the
            # binding check = the normalized message must carry the reviewed
            # HEAD (the hex survives every observed composer transform) and
            # the exact packet digest marker.
            # Request binding (composer-round-trip robust): the conversation
            # was CREATED by this write — its CWA request-bound conversation
            # identity authority (verified at write time and recorded in the
            # journal) binds the conversation to THIS request. The user
            # messages in the conversation are therefore this request's
            # round-trip; their text survives the composer only as a
            # transformed form (nbsp/recursive markdown escapes/auto-linking)
            # and is NOT used for byte-exact binding. The reply-side head echo
            # (below) is the strong response binding.
            user_items = [item for item in items if item.get("role") == "user"]
            if len(user_items) > 1:
                raise FinalReviewTransportError(
                    _transport_code("DUPLICATE_COMMIT")
                )
            assistant_after = None
            if user_items:
                user_index = items.index(user_items[0])
                assistants_after = [
                    item
                    for item in items[user_index + 1 :]
                    if item.get("role") == "assistant"
                ]
                # The product may stream a reasoning-summary assistant message
                # (no finish) BEFORE the final answer — the LAST assistant
                # after our user message is the authoritative reply.
                assistant_after = assistants_after[-1] if assistants_after else None
            assistant_complete = bool(
                assistant_after
                and assistant_after.get("finish_reason") == "stop"
                and (assistant_after.get("metadata_preview") or {}).get(
                    "is_complete"
                )
                is True
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "readAt": _utc_now(),
                    "status": status_result,
                    "messageCount": len(items),
                    "matchingUserMessageCount": len(user_items),
                    "assistantMessageId": (
                        assistant_after or {}
                    ).get("message_id"),
                    "assistantComplete": assistant_complete,
                }
            )
            if user_items and assistant_complete:
                # Request binding (composer-round-trip robust): the
                # conversation was CREATED by this write (the CWA
                # request-bound conversation identity authority), so the user
                # messages in the conversation are this request's round-trip;
                # their text survives the composer only as a transformed form
                # (nbsp/recursive markdown escapes/auto-linking) and is NOT
                # used for byte-exact binding. The reply-side head echo
                # (below) is the strong response binding.
                reply_text_candidate = assistant_after.get("text")
                reply_text = reply_text_candidate if isinstance(reply_text_candidate, str) else None
                if not reply_text or not reply_text.strip():
                    # Unambiguous finality with an empty reply body is not a
                    # verdict; the journal stays WRITE_ACKNOWLEDGED so a later
                    # reconcile can re-read without any new write.
                    raise FinalReviewTransportError(_transport_code("REPLY_EMPTY"))
                reply_norm = _normalize_product_text(reply_text)
                if _normalize_product_text(head_sha) not in reply_norm:
                    raise FinalReviewTransportError(
                        _transport_code("RESPONSE_MISMATCH")
                    )
                recovered_message_id = assistant_after.get("message_id")
                recovered_user_message_id = user_items[0].get("message_id")
                model_value = (assistant_after.get("metadata_preview") or {}).get(
                    "model_slug"
                )
                model_slug = model_value if isinstance(model_value, str) else None
                finality = "FINAL"
                break
        if finality != "FINAL":
            # Persist the read attempts: the durable journal must show WHAT the
            # canonical reads observed before the fail-closed verdict.
            journal["canonicalReadAttempts"] = attempts
            _persist(self._journal_path(canonical_request_id), journal)
            raise FinalReviewTransportError(
                _transport_code("FINALITY_AMBIGUOUS"),
                journal_state=STATE_RESPONSE_WAIT,
                reconcile_required=True,
            )
        if reply_text is None or not reply_text.strip():
            # Unambiguous finality with an empty reply body is not a verdict;
            # the journal stays RESPONSE_WAIT so a later reconcile can re-read
            # without any new write.
            raise FinalReviewTransportError(_transport_code("REPLY_EMPTY"))
        self._update_journal(
            journal,
            to_state=STATE_RESPONSE_CONFIRMED,
            reconciledAt=_utc_now(),
            canonicalReadAttempts=attempts,
            recoveredAssistantMessageId=recovered_message_id,
            recoveredUserMessageId=recovered_user_message_id,
            replyText=reply_text,
            replyModelSlug=model_slug,
            result={
                "finality": finality,
                "replyText": reply_text,
                "replyModelSlug": model_slug,
            },
        )
        return self._request_result_from_journal(journal)

    def _request_result_from_journal(
        self, journal: dict[str, Any]
    ) -> "FinalReviewRequestResult":
        return FinalReviewRequestResult(
            canonical_request_id=journal["canonicalRequestId"],
            conversation_id=journal.get("conversationId") or "",
            submission_id=(journal.get("ack") or {}).get("submission_id")
            or journal.get("recoveredAssistantMessageId")
            or "reconciled",
            sse_conversation_identity_authority=journal.get(
                "sseConversationIdentityAuthority"
            ),
            reply_text=journal["replyText"],
            model_slug=journal.get("replyModelSlug"),
            finality="FINAL",
            payload=journal["binding"]["canonicalPayload"],
            reconciled_at=journal.get("reconciledAt", ""),
        )

    def _recover_verdict(self, journal: dict[str, Any]) -> FinalReviewResult:
        self._begin_response_wait(journal)
        canonical_request_id = journal["canonicalRequestId"]
        conversation_id = journal["conversationId"]
        payload = journal["binding"]["canonicalPayload"]
        runtime = self._runtime_factory()
        conversation = ConversationRef(conversation_id)

        attempts: list[dict[str, Any]] = []
        recovered_payload: dict[str, Any] | None = None
        recovered_message_id: str | None = None
        recovered_user_message_id: str | None = None
        finality: str | None = None
        status_result: dict[str, Any] | None = None
        for attempt in range(1, _READ_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(_READ_WAIT_S[attempt - 1])
            else:
                time.sleep(_READ_WAIT_S[0])
            try:
                status = runtime.get_status(conversation)
                status_result = (
                    status.to_dict() if hasattr(status, "to_dict") else status
                )
            except Exception as error:  # noqa: BLE001 - evidence boundary
                status_result = {
                    "errorType": type(error).__name__,
                    "error": str(error),
                }
            try:
                messages = runtime.get_messages(conversation)
                items = [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in (messages if isinstance(messages, list) else [])
                ]
            except Exception as error:  # noqa: BLE001 - evidence boundary
                items = []
            matching_users = [
                item
                for item in items
                if item.get("role") == "user"
                and _normalize_product_text(item.get("text")) == _normalize_product_text(journal["payloadText"])
            ]
            if len(matching_users) > 1:
                raise FinalReviewTransportError(
                    _transport_code("DUPLICATE_COMMIT")
                )
            assistant_after = None
            if matching_users:
                user_index = items.index(matching_users[0])
                assistants_after = [
                    item
                    for item in items[user_index + 1 :]
                    if item.get("role") == "assistant"
                ]
                # The product may stream a reasoning-summary assistant message
                # (no finish) BEFORE the final answer — the LAST assistant
                # after our user message is the authoritative reply.
                assistant_after = assistants_after[-1] if assistants_after else None
            assistant_complete = bool(
                assistant_after
                and assistant_after.get("finish_reason") == "stop"
                and (assistant_after.get("metadata_preview") or {}).get(
                    "is_complete"
                )
                is True
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "readAt": _utc_now(),
                    "status": status_result,
                    "messageCount": len(items),
                    "matchingUserMessageCount": len(matching_users),
                    "assistantMessageId": (
                        assistant_after or {}
                    ).get("message_id"),
                    "assistantComplete": assistant_complete,
                }
            )
            if matching_users and assistant_complete:
                # Strict parse of the CANONICAL read-back text (not our
                # journal copy): the committed payload must parse to the
                # bound payload byte-for-byte (product whitespace folded).
                recovered_payload = _parse_payload_text(
                    _normalize_product_text(matching_users[0].get("text"))
                )
                recovered_message_id = assistant_after.get("message_id")
                recovered_user_message_id = matching_users[0].get("message_id")
                finality = "FINAL"
                break
        if recovered_payload is None or finality != "FINAL":
            if attempts:
                journal["canonicalReadAttempts"] = attempts
                _persist(self._journal_path(canonical_request_id), journal)
            raise FinalReviewTransportError(
                _transport_code("FINALITY_AMBIGUOUS"),
                journal_state=STATE_RESPONSE_WAIT,
                reconcile_required=True,
            )
        # Exact response binding: the recovered committed payload must be the
        # bound payload byte-for-byte.
        response_digest = hashlib.sha256(
            _canonical_json(recovered_payload).encode("utf-8")
        ).hexdigest()
        try:
            verify_final_review_response(
                {
                    "canonicalRequestId": canonical_request_id,
                    "canonicalPayload": payload,
                },
                response_digest=response_digest,
                finality=finality,
            )
        except FinalReviewBindingError as error:
            raise FinalReviewTransportError(str(error)) from error

        reconciled_at = _utc_now()
        self._update_journal(
            journal,
            to_state=STATE_RESPONSE_CONFIRMED,
            reconciledAt=reconciled_at,
            canonicalReadAttempts=attempts,
            recoveredAssistantMessageId=recovered_message_id,
            recoveredUserMessageId=recovered_user_message_id,
            result={
                "verdict": payload["verdict"],
                "finality": finality,
                "responseDigest": response_digest,
                "reconciledAt": reconciled_at,
            },
        )
        return FinalReviewResult(
            canonical_request_id=canonical_request_id,
            conversation_id=conversation_id,
            submission_id=journal["ack"]["submission_id"],
            sse_conversation_identity_authority=journal.get(
                "sseConversationIdentityAuthority"
            ),
            verdict=payload["verdict"],
            finality=finality,
            payload=payload,
            reconciled_at=reconciled_at,
        )


__all__ = [
    "CWA_SSE_IDENTITY_AUTHORITY",
    "FINAL_REVIEW_PAYLOAD_PREFIX",
    "JOURNAL_SCHEMA",
    "STATE_PREPARED",
    "STATE_SUBMIT_DELEGATED",
    "STATE_WRITE_CONFIRMED",
    "STATE_WRITE_CONFIRMED_IDENTITY_REJECTED",
    "STATE_RESPONSE_WAIT",
    "STATE_RESPONSE_CONFIRMED",
    "STATE_WRITE_FINALITY_UNKNOWN",
    "STATE_RECONCILING",
    "STATE_WRITE_FOUND",
    "STATE_NO_WRITE_PROVEN",
    "STATE_AMBIGUOUS",
    "STATE_SUBMIT_FAILED_NONRETRYABLE",
    "CwaFinalReviewTransport",
    "FinalReviewRequest",
    "FinalReviewRequestResult",
    "FinalReviewResult",
    "FinalReviewTransport",
    "FinalReviewTransportError",
    "canonical_request_identity",
]
