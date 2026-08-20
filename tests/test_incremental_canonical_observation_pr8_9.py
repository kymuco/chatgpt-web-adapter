from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from chatgpt_web_adapter.incremental_canonical_observation_pr8_9 import (
    RevisionSafeCanonicalTracker,
    StreamCanonicalReconciliation,
    TextObservationKind,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "chatgpt_web_adapter" / "incremental_canonical_observation_pr8_9.py"


def _message(text: str, *, message_id: str = "assistant-new", node_id: str = "node-new"):
    return SimpleNamespace(
        message_id=message_id,
        node_id=node_id,
        text=text,
        finish_reason=None,
    )


def _status(value: str, message_id: str | None = None):
    return SimpleNamespace(status=value, message_id=message_id)


def test_tracker_ignores_baseline_and_classifies_snapshot_delta_revision() -> None:
    tracker = RevisionSafeCanonicalTracker({"assistant-old"})

    assert tracker.observe(
        _message("old", message_id="assistant-old"),
        status=_status("completed", "assistant-old"),
        observed_at_ms=1,
        write_in_flight=True,
    ) is None

    first = tracker.observe(
        _message("The answer is"),
        status=_status("running"),
        observed_at_ms=100,
        write_in_flight=True,
    )
    assert first is not None
    assert first.kind is TextObservationKind.SNAPSHOT
    assert first.pre_final is True
    assert first.write_in_flight is True

    delta = tracker.observe(
        _message("The answer is probably"),
        status=_status("running"),
        observed_at_ms=140,
        write_in_flight=True,
    )
    assert delta is not None
    assert delta.kind is TextObservationKind.DELTA
    assert delta.delta_preview == "probably"
    assert delta.delta_length == len(" probably")

    revision = tracker.observe(
        _message("The result is definitely"),
        status=_status("running"),
        observed_at_ms=180,
        write_in_flight=True,
    )
    assert revision is not None
    assert revision.kind is TextObservationKind.REVISION
    assert revision.delta_preview is None
    assert revision.previous_text_sha256 is not None

    final = tracker.observe(
        _message("The result is definitely final"),
        status=_status("completed", "assistant-new"),
        observed_at_ms=220,
        write_in_flight=False,
    )
    assert final is not None
    assert final.kind is TextObservationKind.DELTA
    assert final.finality_proven_at_observation is True
    assert final.pre_final is False


def test_tracker_deduplicates_identical_snapshots() -> None:
    tracker = RevisionSafeCanonicalTracker()
    message = _message("same text")
    first = tracker.observe(
        message,
        status=_status("running"),
        observed_at_ms=10,
        write_in_flight=True,
    )
    second = tracker.observe(
        message,
        status=_status("running"),
        observed_at_ms=20,
        write_in_flight=True,
    )
    assert first is not None
    assert second is None
    assert len(tracker.observations) == 1


def test_reconciliation_states_are_revision_safe() -> None:
    exact = RevisionSafeCanonicalTracker()
    exact.observe(
        _message("abc"),
        status=_status("running"),
        observed_at_ms=1,
        write_in_flight=True,
    )
    assert exact.reconciliation(
        final_message_id="assistant-new",
        final_text="abc",
    ) is StreamCanonicalReconciliation.EXACT_MATCH

    extends = RevisionSafeCanonicalTracker()
    extends.observe(
        _message("abc"),
        status=_status("running"),
        observed_at_ms=1,
        write_in_flight=True,
    )
    assert extends.reconciliation(
        final_message_id="assistant-new",
        final_text="abcdef",
    ) is StreamCanonicalReconciliation.CANONICAL_EXTENDS_STREAM

    revised = RevisionSafeCanonicalTracker()
    revised.observe(
        _message("abc"),
        status=_status("running"),
        observed_at_ms=1,
        write_in_flight=True,
    )
    assert revised.reconciliation(
        final_message_id="assistant-new",
        final_text="xyz",
    ) is StreamCanonicalReconciliation.STREAM_REVISED_BY_CANONICAL

    assert RevisionSafeCanonicalTracker().reconciliation(
        final_message_id="assistant-new",
        final_text="abc",
    ) is StreamCanonicalReconciliation.UNAVAILABLE
    assert RevisionSafeCanonicalTracker().reconciliation(
        final_message_id="assistant-new",
        final_text="",
    ) is StreamCanonicalReconciliation.STREAM_INCOMPLETE


def test_observation_serialization_exports_preview_and_digest_not_full_text() -> None:
    tracker = RevisionSafeCanonicalTracker()
    observation = tracker.observe(
        _message("private-ish controlled probe text"),
        status=_status("running"),
        observed_at_ms=5,
        write_in_flight=True,
    )
    assert observation is not None
    payload = observation.to_dict()
    assert "text" not in payload
    assert payload["text_preview"] == "private-ish controlled probe text"
    assert len(payload["text_sha256"]) == 64
    assert payload["pre_final"] is True


def test_live_probe_has_one_product_write_site_and_no_retry_or_private_endpoint() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("self.runtime.send_text_observed(") == 1
    assert '"product_write_budget": 1' in source
    assert '"automatic_write_retry": False' in source
    assert "--acknowledge-live-writes" in source
    assert "Refusing live characterization without --acknowledge-live-writes" in source
    assert "while True" not in source
    assert "for attempt" not in source
    assert "backend-api/f/conversation" not in source
    assert "backend-api/conversation" not in source
    assert "chat-requirements" not in source
    assert "turnstile" not in source.lower()
    assert "proof_token" not in source.lower()


def test_candidate_a_probe_is_continuation_only_and_does_not_enable_production_streaming() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert 'parser.add_argument("--conversation", required=True)' in source
    assert '"production_streaming_enabled": False' in source
    assert '"next_source_if_not_proven": "SAFE_BROWSER_RESPONSE_OBSERVATION"' in source
    assert 'browser_authority_policy="PERSISTENT"' in source
