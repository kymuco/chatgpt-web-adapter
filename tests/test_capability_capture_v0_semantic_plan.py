from __future__ import annotations

from copy import deepcopy

import pytest

from tools.capability_capture_v0_semantic_plan import (
    compile_semantic_replay_plan,
    evaluate_locator_fixture,
)


def _capture() -> dict:
    # A synthetic representation of the previously reported live observation.
    # The example tab id is fake; no live Chrome instance is ever contacted.
    return {
        "schema": "CWA_CAPTURE_V0_STRUCTURAL_TRACE",
        "productId": "google-translate-web",
        "captureMode": "EXPLICIT_OBSERVE_ONLY",
        "observedTabId": 12,
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "events": [
            {"phase": "source_ready", "role": "textbox", "t_ms": 0},
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


def _compile(trace: dict | None = None) -> dict:
    return compile_semantic_replay_plan(
        _capture() if trace is None else trace,
        expected_source_language="en",
        expected_target_language="es",
    )


def _node(
    role: str,
    family: str,
    *,
    visible: bool = True,
    enabled: bool = True,
) -> dict:
    return {
        "role": role,
        "family": family,
        "visible": visible,
        "enabled": enabled,
    }


def test_live_structure_compiles_to_bounded_dry_run_plan_only() -> None:
    result = _compile()
    assert result["schema"] == "CWA_CAPTURE_V0_SEMANTIC_PLAN_NON_EXECUTABLE"
    assert result["capture_classification"] == "STRUCTURAL_DEMONSTRATION_ACCEPTED"
    assert result["source"] == "HUMAN_STRUCTURE_PLUS_HANDWRITTEN_REFERENCE"
    assert result["expected_route"] == {
        "origin": "https://translate.google.com",
        "source_language": "en",
        "target_language": "es",
        "provenance": "EXTERNAL_EXPECTATIONS_MATCH_CAPTURE",
    }
    assert result["input_binding"] == {
        "field": "text",
        "value_captured": False,
        "reference_source_text_match_required": True,
        "source_text_match_proven_by_capture": False,
    }
    assert [s["phase"] for s in result["phases"]] == [
        "route_languages",
        "clear_source",
        "prove_result_cleared",
        "mutate_source_input",
        "observe_stable_result",
        "verify_result_route",
    ]
    assert result["phases"][3]["capture_evidence"] == (
        "CAPTURE_OBSERVED_HUMAN_INPUT_EVENT_ONLY"
    )
    assert result["phases"][4]["capture_evidence"] == (
        "CAPTURE_OBSERVED_STRUCTURAL_PRESENCE_ONLY"
    )
    assert result["phases"][2]["capture_evidence"] == "HANDWRITTEN_REFERENCE_ONLY"
    assert result["effect_boundary"] == {
        "phase": "mutate_source_input",
        "reference_provenance": "HANDWRITTEN_REFERENCE_ONLY",
        "capture_proves_human_mutation_occurred": True,
        "new_write_authority": False,
        "post_effect_unknown": "RECONCILE_NO_AUTO_RETRY",
    }
    assert result["required_finality"] == "PAGE_DOM_STABLE_TRANSLATION"
    assert result["required_finality_proven"] is False
    assert result["locator_identity_proven"] is False
    assert result["new_write_authority"] is False
    assert result["automatic_retry"] is False
    assert result["executable"] is False
    assert result["promotion_verdict"] == "BLOCKED_UNPROVEN_SEMANTICS_AND_AUTHORITY"
    assert all(
        locator["provenance"] == "HANDWRITTEN_REFERENCE_HEURISTIC_NOT_CAPTURED"
        and locator["live_locator_identity_proven"] is False
        for locator in result["locator_templates"]
    )
    for secret_key in ("observedTabId", "events", "translatedText", "rawDom"):
        assert secret_key not in result


def test_partial_trace_compiles_as_blocked_not_capture_proven() -> None:
    trace = _capture()
    trace["events"] = [
        {"phase": "source_ready", "role": "textbox", "t_ms": 0},
        {"phase": "source_input_event", "t_ms": 18061},
        {"phase": "result_candidate_seen", "t_ms": 19617},
    ]
    trace["candidatePresenceStable"] = False
    trace["candidateIdentityResolved"] = False
    plan = _compile(trace)
    assert plan["capture_classification"] == "OBSERVATION_INCOMPLETE"
    assert plan["effect_boundary"]["new_write_authority"] is False
    assert plan["effect_boundary"]["capture_proves_human_mutation_occurred"] is False
    assert all(s["capture_evidence"] == "CAPTURE_INCOMPLETE" for s in plan["phases"])
    assert plan["executable"] is False


@pytest.mark.parametrize(
    "field, value",
    [
        ("productId", "wrong-product"),
        ("routeVerified", False),
        ("canonicalCompletionProven", True),
        ("automaticRetry", True),
        ("replayExecutable", True),
        ("sourceLanguage", "de"),
        ("rawContentRetained", True),
    ],
)
def test_compilation_does_not_accept_trace_spoofing(field: str, value: object) -> None:
    trace = _capture()
    trace[field] = value
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        _compile(trace)


def test_compiler_rejects_private_content_in_trace() -> None:
    trace = deepcopy(_capture())
    trace["events"][1]["typed_text"] = "secret"
    with pytest.raises(ValueError, match="CAPTURE_V0_UNBOUNDED_EVENT"):
        _compile(trace)
    trace = _capture()
    trace["pageHtml"] = "<div>secret</div>"
    with pytest.raises(ValueError, match="CAPTURE_V0_AUDIT_UNEXPECTED_FIELDS"):
        _compile(trace)


def test_independently_bound_language_pair_cannot_be_changed_by_trace() -> None:
    trace = _capture()
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        compile_semantic_replay_plan(
            trace,
            expected_source_language="fr",
            expected_target_language="es",
        )


def test_unique_synthetic_roles_are_only_fixture_evidence() -> None:
    nodes = [
        _node("other", "other"),
        _node("textbox", "source_input_candidate"),
        _node("result_leaf", "translate_result_candidate"),
        _node("textbox", "source_input_candidate", visible=False),
        _node("result_leaf", "translate_result_candidate", enabled=False),
    ]
    first = evaluate_locator_fixture(nodes)
    last = evaluate_locator_fixture(list(reversed(nodes)))
    assert first == last
    assert first["source_input"] == {
        "status": "UNIQUE_IN_SYNTHETIC_FIXTURE",
        "matching_count": 1,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "live_locator_identity_proven": False,
    }
    assert first["translated_result"]["status"] == "UNIQUE_IN_SYNTHETIC_FIXTURE"
    assert _compile()["executable"] is False


def test_two_enabled_visible_textboxes_are_ambiguous_not_leftmost() -> None:
    nodes = [
        _node("textbox", "source_input_candidate"),
        _node("textbox", "source_input_candidate"),
        _node("result_leaf", "translate_result_candidate"),
    ]
    evaluated = evaluate_locator_fixture(nodes)
    assert evaluated["source_input"]["status"] == "AMBIGUOUS"
    assert evaluated["source_input"]["matching_count"] == 2
    assert evaluated["translated_result"]["status"] == "UNIQUE_IN_SYNTHETIC_FIXTURE"


def test_two_result_leaves_and_missing_inputs_fail_closed() -> None:
    nodes = [
        _node("result_leaf", "translate_result_candidate"),
        _node("result_leaf", "translate_result_candidate"),
    ]
    evaluated = evaluate_locator_fixture(nodes)
    assert evaluated["source_input"]["status"] == "MISSING"
    assert evaluated["translated_result"]["status"] == "AMBIGUOUS"


@pytest.mark.parametrize(
    "invalid",
    [
        "textbox",
        {"role": "textbox"},
        [{}],
        [_node("textbox", "source_input_candidate") | {"rawText": "sensitive"}],
        [_node("textbox", "source_input_candidate") | {"visible": 1}],
        [_node("textbox", "source_input_candidate") | {"enabled": "true"}],
        [_node("textbox", "other") | {"css": "#source"}],
        [_node("textbox", "source_input_candidate")] * 33,
    ],
)
def test_unbounded_or_nonsemantic_fixtures_rejected(invalid: object) -> None:
    with pytest.raises(ValueError, match="CAPTURE_V0_FIXTURE"):
        evaluate_locator_fixture(invalid)  # type: ignore[arg-type]
