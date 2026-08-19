from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.revision_safe_streaming_pr8_9 import (
    CANONICAL_EXTENDS_STREAM,
    EXACT_MATCH,
    STREAM_INCOMPLETE,
    STREAM_REVISED_BY_CANONICAL,
    RevisionSafeTextAccumulator,
)

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_accumulator_reconstructs_snapshot_delta_and_revision() -> None:
    state = RevisionSafeTextAccumulator()
    assert state.apply({"type": "assistant_text_snapshot", "sequence": 1, "text": "Hel"})
    assert state.apply({"type": "assistant_text_delta", "sequence": 2, "delta": "lo"})
    assert state.text == "Hello"
    assert state.reconcile("Hello") == EXACT_MATCH

    event = state.apply({"type": "assistant_text_revision", "sequence": 3, "text": "Hallo"})
    assert event is not None
    assert state.text == "Hallo"
    assert state.revision_count == 1
    assert state.reconcile("Hallo world") == CANONICAL_EXTENDS_STREAM
    assert state.reconcile("Hello world") == STREAM_REVISED_BY_CANONICAL


def test_sequence_gap_fails_reconciliation_closed_without_throwing() -> None:
    state = RevisionSafeTextAccumulator()
    state.apply({"type": "assistant_text_snapshot", "sequence": 1, "text": "A"})
    state.apply({"type": "assistant_text_delta", "sequence": 3, "delta": "C"})
    assert state.delivery_incomplete is True
    assert state.reconcile("ABC") == STREAM_INCOMPLETE


def test_finalization_event_keeps_canonical_text_authoritative() -> None:
    state = RevisionSafeTextAccumulator()
    state.apply({"type": "assistant_text_snapshot", "sequence": 1, "text": "partial"})
    event = state.finalization_event(
        canonical_text="partial final",
        conversation_id="c1",
        message_id="m1",
        model="gpt-5-6",
        finish_reason="stop",
    )
    assert event["type"] == "canonical_text_finalized"
    assert event["text"] == "partial final"
    assert event["reconciliation"] == CANONICAL_EXTENDS_STREAM


def test_extension_delivery_exports_only_reduced_text_events() -> None:
    source = (
        EXTENSION / "service_worker_revision_safe_text_delivery_pr8_9.js"
    ).read_text(encoding="utf-8")
    assert 'type: "turn_event"' in source
    assert '"assistant_text_snapshot"' in source
    assert '"assistant_text_delta"' in source
    assert '"assistant_text_revision"' in source
    assert "streamTextObservations" in source
    for forbidden in (
        "Network.getResponseBody",
        "Fetch.enable",
        "Fetch.fulfillRequest",
        "requestHeaders",
        "requestPostData",
        "document.cookie",
    ):
        assert forbidden not in source


def test_observability_loads_delivery_after_patch_protocol() -> None:
    source = (EXTENSION / "service_worker_observability.js").read_text(encoding="utf-8")
    patch = 'importScripts("service_worker_safe_browser_response_patch_protocol_pr8_9.js");'
    delivery = 'importScripts("service_worker_revision_safe_text_delivery_pr8_9.js");'
    assert patch in source
    assert delivery in source
    assert source.index(patch) < source.index(delivery)
