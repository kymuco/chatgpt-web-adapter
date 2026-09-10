"""Request-mode + runtime-readiness regressions (deterministic, no network).

Covers the Soc_brain wiring surface: submit_final_review_request (exact
request binding, reply recovery, duplicate/ambiguous/replay fail-closed,
idempotent terminal reconcile) and the readiness gate (sentinel parse,
staleness rule, missing sentinel).
"""

import json
import time

import pytest

from chatgpt_web_adapter import final_review_transport as frt
from chatgpt_web_adapter.final_review_binding_contract import (
    FinalReviewBindingError,
)
from chatgpt_web_adapter.final_review_transport import (
    CwaFinalReviewTransport,
    FinalReviewTransportError,
)
from chatgpt_web_adapter import browser_runtime_readiness as readiness

REPO = "duongpdddic-droid/Soc_brain"
ISSUE = 148
PR = 200
HEAD = "a" * 40
PROMPT = "FINAL REVIEW REQUEST {\"verdict-schema\":\"1\"}\nCanonical packet body."


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
        conversation_id: str = "6aa2b4c7-437c-83ec-a7e9-8d90f5cf4bcb",
        authority: str | None = "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS",
        reply_text: str = '{"verdict":"PASS","binding":{}}',
        assistant_complete: bool = True,
        user_text: str | None = None,
        duplicate_user: bool = False,
    ) -> None:
        self.submit_calls = 0
        self.conversation_id = conversation_id
        self.authority = authority
        self.reply_text = reply_text
        self.assistant_complete = assistant_complete
        self.user_text = user_text
        self.duplicate_user = duplicate_user
        self.submitted_text: str | None = None

    def submit(self, text, *, timeout, poll_interval, on_event):
        self.submit_calls += 1
        self.submitted_text = text
        on_event(
            {
                "type": "browser_native_write_completed",
                "submission_id": "sub-1",
                "conversation_id": self.conversation_id,
                "sse_conversation_identity_authority": self.authority,
                "sse_conversation_identity_record_count": 6,
                "sse_conversation_identity_distinct_count": 1,
            }
        )
        return FakeAck(self.conversation_id)

    def get_status(self, conversation):
        return {"status": "user_last_message", "message_id": "u-1"}

    def get_messages(self, conversation):
        user_text = self.user_text if self.user_text is not None else self.submitted_text
        items = [FakeMessage(role="user", text=user_text, message_id="u-1")]
        if self.duplicate_user:
            items.append(FakeMessage(role="user", text=user_text, message_id="u-2"))
        items.append(
            FakeMessage(
                role="assistant",
                message_id="a-1",
                finish_reason="stop" if self.assistant_complete else None,
                metadata_preview={
                    "is_complete": self.assistant_complete,
                    "model_slug": "gpt-5-6",
                },
                text=self.reply_text,
            )
        )
        return items


def _transport(runtime, tmp_path) -> CwaFinalReviewTransport:
    return CwaFinalReviewTransport(
        expected_repository=REPO,
        expected_issue_number=ISSUE,
        expected_pull_request_number=PR,
        runtime_factory=lambda: runtime,
        durable_store=tmp_path / "store",
    )


def _submit_kwargs(**overrides):
    kwargs = dict(
        prompt=PROMPT,
        repository=REPO,
        issue_number=ISSUE,
        pull_request_number=PR,
        head_sha=HEAD,
        evidence_digest=frt.hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        current_head_sha=HEAD,
    )
    kwargs.update(overrides)
    return kwargs


def _code(error: Exception) -> str:
    return str(error).rsplit(":", 1)[-1]


