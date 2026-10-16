"""Research-only annotated Google Translate capture candidate; never executes a write.

This module does not record the browser or replay generated UI steps. It is a
bounded, manual-annotation scaffold for falsifying the first CapabilitySpec
semantics before instrumenting Chrome/CDP.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import parse_qs, urlsplit

from chatgpt_web_adapter.google_translate_web import (
    GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
    GOOGLE_TRANSLATE_WEB_FINALITY,
    GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
    GoogleTranslateTextResult,
)

ANNOTATED_TRANSLATE_PHASES = (
    "route_languages",
    "clear_source",
    "prove_result_cleared",
    "mutate_source_input",
    "observe_stable_result",
    "verify_result_route",
)

SOURCE_INPUT_EFFECT_BOUNDARY = "mutate_source_input"
ANNOTATION_SOURCE = "MANUAL_REFERENCE_ANNOTATION_NOT_CAPTURED"


@dataclass(frozen=True)
class CandidateCapabilitySpec:
    product_id: str
    capability_id: str
    input_names: tuple[str, ...]
    phases: tuple[str, ...]
    effect_boundary: str
    result_evidence: str
    canonical_completion_proven: bool
    automatic_retry: bool
    annotation_source: str
    executable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "CWA_CAPTURE_CANDIDATE_V0_NOT_EXECUTABLE",
            "product_id": self.product_id,
            "capability_id": self.capability_id,
            "inputs": list(self.input_names),
            "phases": list(self.phases),
            "effect_boundary": self.effect_boundary,
            "on_unknown_after_effect": "RECONCILE_NO_AUTO_RETRY",
            "result_evidence": self.result_evidence,
            "canonical_completion_proven": self.canonical_completion_proven,
            "automatic_retry": self.automatic_retry,
            "annotation_source": self.annotation_source,
            "executable": self.executable,
        }


def compile_manually_annotated_translate(
    phases: Sequence[str],
) -> CandidateCapabilitySpec:
    """Validate an explicit annotation, never infer DOM identity from a trace."""
    actual = tuple(phases)
    if actual != ANNOTATED_TRANSLATE_PHASES:
        raise ValueError("CAPTURE_V0_ANNOTATED_PHASES_NOT_PROVEN")
    return CandidateCapabilitySpec(
        product_id=GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
        capability_id=GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
        input_names=("text", "source_language", "target_language"),
        phases=actual,
        effect_boundary=SOURCE_INPUT_EFFECT_BOUNDARY,
        result_evidence=GOOGLE_TRANSLATE_WEB_FINALITY,
        canonical_completion_proven=False,
        automatic_retry=False,
        annotation_source=ANNOTATION_SOURCE,
        executable=False,
    )


def inspect_reference_result(
    candidate: CandidateCapabilitySpec,
    result: GoogleTranslateTextResult,
    *,
    expected_source_language: str,
    expected_target_language: str,
) -> bool:
    """Inspect one already-returned CWA result; no browser, request or retry."""
    if candidate != compile_manually_annotated_translate(candidate.phases):
        return False
    if not isinstance(result, GoogleTranslateTextResult):
        return False
    try:
        route = urlsplit(result.final_url)
        languages = parse_qs(route.query, keep_blank_values=True)
        route_bound = (
            route.scheme == "https"
            and route.hostname == "translate.google.com"
            and route.username is None
            and route.password is None
            and languages.get("sl") == [expected_source_language]
            and languages.get("tl") == [expected_target_language]
        )
    except ValueError:
        return False
    return (
        route_bound
        and bool(result.translated_text.strip())
        and result.source_language == expected_source_language
        and result.target_language == expected_target_language
        and result.finality_evidence == candidate.result_evidence
        and result.canonical_completion_proven is False
        and result.automatic_retry is False
    )


def main() -> None:
    # Offline inspection only. No browser/extension connection occurs here.
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    print(json.dumps(candidate.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
