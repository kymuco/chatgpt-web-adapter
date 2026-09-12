"""Gate: production FinalReviewTransport deterministic regressions.

Full fail-closed matrix with a fake runtime (no network, no live write):
exact binding PASS; stale head / wrong target / malformed verdict / replay /
identity-authority-absent / route-only identity / ambiguous finality /
response mismatch / duplicate commit FAIL_CLOSED; restart reconciliation with
zero resend; duplicate submission impossible.
"""

import json

import pytest

from chatgpt_web_adapter import final_review_transport as frt
from chatgpt_web_adapter.final_review_binding_contract import (
    FinalReviewBindingError,
)
from chatgpt_web_adapter.final_review_transport import (
    CwaFinalReviewTransport,
    FinalReviewRequest,
    FinalReviewTransportError,
)

REPO = "fixture/repo"
ISSUE = 12
PR = 34
HEAD = "a" * 40
DIGEST = "b" * 64
VERDICT = "APPROVE"
AUTHORITY = "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS"


@pytest.fixture(autouse=True)
def _no_read_waits(monkeypatch):
    monkeypatch.setattr(frt, "_READ_WAIT_S", (0.0, 0.0, 0.0))


class FakeAck:
    def __init__(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    def to_dict(self) -> dict:
        return {
            "submission_id": "sub-1",
            "transport": "browser-owned",
            "conversation_id": self._conversation_id,
            "turn_lifecycle_id": "tl-1",
            "accepted_at_ms": 1,
        }


class FakeMessage(dict):
    def to_dict(self) -> dict:
        return dict(self)


class FakeRuntime:
    def __init__(
        self,
        *,
        conversation_id: str = "6aa2a05d-dad4-83ec-b25d-803ba37fe79e",
        authority: str | None = AUTHORITY,
        assistant_complete: bool = True,
        duplicate_user: bool = False,
        submitted_text: str | None = None,
    ) -> None:
        self.submit_calls = 0
        self.conversation_id = conversation_id
        self.authority = authority
        self.assistant_complete = assistant_complete
        self.duplicate_user = duplicate_user
        self.submitted_text = submitted_text

    def submit(self, text, *, timeout, poll_interval, on_event):
        self.submit_calls += 1
        self.submitted_text = text
        on_event({"type": "browser_native_turn_started", "submission_id": "sub-1"})
        on_event(
            {
                "type": "browser_native_write_completed",
                "submission_id": "sub-1",
                "conversation_id": self.conversation_id,
                "sse_conversation_identity_authority": self.authority,
                "sse_conversation_identity_record_count": 7,
                "sse_conversation_identity_distinct_count": 1,
            }
        )
        return FakeAck(self.conversation_id)

    def _messages(self):
        items = [
            FakeMessage(
                role="user", text=self.submitted_text, message_id="u-1"
            )
        ]
        if self.duplicate_user:
            items.append(
                FakeMessage(role="user", text=self.submitted_text, message_id="u-2")
            )
        items.append(
            FakeMessage(
                role="assistant",
                message_id="a-1",
                finish_reason="stop" if self.assistant_complete else None,
                metadata_preview={"is_complete": self.assistant_complete},
            )
        )
        return items

    def get_status(self, conversation):
        return {
            "status": "user_last_message",
            "message_id": "u-1",
            "role": "user",
        }

    def get_messages(self, conversation):
        return self._messages()


def _request(**overrides) -> FinalReviewRequest:
    kwargs = dict(
        repository=REPO,
        issue_number=ISSUE,
        pull_request_number=PR,
        head_sha=HEAD,
        evidence_digest=DIGEST,
        verdict=VERDICT,
        current_head_sha=HEAD,
    )
    kwargs.update(overrides)
    return FinalReviewRequest(**kwargs)


def _transport(runtime, tmp_path) -> CwaFinalReviewTransport:
    return CwaFinalReviewTransport(
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        runtime_factory=lambda: runtime,
        durable_store=tmp_path / "store",
    )


def _code(error: Exception) -> str:
    return str(error).rsplit(":", 1)[-1]


def test_exact_binding_happy_path(tmp_path) -> None:
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    result = transport.submit_final_review(_request())
    assert result.canonical_request_id
    assert result.conversation_id == runtime.conversation_id
    assert result.submission_id == "sub-1"
    assert result.verdict == VERDICT
    assert result.finality == "FINAL"
    assert (
        result.sse_conversation_identity_authority == AUTHORITY
    )
    assert runtime.submit_calls == 1
    journal = json.loads(
        (tmp_path / "store" / f"{result.canonical_request_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert journal["state"] == "RESPONSE_CONFIRMED"
    assert journal["liveWriteCount"] == 1
    assert (
        journal["sseConversationIdentityAuthority"] == AUTHORITY
    )
    assert result.payload["repository"] == REPO
    assert result.payload["issueNumber"] == ISSUE
    assert result.payload["pullRequestNumber"] == PR
    assert result.payload["headSha"] == HEAD
    assert result.payload["evidenceDigest"] == DIGEST


def test_identity_authority_absent_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(authority=None)
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review(_request())
    assert _code(exc.value) == "IDENTITY_AUTHORITY_ABSENT"
    assert runtime.submit_calls == 1  # never retried


def test_route_only_identity_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(conversation_id="WEB:0347d734-e2bc-42cb-90eb-1b19ee3575cd")
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review(_request())
    assert _code(exc.value) == "IDENTITY_ROUTE_ONLY"
    assert runtime.submit_calls == 1  # never retried, never stripped


def test_stale_head_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewBindingError) as exc:
        transport.submit_final_review(
            _request(head_sha=HEAD, current_head_sha="c" * 40)
        )
    assert _code(exc.value) == "HEAD_SHA_STALE"
    assert runtime.submit_calls == 0
    assert not (tmp_path / "store").exists() or not list(
        (tmp_path / "store").glob("*.json")
    )


def test_wrong_target_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewBindingError) as exc:
        transport.submit_final_review(_request(issue_number=ISSUE + 1))
    assert _code(exc.value) == "TARGET_MISMATCH"
    assert runtime.submit_calls == 0
    with pytest.raises(FinalReviewBindingError) as exc:
        transport.submit_final_review(_request(pull_request_number=PR + 1))
    assert _code(exc.value) == "TARGET_MISMATCH"
    with pytest.raises(FinalReviewBindingError) as exc:
        transport.submit_final_review(_request(repository="fixture/other"))
    assert _code(exc.value) == "TARGET_MISMATCH"
    assert runtime.submit_calls == 0


def test_malformed_verdict_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewBindingError) as exc:
        transport.submit_final_review(_request(verdict="LGTM!!!"))
    assert _code(exc.value) == "VERDICT_MALFORMED"
    assert runtime.submit_calls == 0