def test_request_mode_happy_path(tmp_path) -> None:
    runtime = FakeRuntime()
    result = _transport(runtime, tmp_path).submit_final_review_request(
        **_submit_kwargs()
    )
    assert runtime.submit_calls == 1
    assert result.canonical_request_id
    assert result.reply_text == '{"verdict":"PASS","binding":{}}'
    assert result.model_slug == "gpt-5-6"
    assert result.finality == "FINAL"
    assert result.sse_conversation_identity_authority == (
        "REQUEST_BOUND_SSE_CONVERSATION_ID_CONSENSUS"
    )
    assert "verdict" not in result.payload  # request binding omits the verdict
    journal = json.loads(
        (tmp_path / "store" / f"{result.canonical_request_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert journal["state"] == "RECONCILED"
    assert journal["mode"] == "REQUEST"
    assert journal["liveWriteCount"] == 1


def test_request_mode_replay_then_reconcile_is_idempotent(tmp_path) -> None:
    runtime = FakeRuntime()
    transport = _transport(runtime, tmp_path)
    first = transport.submit_final_review_request(**_submit_kwargs())
    # Re-entered finalReview with identical evidence: no second write, the
    # terminal durable result is returned as-is.
    second = transport.submit_final_review_request(**_submit_kwargs())
    assert runtime.submit_calls == 1
    assert second.reply_text == first.reply_text
    assert second.canonical_request_id == first.canonical_request_id


def test_request_mode_duplicate_commit_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(duplicate_user=True)
    with pytest.raises(FinalReviewTransportError) as exc:
        _transport(runtime, tmp_path).submit_final_review_request(
            **_submit_kwargs()
        )
    assert _code(exc.value) == "DUPLICATE_COMMIT"


def test_request_mode_ambiguous_finality_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime(assistant_complete=False)
    with pytest.raises(FinalReviewTransportError) as exc:
        _transport(runtime, tmp_path).submit_final_review_request(
            **_submit_kwargs()
        )
    assert _code(exc.value) == "FINALITY_AMBIGUOUS"


def test_request_mode_empty_reply_fails_closed_and_reconciles(tmp_path) -> None:
    runtime = FakeRuntime(reply_text="   ")
    transport = _transport(runtime, tmp_path)
    with pytest.raises(FinalReviewTransportError) as exc:
        transport.submit_final_review_request(**_submit_kwargs())
    assert _code(exc.value) == "REPLY_EMPTY"
    assert runtime.submit_calls == 1  # no resend
    # The product reply settles later; reconcile recovers it read-only.
    runtime.reply_text = '{"verdict":"REWORK","binding":{}}'
    result = transport.reconcile_final_review(
        json.loads(
            next((tmp_path / "store").glob("*.json")).read_text(encoding="utf-8")
        )["canonicalRequestId"]
    )
    assert result.reply_text == '{"verdict":"REWORK","binding":{}}'
    assert runtime.submit_calls == 1


def test_request_mode_stale_head_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime()
    with pytest.raises(FinalReviewBindingError) as exc:
        _transport(runtime, tmp_path).submit_final_review_request(
            **_submit_kwargs(current_head_sha="c" * 40)
        )
    assert _code(exc.value) == "HEAD_SHA_STALE"
    assert runtime.submit_calls == 0


def test_request_mode_wrong_target_fails_closed(tmp_path) -> None:
    runtime = FakeRuntime()
    with pytest.raises(FinalReviewBindingError) as exc:
        _transport(runtime, tmp_path).submit_final_review_request(
            **_submit_kwargs(issue_number=ISSUE + 1)
        )
    assert _code(exc.value) == "TARGET_MISMATCH"
    assert runtime.submit_calls == 0


# ---- readiness gate -----------------------------------------------------------


def _write_leveldb_log(tmp_path, records: bytes) -> Path:
    storage = (
        tmp_path
        / "User Data"
        / "Profile 1"
        / "Local Extension Settings"
        / "kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "000003.log").write_bytes(records)
    return tmp_path / "User Data"


def test_readiness_missing_sentinel_not_ready(tmp_path) -> None:
    user_data = _write_leveldb_log(tmp_path, b"")
    report = readiness.check_readiness(
        user_data=str(user_data), profile="Profile 1", extension_id="kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    assert report["ready"] is False
    assert "CWA_SENTINEL_MISSING" in report["reasons"]


def test_readiness_stale_sentinel_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(readiness, "bridge_connected", lambda: True)
    old_ms = readiness.newest_source_mtime_ms() - 60_000
    record = (
        f'{readiness.SSE_SENTINEL_KEY}\x00{{"schema":1,"bundle":"worktree-cwa-main-test","loadedAtMs":{old_ms}}}'
    ).encode("latin-1")
    user_data = _write_leveldb_log(tmp_path, record)
    report = readiness.check_readiness(
        user_data=str(user_data), profile="Profile 1", extension_id="kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    assert report["ready"] is False
    assert "CWA_SENTINEL_STALE" in report["reasons"]
    assert report["sentinel"]["loadedAtMs"] == old_ms


def test_readiness_fresh_sentinel_with_connected_bridge(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(readiness, "bridge_connected", lambda: True)
    now_ms = readiness.newest_source_mtime_ms() + 5_000  # newer than any source mtime
    record = (
        f'{readiness.SSE_SENTINEL_KEY}\x00{{"schema":1,"bundle":"worktree-cwa-main-test","loadedAtMs":{now_ms}}}'
    ).encode("latin-1")
    user_data = _write_leveldb_log(tmp_path, record)
    report = readiness.check_readiness(
        user_data=str(user_data), profile="Profile 1", extension_id="kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    assert report["ready"] is True
    assert report["sentinel"]["bundle"] == "worktree-cwa-main-test"


def test_readiness_bundle_mismatch_not_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(readiness, "bridge_connected", lambda: True)
    now_ms = int(time.time() * 1000) + 5_000
    record = (
        f'{readiness.SSE_SENTINEL_KEY}\x00{{"schema":1,"bundle":"other-deployment","loadedAtMs":{now_ms}}}'
    ).encode("latin-1")
    user_data = _write_leveldb_log(tmp_path, record)
    report = readiness.check_readiness(
        user_data=str(user_data), profile="Profile 1", extension_id="kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    assert report["ready"] is False
    assert "CWA_BUNDLE_MISMATCH" in report["reasons"]


def test_readiness_repair_requires_stale_proof(tmp_path, monkeypatch) -> None:
    killed = []
    monkeypatch.setattr(readiness, "_stale_chrome_processes", lambda user_data: killed.append(user_data) or [123])
    monkeypatch.setattr(readiness, "bridge_connected", lambda: True)
    now_ms = int(time.time() * 1000) + 5_000
    record = (
        f'{readiness.SSE_SENTINEL_KEY}\x00{{"schema":1,"bundle":"worktree-cwa-main-test","loadedAtMs":{now_ms}}}'
    ).encode("latin-1")
    user_data = _write_leveldb_log(tmp_path, record)
    report = readiness.repair_stale_runtime(
        user_data=str(user_data), profile="Profile 1", extension_id="kjfnkhajljnkbhikmfijcchenlfglaie"
    )
    assert report["repaired"] is False
    assert report["reason"] == "CWA_REPAIR_REQUIRES_STALE_PROOF"
    assert killed == []  # no process touched without a stale proof
