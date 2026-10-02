from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter._gemini_notebook_video_generation import (
    _GEMINI_NOTEBOOK_VIDEO_GENERATION_OPERATION,
    _generate_gemini_notebook_video,
)
from chatgpt_web_adapter.gemini_notebook_web import (
    GeminiNotebookOutcomeAmbiguousError,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"


class _FakeBridge:
    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "tabId": 7,
            "elapsedMs": 521,
            "beforeArtifactRefs": ["audio-ref"],
            "afterArtifactRefs": ["audio-ref", "video-ref"],
            "generationCommitMayHaveExecuted": True,
            "generationAcceptedProven": True,
            "observedArtifactRef": "video-ref",
            "artifactStatus": "PENDING",
            "artifactTitle": "",
            "artifactDetails": "",
            "artifactIcons": ["progress_activity"],
            "startEvidence": "PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_ACCEPTED",
            "canonicalCompletionProven": False,
            "automaticRetry": False,
            "navigationPerformed": False,
        }


def test_video_generation_stays_private() -> None:
    assert _GEMINI_NOTEBOOK_VIDEO_GENERATION_OPERATION == (
        "gemini_notebook_video_generation"
    )
    assert not hasattr(adapter, "_generate_gemini_notebook_video")


def test_video_generation_requires_exact_one_artifact_delta() -> None:
    result = _generate_gemini_notebook_video(
        notebook=NOTEBOOK,
        bridge=_FakeBridge(),
    )

    assert result["before_artifact_refs"] == ["audio-ref"]
    assert result["after_artifact_refs"] == ["audio-ref", "video-ref"]
    assert result["observed_artifact_ref"] == "video-ref"
    assert result["generation_commit_may_have_executed"] is True
    assert result["generation_accepted_proven"] is True
    assert result["automatic_retry"] is False
    assert result["canonical_completion_proven"] is False


def test_video_generation_response_loss_is_ambiguous() -> None:
    class _LostBridge:
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        _generate_gemini_notebook_video(
            notebook=NOTEBOOK,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_video_generate_now_identity_is_structural_and_single_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    click = worker.split(
        "function _cwaGeminiNotebookClickVideoGenerateNowExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookWaitForVideoConfig(",
        1,
    )[0]

    assert 'icons.includes("subscriptions")' in click
    assert 'button.classList.contains("mat-tonal-button")' in click
    assert "tonalCandidates.length !== 1" in click
    assert click.count(".click()") == 1
    assert "Сгенерировать сейчас" not in click
    assert "Generate now" not in click


def test_video_generation_effect_boundary_precedes_generate_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoGeneration(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[0]

    boundary = probe.index("generationCommitMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVideoGenerateNowExpression()")
    assert boundary < click
    assert probe.count("generationCommitMayHaveExecuted = false") == 1
    assert "if (generationCommitMayHaveExecuted)" in probe
    assert "_cwaGeminiNotebookAmbiguousError(error)" in probe
    assert "automaticRetry: false" in probe


def test_video_generation_acceptance_is_exact_new_ref_delta() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    wait = worker.split(
        "async function _cwaGeminiNotebookWaitForStableArtifactDelta(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoGeneration(message)",
        1,
    )[0]

    assert "newRows.length > 1" in wait
    assert "!before.has(String(row.observedArtifactRef))" in wait
    assert '"PENDING_CANDIDATE"' in wait
    assert '"NON_PENDING_CANDIDATE"' in wait
    assert "CWA_GEMINI_NOTEBOOK_AUDIO_OBSERVATION_STABLE_MS" in wait


def test_video_generation_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_generation",' in host
    assert '"gemini_notebook_video_generation": 60_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