def test_replay_continues_idempotently(tmp_path) -> None:
    # Issue #169: a replay of the SAME immutable identity never re-issues the
    # write: the terminal journal replays the stored result with zero writes.
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    result = transport.submit_final_review(_request())
    assert runtime.submit_calls == 1
    replay = transport.submit_final_review(_request())
    assert runtime.submit_calls == 1  # second bind never reached the write
    assert replay.canonical_request_id == result.canonical_request_id
    assert replay.verdict == VERDICT


def test_duplicate_submission_impossible(tmp_path) -> None:
    # First submission's reconciliation never completes -> journal stays
    # WRITE_ACKNOWLEDGED (active). A different request must be refused.
    runtime_stuck = FakeRuntime(assistant_complete=False)
    transport = _transport(runtime_stuck, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review(_request())
    assert _code(exc.value) == "FINALITY_AMBIGUOUS"
    assert runtime_stuck.submit_calls == 1

    runtime_next = FakeRuntime()
    transport_next = _transport(runtime_next, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport_next.submit_final_review(_request(evidence_digest="c" * 64))
    assert _code(exc.value) == "ACTIVE_SUBMISSION_EXISTS"
    assert runtime_next.submit_calls == 0


def test_ambiguous_finality_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(assistant_complete=False)
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review(_request())
    assert _code(exc.value) == "FINALITY_AMBIGUOUS"
    journal_files = list((tmp_path / "store").glob("*.json"))
    journal = json.loads(journal_files[0].read_text(encoding="utf-8"))
    # RESPONSE_WAIT is re-enterable by reconcile: reads again, NEVER rewrites.
    assert journal["state"] == "RESPONSE_WAIT"


def test_response_mismatch_fails_closed(tmp_path) -> None:
    # Tampered durable payload text: canonical read-back matches the tampered
    # text but its digest no longer equals the bound canonical request id.
    transport = _transport(FakeRuntime(), tmp_path)
    from chatgpt_web_adapter.final_review_binding_contract import (
        bind_final_review_request,
    )
    bound = bind_final_review_request(
        REPO, ISSUE, PR, HEAD, DIGEST, VERDICT,
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        current_head_sha=HEAD,
        known_request_ids=set(),
    )
    tampered_payload = dict(bound["canonicalPayload"], verdict="REQUEST_CHANGES")
    journal = {
        "schema": 1,
        "state": "WRITE_ACKNOWLEDGED",
        "canonicalRequestId": bound["canonicalRequestId"],
        "binding": bound,
        "payloadText": f"{frt.FINAL_REVIEW_PAYLOAD_PREFIX} "
        + json.dumps(
            tampered_payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ),
        "conversationId": "6aa2a05d-dad4-83ec-b25d-803ba37fe79e",
        "sseConversationIdentityAuthority": AUTHORITY,
        "ack": {"submission_id": "sub-1"},
    }
    (tmp_path / "store").mkdir(parents=True, exist_ok=True)
    (tmp_path / "store" / f"{bound['canonicalRequestId']}.json").write_text(
        json.dumps(journal), encoding="utf-8"
    )
    runtime = FakeRuntime(submitted_text=journal["payloadText"])
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.reconcile_final_review(bound["canonicalRequestId"])
    assert str(exc.value).endswith("RESPONSE_MISMATCH")
    assert runtime.submit_calls == 0


def test_duplicate_commit_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(duplicate_user=True)
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review(_request())
    assert _code(exc.value) == "DUPLICATE_COMMIT"


def test_restart_reconciliation_zero_resend(tmp_path) -> None:
    # Process 1: write + durable ACK, reconciliation never completes.
    runtime_1 = FakeRuntime(assistant_complete=False)
    transport_1 = _transport(runtime_1, tmp_path)
    with pytest.raises(FinalReviewTransportError):
        transport_1.submit_final_review(_request())
    assert runtime_1.submit_calls == 1
    journal_files = list((tmp_path / "store").glob("*.json"))
    canonical_request_id = journal_files[0].stem

    # Process 2 (fresh transport/runtime): reconcile from durable evidence.
    journal_data = json.loads(journal_files[0].read_text(encoding="utf-8"))
    runtime_2 = FakeRuntime(submitted_text=journal_data["payloadText"])
    transport_2 = _transport(runtime_2, tmp_path)
    result = transport_2.reconcile_final_review(canonical_request_id)
    assert runtime_2.submit_calls == 0  # zero resend
    assert result.canonical_request_id == canonical_request_id
    assert result.finality == "FINAL"
    assert result.verdict == VERDICT
    assert result.sse_conversation_identity_authority == AUTHORITY
    assert result.payload["headSha"] == HEAD


def test_reconcile_prepared_requires_ack_fails_closed(tmp_path) -> None:
    from chatgpt_web_adapter.final_review_binding_contract import (
        bind_final_review_request,
    )
    bound = bind_final_review_request(
        REPO, ISSUE, PR, HEAD, DIGEST, VERDICT,
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        current_head_sha=HEAD,
        known_request_ids=set(),
    )
    (tmp_path / "store").mkdir(parents=True, exist_ok=True)
    journal = {
        "schema": 3,
        "stateMachineVersion": 3,
        "mode": "VERDICT",
        "state": "PREPARED",
        "canonicalRequestId": bound["canonicalRequestId"],
        "binding": bound,
        "payloadText": frt._payload_text(bound["canonicalPayload"]),
        "conversationId": None,
    }
    (tmp_path / "store" / f"{bound['canonicalRequestId']}.json").write_text(
        json.dumps(journal), encoding="utf-8"
    )
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.reconcile_final_review(bound["canonicalRequestId"])
    assert _code(exc.value) == "RECONCILIATION_REQUIRES_ACK"
    assert runtime.submit_calls == 0



def test_malformed_payload_text_fails_closed() -> None:
    with pytest.raises(FinalReviewTransportError) as exc:
        frt._parse_payload_text("FINAL_REVIEW_VERDICT_V1 not-json")
    assert _code(exc.value) == "PAYLOAD_MALFORMED"
    with pytest.raises(FinalReviewTransportError) as exc:
        frt._parse_payload_text('FINAL_REVIEW_VERDICT_V1 { "a": 1}')
    assert _code(exc.value) == "PAYLOAD_MALFORMED"


def test_typed_authority_propagation_wired() -> None:
    from pathlib import Path

    src = Path(frt.__file__).resolve().parent
    provider = (src / "browser_native_provider.py").read_text(encoding="utf-8")
    client = (src / "browser_native_client.py").read_text(encoding="utf-8")
    assert "sse_conversation_identity_authority: str | None = None" in provider
    assert 'response.get("sseConversationIdentityAuthority")' in provider
    assert (
        "sse_conversation_identity_authority=turn.sse_conversation_identity_authority"
        in client
    )
