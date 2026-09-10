"""Gate C: deterministic final-review transport binding fixture.

Proves exact binding (repository, issueNumber, pullRequestNumber, headSha,
evidence digest) and the required fail-closed matrix: stale headSha, wrong
Issue/PR, malformed verdict, replay, ambiguous finality, mismatched response.
No production issue/PR data; no network; no live write.
"""

import pytest

from chatgpt_web_adapter.final_review_binding_contract import (
    FINAL_REVIEW_FINALITY_STATES,
    bind_final_review_request,
    canonical_request_identity,
    verify_final_review_response,
    FinalReviewBindingError,
)

REPO = "fixture/repo"
ISSUE = 12
PR = 34
HEAD = "a" * 40
DIGEST = "b" * 64
VERDICT = "APPROVE"


def _bind(**overrides):
    kwargs = dict(
        repository=REPO,
        issue_number=ISSUE,
        pull_request_number=PR,
        head_sha=HEAD,
        evidence_digest=DIGEST,
        verdict=VERDICT,
    )
    kwargs.update(overrides)
    return bind_final_review_request(
        kwargs["repository"],
        kwargs["issue_number"],
        kwargs["pull_request_number"],
        kwargs["head_sha"],
        kwargs["evidence_digest"],
        kwargs["verdict"],
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        current_head_sha=HEAD,
        known_request_ids=set(),
    )


def _reason(error: FinalReviewBindingError) -> str:
    return str(error).rsplit(":", 1)[-1]


def test_exact_binding_is_deterministic_and_verbatim() -> None:
    binding = _bind()
    assert binding["canonicalPayload"]["repository"] == REPO
    assert binding["canonicalPayload"]["issueNumber"] == ISSUE
    assert binding["canonicalPayload"]["pullRequestNumber"] == PR
    assert binding["canonicalPayload"]["headSha"] == HEAD
    assert binding["canonicalPayload"]["evidenceDigest"] == DIGEST
    assert (
        binding["canonicalRequestId"]
        == canonical_request_identity(binding["canonicalPayload"])
    )
    assert (
        verify_final_review_response(
            binding, response_digest=binding["canonicalRequestId"], finality="FINAL"
        )
        == {"verified": True, "canonicalRequestId": binding["canonicalRequestId"]}
    )
    assert FINAL_REVIEW_FINALITY_STATES == {"FINAL"}


def test_stale_head_sha_fails_closed() -> None:
    with pytest.raises(FinalReviewBindingError) as exc:
        bind_final_review_request(
            REPO, ISSUE, PR, HEAD, DIGEST, VERDICT,
            expected_repository=REPO,
            expected_issue_number=ISSUE,
            expected_pull_request_number=PR,
            current_head_sha="c" * 40,
            known_request_ids=set(),
        )
    assert _reason(exc.value) == "HEAD_SHA_STALE"


def test_wrong_issue_and_pr_fail_closed() -> None:
    with pytest.raises(FinalReviewBindingError) as exc:
        bind_final_review_request(
            REPO, ISSUE, PR, HEAD, DIGEST, VERDICT,
            expected_repository=REPO,
            expected_issue_number=ISSUE + 1,
            expected_pull_request_number=PR,
            current_head_sha=HEAD,
            known_request_ids=set(),
        )
    assert _reason(exc.value) == "TARGET_MISMATCH"
    with pytest.raises(FinalReviewBindingError) as exc:
        bind_final_review_request(
            REPO, ISSUE, PR + 1, HEAD, DIGEST, VERDICT,
            expected_repository=REPO,
            expected_issue_number=ISSUE,
            expected_pull_request_number=PR,
            current_head_sha=HEAD,
            known_request_ids=set(),
        )
    assert _reason(exc.value) == "TARGET_MISMATCH"
    with pytest.raises(FinalReviewBindingError) as exc:
        bind_final_review_request(
            "fixture/other", ISSUE, PR, HEAD, DIGEST, VERDICT,
            expected_repository=REPO,
            expected_issue_number=ISSUE,
            expected_pull_request_number=PR,
            current_head_sha=HEAD,
            known_request_ids=set(),
        )
    assert _reason(exc.value) == "TARGET_MISMATCH"


def test_malformed_verdict_fails_closed() -> None:
    for bad in ("LGTM!!!", "", None, "approve", "APPROVE ", "SHIP_IT"):
        with pytest.raises(FinalReviewBindingError) as exc:
            _bind(verdict=bad)
        assert _reason(exc.value) == "VERDICT_MALFORMED"


def test_malformed_fields_fail_closed() -> None:
    for field, bad in (
        ("head_sha", "XYZ"),
        ("head_sha", "a" * 39),
        ("evidence_digest", "b" * 63),
        ("evidence_digest", None),
        ("repository", ""),
        ("repository", None),
        ("issue_number", 0),
        ("issue_number", "12"),
        ("pull_request_number", -1),
    ):
        with pytest.raises(FinalReviewBindingError) as exc:
            _bind(**{field: bad})
        assert "FIELD_MALFORMED" in str(exc.value), field


def test_replay_fails_closed() -> None:
    binding = _bind()
    with pytest.raises(FinalReviewBindingError) as exc:
        bind_final_review_request(
            REPO, ISSUE, PR, HEAD, DIGEST, VERDICT,
            expected_repository=REPO,
            expected_issue_number=ISSUE,
            expected_pull_request_number=PR,
            current_head_sha=HEAD,
            known_request_ids={binding["canonicalRequestId"]},
        )
    assert _reason(exc.value) == "REPLAY"


def test_ambiguous_finality_fails_closed_after_delivery() -> None:
    binding = _bind()
    with pytest.raises(FinalReviewBindingError) as exc:
        verify_final_review_response(
            binding, response_digest=binding["canonicalRequestId"], finality=None
        )
    assert _reason(exc.value) == "FINALITY_AMBIGUOUS"
    with pytest.raises(FinalReviewBindingError) as exc:
        verify_final_review_response(
            binding, response_digest=binding["canonicalRequestId"], finality="PENDING"
        )
    assert _reason(exc.value) == "FINALITY_AMBIGUOUS"


def test_mismatched_response_fails_closed() -> None:
    binding = _bind()
    with pytest.raises(FinalReviewBindingError) as exc:
        verify_final_review_response(
            binding, response_digest="c" * 64, finality="FINAL"
        )
    assert _reason(exc.value) == "RESPONSE_MISMATCH"
