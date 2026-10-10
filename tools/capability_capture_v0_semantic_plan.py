"""Slice C0: compile captured structure to a non-executable semantic replay plan.

This is deliberately *not* a DOM/selector compiler or a product executor.
The current capture proves an input event and structural output presence, but
not which semantic element was targeted or whether result text was correct.
Every reference-derived locator is labelled as such, never capture-proven.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from tools.capability_capture_v0 import (
    ANNOTATED_TRANSLATE_PHASES,
    compile_manually_annotated_translate,
)
from tools.capability_capture_v0_gap_audit import audit_structural_trace

_PLAN_SCHEMA = "CWA_CAPTURE_V0_SEMANTIC_PLAN_NON_EXECUTABLE"
_FIXTURE_ROLES = frozenset({"textbox", "result_leaf", "other"})
_FIXTURE_FAMILIES = frozenset(
    {"source_input_candidate", "translate_result_candidate", "other"}
)
_PHASE_EVIDENCE: dict[str, str] = {
    "route_languages": "CAPTURE_OBSERVED_ROUTE_ONLY",
    "clear_source": "HANDWRITTEN_REFERENCE_ONLY",
    "prove_result_cleared": "HANDWRITTEN_REFERENCE_ONLY",
    "mutate_source_input": "CAPTURE_OBSERVED_HUMAN_INPUT_EVENT_ONLY",
    "observe_stable_result": "CAPTURE_OBSERVED_STRUCTURAL_PRESENCE_ONLY",
    "verify_result_route": "CAPTURE_OBSERVED_ROUTE_ONLY",
}
_REFERENCE_LOCATORS = (
    {
        "slot": "source_input",
        "role": "textbox",
        "family": "source_input_candidate",
        "expected_cardinality": "EXACTLY_ONE",
        "provenance": "HANDWRITTEN_REFERENCE_HEURISTIC_NOT_CAPTURED",
        "live_locator_identity_proven": False,
    },
    {
        "slot": "translated_result",
        "role": "result_leaf",
        "family": "translate_result_candidate",
        "expected_cardinality": "EXACTLY_ONE",
        "provenance": "HANDWRITTEN_REFERENCE_HEURISTIC_NOT_CAPTURED",
        "live_locator_identity_proven": False,
    },
)


@dataclass(frozen=True)
class SemanticFixtureNode:
    """One deliberately synthetic, content-free DOM descriptor.

    IDs, selectors, accessible names, page text and URLs are disallowed.
    Family and role are *manual fixture labels*, not captured browser evidence.
    """

    role: str
    family: str
    visible: bool
    enabled: bool

    @classmethod
    def parse(cls, value: object) -> SemanticFixtureNode:
        if not isinstance(value, dict) or set(value) != {
            "role",
            "family",
            "visible",
            "enabled",
        }:
            raise ValueError("CAPTURE_V0_FIXTURE_DESCRIPTOR_INVALID")
        role = value["role"]
        family = value["family"]
        if (
            not isinstance(role, str)
            or role not in _FIXTURE_ROLES
            or not isinstance(family, str)
            or family not in _FIXTURE_FAMILIES
            or type(value["visible"]) is not bool
            or type(value["enabled"]) is not bool
        ):
            raise ValueError("CAPTURE_V0_FIXTURE_DESCRIPTOR_INVALID")
        return cls(
            role=role, family=family, visible=value["visible"], enabled=value["enabled"]
        )


def evaluate_locator_fixture(nodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Classify ambiguity in synthetic semantics, without resolving live DOM.

    Even a UNIQUE fixture result has zero effect or replay authority.
    """
    if isinstance(nodes, (str, bytes, dict)) or not isinstance(nodes, Sequence):
        raise ValueError("CAPTURE_V0_FIXTURE_SEQUENCE_REQUIRED")
    if len(nodes) > 32:
        raise ValueError("CAPTURE_V0_FIXTURE_TOO_LARGE")
    candidates = tuple(SemanticFixtureNode.parse(n) for n in nodes)
    result: dict[str, Any] = {}
    for slot in _REFERENCE_LOCATORS:
        count = sum(
            1
            for node in candidates
            if node.role == slot["role"]
            and node.family == slot["family"]
            and node.visible
            and node.enabled
        )
        status = (
            "UNIQUE_IN_SYNTHETIC_FIXTURE"
            if count == 1
            else ("MISSING" if count == 0 else "AMBIGUOUS")
        )
        result[slot["slot"]] = {
            "status": status,
            "matching_count": count,
            "provenance": "SYNTHETIC_FIXTURE_ONLY",
            "live_locator_identity_proven": False,
        }
    return result


def compile_semantic_replay_plan(
    trace: dict[str, Any],
    *,
    expected_source_language: str,
    expected_target_language: str,
) -> dict[str, Any]:
    """Compile *structural* observations + annotated reference constraints.

    No actual input text, selectors, tab IDs, or product write instructions
    are accepted or returned. The result is never executable.
    """
    audit = audit_structural_trace(
        trace,
        expected_source_language=expected_source_language,
        expected_target_language=expected_target_language,
    )
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    structural = audit["classification"] == "STRUCTURAL_DEMONSTRATION_ACCEPTED"
    phase_slots = [
        {
            "phase": phase,
            "reference_provenance": "HANDWRITTEN_REFERENCE_ANNOTATION",
            "capture_evidence": (
                _PHASE_EVIDENCE[phase] if structural else "CAPTURE_INCOMPLETE"
            ),
        }
        for phase in candidate.phases
    ]
    return {
        "schema": _PLAN_SCHEMA,
        "product_id": candidate.product_id,
        "capability_id": candidate.capability_id,
        "source": "HUMAN_STRUCTURE_PLUS_HANDWRITTEN_REFERENCE",
        "capture_classification": audit["classification"],
        "expected_route": {
            "origin": "https://translate.google.com",
            "source_language": expected_source_language,
            "target_language": expected_target_language,
            "provenance": "EXTERNAL_EXPECTATIONS_MATCH_CAPTURE",
        },
        "input_binding": {
            "field": "text",
            "value_captured": False,
            "reference_source_text_match_required": True,
            "source_text_match_proven_by_capture": False,
        },
        "locator_templates": [dict(locator) for locator in _REFERENCE_LOCATORS],
        "phases": phase_slots,
        "effect_boundary": {
            "phase": candidate.effect_boundary,
            "reference_provenance": "HANDWRITTEN_REFERENCE_ONLY",
            "capture_proves_human_mutation_occurred": structural,
            "new_write_authority": False,
            "post_effect_unknown": "RECONCILE_NO_AUTO_RETRY",
        },
        "required_finality": candidate.result_evidence,
        "required_finality_proven": False,
        "unproven_requirements": list(audit["unproven_requirements"]),
        "locator_identity_proven": False,
        "new_write_authority": False,
        "automatic_retry": False,
        "executable": False,
        "promotion_verdict": "BLOCKED_UNPROVEN_SEMANTICS_AND_AUTHORITY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline semantic plan compiler (never touches a browser)"
    )
    parser.add_argument("trace_json", type=Path)
    parser.add_argument("--source-language", required=True)
    parser.add_argument("--target-language", required=True)
    args = parser.parse_args()
    trace = json.loads(args.trace_json.read_text(encoding="utf-8"))
    report = compile_semantic_replay_plan(
        trace,
        expected_source_language=args.source_language,
        expected_target_language=args.target_language,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
