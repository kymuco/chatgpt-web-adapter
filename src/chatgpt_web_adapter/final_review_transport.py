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
  resent merely because the final response was lost.

``ponytail:`` ceiling — replay set is the durable-store directory scan; the
upgrade path is an external ledger if multi-process submission is ever needed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .final_review_binding_contract import (
    bind_final_review_request,
    canonical_request_identity,
    verify_final_review_response,
    FinalReviewBindingError,
)
from .types import ConversationRef

CWA_SSE_IDENTITY_AUTHORITY = "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS"
FINAL_REVIEW_PAYLOAD_PREFIX = "FINAL_REVIEW_VERDICT_V1"
FINAL_REVIEW_TRANSPORT_ERROR = "FINAL_REVIEW_TRANSPORT_REJECTED"
_READ_ATTEMPTS = 3
_READ_WAIT_S = (15.0, 30.0, 30.0)
_ACTIVE_STATES = frozenset(
    {"BOUND", "WRITE_ACKNOWLEDGED", "WRITE_ACKNOWLEDGED_IDENTITY_REJECTED"}
)


class FinalReviewTransportError(Exception):
    """Fail-closed transport rejection with a stable ``:CODE`` message."""


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
    ) -> None:
        self.repository = repository
        self.issue_number = issue_number
        self.pull_request_number = pull_request_number
        self.head_sha = head_sha
        self.evidence_digest = evidence_digest
        self.verdict = verdict
        self.current_head_sha = current_head_sha


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
    """Composer-owned whitespace normalization: the product editor turns
    regular spaces into non-breaking spaces (and may use CRLF). Equality and
    digest checks run on this canonical form — exact binding modulo
    product-owned normalization, never a content rewrite."""
    return (
        str(text)
        .replace("\u00a0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _persist(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


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

    def _assert_no_active_submission(self, canonical_request_id: str) -> None:
        for path in self._durable_store.glob("*.json"):
            if path.stem == canonical_request_id or len(path.stem) != 64:
                continue
            try:
                journal = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if journal.get("state") in _ACTIVE_STATES:
                raise FinalReviewTransportError(
                    _transport_code("ACTIVE_SUBMISSION_EXISTS")
                )

    def submit_final_review(self, request: FinalReviewRequest) -> FinalReviewResult:
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
        )
        canonical_request_id = binding["canonicalRequestId"]
        self._assert_no_active_submission(canonical_request_id)
        journal = self._bound_journal(binding, mode="VERDICT")
        journal["payloadText"] = _payload_text(binding["canonicalPayload"])
        self._protected_write(journal)
        return self._recover_from_ack(journal)

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
            )
        except FinalReviewBindingError as error:
            if str(error).rsplit(":", 1)[-1] != "REPLAY":
                raise
            # Same request identity already bound: continue from durable
            # evidence with ZERO writes (idempotent re-entry).
            payload = {
                "repository": repository,
                "issueNumber": issue_number,
                "pullRequestNumber": pull_request_number,
                "headSha": head_sha,
                "evidenceDigest": evidence_digest,
            }
            canonical_request_id = canonical_request_identity(payload)
            path = self._journal_path(canonical_request_id)
            if not path.is_file():
                raise
            journal = json.loads(path.read_text(encoding="utf-8"))
            if journal.get("state") == "RECONCILED":
                return self._request_result_from_journal(journal)
            if journal.get("state") == "WRITE_ACKNOWLEDGED":
                return self._recover_request(journal)
            raise
        canonical_request_id = binding["canonicalRequestId"]
        self._assert_no_active_submission(canonical_request_id)
        journal = self._bound_journal(binding, mode="REQUEST")
        journal["payloadText"] = prompt
        self._protected_write(journal)
        return self._recover_from_ack(journal)

    def _bound_journal(self, binding: dict[str, Any], *, mode: str) -> dict[str, Any]:
        journal: dict[str, Any] = {
            "schema": 2,
            "probe": "FINAL_REVIEW_TRANSPORT",
            "mode": mode,
            "state": "BOUND",
            "boundAt": _utc_now(),
            "canonicalRequestId": binding["canonicalRequestId"],
            "binding": binding,
            "liveWriteCount": 0,
        }
        # Durable BEFORE external mutation: replay/duplicate rejection and
        # crash reconciliation both key off this file.
        _persist(self._journal_path(binding["canonicalRequestId"]), journal)
        return journal

    def _protected_write(self, journal: dict[str, Any]) -> None:
        """Exactly one browser-owned write + durable identity-gated ACK.

        The write MAY have committed even when this method raises: the durable
        ACK + typed identity evidence are persisted BEFORE any fail-closed
        gate, so reconciliation never loses the write evidence.
        """
        canonical_request_id = journal["canonicalRequestId"]
        events: list[dict[str, Any]] = []
        try:
            runtime = self._runtime_factory()
            ack = runtime.submit(
                journal["payloadText"],
                timeout=240.0,
                poll_interval=0.5,
                on_event=events.append,
            )
        except Exception as error:
            journal["state"] = "SUBMIT_FAILED_NONRETRYABLE"
            journal["submitErrorType"] = type(error).__name__
            journal["submitError"] = str(error)
            journal["finishedAt"] = _utc_now()
            _persist(self._journal_path(canonical_request_id), journal)
            raise FinalReviewTransportError(
                _transport_code("SUBMIT_FAILED_NONRETRYABLE")
            ) from error

        ack_dict = ack.to_dict() if hasattr(ack, "to_dict") else dict(ack)
        conversation_id = ack_dict.get("conversation_id")
        authority = None
        record_count = None
        distinct_count = None
        for event in events:
            if event.get("type") == "browser_native_write_completed":
                authority = event.get("sse_conversation_identity_authority")
                record_count = event.get("sse_conversation_identity_record_count")
                distinct_count = event.get(
                    "sse_conversation_identity_distinct_count"
                )
                break
        # The write MAY have committed: persist the durable ACK + typed
        # identity evidence BEFORE any fail-closed gate, so reconciliation
        # never loses the write evidence.
        journal.update(
            {
                "state": "WRITE_ACKNOWLEDGED",
                "writeAcknowledgedAt": _utc_now(),
                "ack": ack_dict,
                "conversationId": conversation_id,
                "sseConversationIdentityAuthority": authority,
                "sseConversationIdentityRecordCount": record_count,
                "sseConversationIdentityDistinctCount": distinct_count,
                "liveWriteCount": 1,
                "writeEvents": [
                    event
                    for event in events
                    if event.get("type")
                    in (
                        "browser_native_turn_started",
                        "browser_native_write_completed",
                    )
                ],
            }
        )
        identity_rejection = None
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            identity_rejection = "IDENTITY_AUTHORITY_ABSENT"
        elif conversation_id.startswith("WEB:"):
            identity_rejection = "IDENTITY_ROUTE_ONLY"
        elif authority != CWA_SSE_IDENTITY_AUTHORITY:
            identity_rejection = "IDENTITY_AUTHORITY_ABSENT"
        if identity_rejection is not None:
            journal["state"] = "WRITE_ACKNOWLEDGED_IDENTITY_REJECTED"
            journal["identityRejection"] = identity_rejection
            _persist(self._journal_path(canonical_request_id), journal)
            raise FinalReviewTransportError(
                _transport_code(identity_rejection)
            )
        # Durable ACK BEFORE any finality attempt.
        _persist(self._journal_path(canonical_request_id), journal)

    def reconcile_final_review(
        self, canonical_request_id: str
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        path = self._journal_path(canonical_request_id)
        if not path.is_file():
            raise FinalReviewTransportError(_transport_code("UNKNOWN_REQUEST"))
        journal = json.loads(path.read_text(encoding="utf-8"))
        if journal.get("state") == "RECONCILED":
            if journal.get("mode") == "REQUEST":
                return self._request_result_from_journal(journal)
            stored = journal.get("result") or {}
            return FinalReviewResult(
                canonical_request_id=journal["canonicalRequestId"],
                conversation_id=journal["conversationId"],
                submission_id=journal["ack"]["submission_id"],
                sse_conversation_identity_authority=journal.get(
                    "sseConversationIdentityAuthority"
                ),
                verdict=stored.get("verdict", journal["binding"]["canonicalPayload"]["verdict"]),
                finality="FINAL",
                payload=journal["binding"]["canonicalPayload"],
                reconciled_at=stored.get("reconciledAt", journal.get("finishedAt", "")),
            )
        if journal.get("state") == "WRITE_ACKNOWLEDGED_IDENTITY_REJECTED":
            raise FinalReviewTransportError(
                _transport_code("IDENTITY_REJECTED_NOT_RECONCILABLE")
            )
        if journal.get("state") != "WRITE_ACKNOWLEDGED":
            raise FinalReviewTransportError(
                _transport_code("RECONCILIATION_REQUIRES_ACK")
            )
        return self._recover_from_ack(journal)

    def _recover_from_ack(
        self, journal: dict[str, Any]
    ) -> "FinalReviewResult | FinalReviewRequestResult":
        if journal.get("mode") == "REQUEST":
            return self._recover_request(journal)
        return self._recover_verdict(journal)

    def _recover_request(
        self, journal: dict[str, Any]
    ) -> "FinalReviewRequestResult":
        canonical_request_id = journal["canonicalRequestId"]
        conversation_id = journal["conversationId"]
        evidence_digest = journal["binding"]["canonicalPayload"]["evidenceDigest"]
        prompt = journal["payloadText"]
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
            matching_users = [
                item
                for item in items
                if item.get("role") == "user" and _normalize_product_text(item.get("text")) == _normalize_product_text(prompt)
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
                # Exact request binding modulo product-owned whitespace
                # normalization: the canonical read-back of the committed
                # user message must equal the durable prompt text on the
                # normalized form (nbsp/CRLF folds), else fail closed.
                recovered_user_text = _normalize_product_text(
                    matching_users[0].get("text")
                )
                if recovered_user_text != _normalize_product_text(prompt):
                    raise FinalReviewTransportError(
                        _transport_code("RESPONSE_MISMATCH")
                    )
                recovered_message_id = assistant_after.get("message_id")
                recovered_user_message_id = matching_users[0].get("message_id")
                text_value = assistant_after.get("text")
                reply_text = text_value if isinstance(text_value, str) else None
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
            raise FinalReviewTransportError(_transport_code("FINALITY_AMBIGUOUS"))
        if reply_text is None or not reply_text.strip():
            # Unambiguous finality with an empty reply body is not a verdict;
            # the journal stays WRITE_ACKNOWLEDGED so a later reconcile can
            # re-read without any new write.
            raise FinalReviewTransportError(_transport_code("REPLY_EMPTY"))
        journal.update(
            {
                "state": "RECONCILED",
                "reconciledAt": _utc_now(),
                "canonicalReadAttempts": attempts,
                "recoveredAssistantMessageId": recovered_message_id,
                "recoveredUserMessageId": recovered_user_message_id,
                "replyText": reply_text,
                "replyModelSlug": model_slug,
                "result": {
                    "finality": finality,
                    "replyText": reply_text,
                    "replyModelSlug": model_slug,
                },
            }
        )
        _persist(self._journal_path(canonical_request_id), journal)
        return self._request_result_from_journal(journal)

    def _request_result_from_journal(
        self, journal: dict[str, Any]
    ) -> "FinalReviewRequestResult":
        return FinalReviewRequestResult(
            canonical_request_id=journal["canonicalRequestId"],
            conversation_id=journal["conversationId"],
            submission_id=journal["ack"]["submission_id"],
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
            raise FinalReviewTransportError(
                _transport_code("FINALITY_AMBIGUOUS")
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
        journal.update(
            {
                "state": "RECONCILED",
                "reconciledAt": reconciled_at,
                "canonicalReadAttempts": attempts,
                "recoveredAssistantMessageId": recovered_message_id,
                "recoveredUserMessageId": recovered_user_message_id,
                "result": {
                    "verdict": payload["verdict"],
                    "finality": finality,
                    "responseDigest": response_digest,
                    "reconciledAt": reconciled_at,
                },
            }
        )
        _persist(self._journal_path(canonical_request_id), journal)
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
    "CwaFinalReviewTransport",
    "FinalReviewRequest",
    "FinalReviewRequestResult",
    "FinalReviewResult",
    "FinalReviewTransport",
    "FinalReviewTransportError",
    "canonical_request_identity",
]
