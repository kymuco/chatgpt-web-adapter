from __future__ import annotations

from copy import deepcopy

import pytest

from tools.capability_capture_v0_gap_audit import audit_structural_trace


def _live_structure() -> dict:
    """Sanitized timing specimen, not a substitute for the actual live gate."""
    return {
        "schema": "CWA_CAPTURE_V0_STRUCTURAL_TRACE",
        "productId": "google-translate-web",
        "captureMode": "EXPLICIT_OBSERVE_ONLY",
        "observedTabId": 123,
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "events": [
            {"phase": "source_ready", "t_ms": 0, "role": "textbox"},
            {"phase": "source_input_event", "t_ms": 2948},
            {"phase": "result_candidate_seen", "t_ms": 4336},
            {"phase": "result_candidate_presence_stable", "t_ms": 5567},
        ],
        "inputEventCount": 5,
        "routeVerified": True,
        "candidatePresenceStable": True,
        "candidateIdentityResolved": True,
        "canonicalCompletionProven": False,
        "semanticFinalityProven": False,
        "effectBoundary": "MANUAL_REFERENCE_ONLY_SOURCE_INPUT",
        "automaticRetry": False,
        "replayExecutable": False,
        "rawContentRetained": False,
    }


def test_observed_structural_trace_cannot_grant_replay_authority() -> None:
    audit = audit_structural_trace(_live_structure())
    assert audit["classification"] == "STRUCTURAL_DEMONSTRATION_ACCEPTED"
    assert audit["observed_requirements"] == [
        "exact_product_and_language_route",
        "human_source_input_event",
        "stable_structural_result_candidate_presence",
    ]
    assert "capture_bound_to_exact_source_text" in audit["unproven_requirements"]
    assert "translation_text_stability_proven" in audit["unproven_requirements"]
    assert "post_effect_lost_ack_reconciliation_proven" in audit[
        "unproven_requirements"
    ]
    assert audit["semantic_finality_proven"] is False
    assert audit["canonical_completion_proven"] is False
    assert audit["replay_executable"] is False
    assert audit["write_authority_granted"] is False
    assert audit["automatic_retry_authorized"] is False
    assert "observedTabId" not in audit
    assert "translatedText" not in audit


def test_partial_live_trace_remains_incomplete_without_false_finality() -> None:
    trace = _live_structure()
    trace["events"] = [
        {"phase": "source_ready", "role": "textbox", "t_ms": 0},
        {"phase": "source_input_event", "t_ms": 18061},
        {"phase": "result_candidate_seen", "t_ms": 19617},
    ]
    trace["candidatePresenceStable"] = False
    trace["candidateIdentityResolved"] = False
    audit = audit_structural_trace(trace)
    assert audit["classification"] == "OBSERVATION_INCOMPLETE"
    assert audit["replay_executable"] is False


@pytest.mark.parametrize(
    "field, value",
    [
        ("replayExecutable", True),
        ("automaticRetry", True),
        ("semanticFinalityProven", True),
        ("canonicalCompletionProven", True),
        ("routeVerified", False),
        ("productId", "some-other-service"),
        ("observedTabId", "123"),
        ("sourceLanguage", "es"),
        ("rawContentRetained", True),
    ],
)
def test_authority_or_identity_tampering_fails_closed(field: str, value: object) -> None:
    trace = _live_structure()
    trace[field] = value
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        audit_structural_trace(trace)


def test_rejects_unexpected_or_sensitive_fields_in_saved_trace() -> None:
    trace = _live_structure()
    trace["rawDom"] = "user content"
    with pytest.raises(ValueError, match="UNEXPECTED_FIELDS"):
        audit_structural_trace(trace)


def test_rejects_event_value_injection() -> None:
    trace = deepcopy(_live_structure())
    trace["events"][1]["text"] = "private"
    with pytest.raises(ValueError, match="UNBOUNDED_EVENT"):
        audit_structural_trace(trace)


def test_rejects_non_object_trace() -> None:
    with pytest.raises(ValueError, match="AUDIT_OBJECT_REQUIRED"):
        audit_structural_trace([])
