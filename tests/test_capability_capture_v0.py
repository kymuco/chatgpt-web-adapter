from __future__ import annotations

from dataclasses import replace

import pytest

from chatgpt_web_adapter.google_translate_web import GoogleTranslateTextResult
from tools.capability_capture_v0 import (
    ANNOTATED_TRANSLATE_PHASES,
    SOURCE_INPUT_EFFECT_BOUNDARY,
    compile_manually_annotated_translate,
    inspect_reference_result,
)


def _reference_result() -> GoogleTranslateTextResult:
    return GoogleTranslateTextResult(
        translated_text="Hola",
        source_language="en",
        target_language="es",
        final_url="https://translate.google.com/?sl=en&tl=es&op=translate",
        tab_id=17,
        elapsed_ms=200,
        finality_evidence="PAGE_DOM_STABLE_TRANSLATION",
        canonical_completion_proven=False,
        automatic_retry=False,
    )


def test_candidate_is_not_executable_and_preserves_effect_semantics() -> None:
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    payload = candidate.to_dict()

    assert candidate.executable is False
    assert payload["schema"] == "CWA_CAPTURE_CANDIDATE_V0_NOT_EXECUTABLE"
    assert payload["annotation_source"] == "MANUAL_REFERENCE_ANNOTATION_NOT_CAPTURED"
    assert payload["effect_boundary"] == SOURCE_INPUT_EFFECT_BOUNDARY
    assert payload["on_unknown_after_effect"] == "RECONCILE_NO_AUTO_RETRY"
    assert payload["result_evidence"] == "PAGE_DOM_STABLE_TRANSLATION"
    assert payload["canonical_completion_proven"] is False
    assert payload["automatic_retry"] is False
    assert payload["inputs"] == ["text", "source_language", "target_language"]
    assert not {"conversation_id", "provider_id"} & set(payload)


@pytest.mark.parametrize(
    "phases",
    [
        (),
        ANNOTATED_TRANSLATE_PHASES[:-1],
        (*ANNOTATED_TRANSLATE_PHASES, "retry"),
        (
            "route_languages",
            "clear_source",
            "mutate_source_input",
            "prove_result_cleared",
            "observe_stable_result",
            "verify_result_route",
        ),
    ],
)
def test_candidate_rejects_missing_extra_or_misordered_effect_evidence(
    phases: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="ANNOTATED_PHASES_NOT_PROVEN"):
        compile_manually_annotated_translate(phases)


def test_reference_observation_is_not_promoted_to_canonical_finality() -> None:
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    assert inspect_reference_result(
        candidate,
        _reference_result(),
        expected_source_language="en",
        expected_target_language="es",
    )


@pytest.mark.parametrize(
    "result",
    [
        replace(_reference_result(), translated_text=""),
        replace(_reference_result(), canonical_completion_proven=True),
        replace(_reference_result(), automatic_retry=True),
        replace(_reference_result(), finality_evidence="CANONICAL_COMPLETED"),
        replace(_reference_result(), target_language="de"),
    ],
)
def test_reference_observation_fails_closed_on_semantic_drift(
    result: GoogleTranslateTextResult,
) -> None:
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    assert not inspect_reference_result(
        candidate,
        result,
        expected_source_language="en",
        expected_target_language="es",
    )


def test_modified_candidate_is_not_silently_accepted() -> None:
    candidate = compile_manually_annotated_translate(ANNOTATED_TRANSLATE_PHASES)
    changed = replace(candidate, automatic_retry=True)
    assert not inspect_reference_result(
        changed,
        _reference_result(),
        expected_source_language="en",
        expected_target_language="es",
    )
