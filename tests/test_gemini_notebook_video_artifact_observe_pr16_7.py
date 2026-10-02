from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter._gemini_notebook_video_artifact_observation import (
    _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_OPERATION,
    GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY,
    GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE,
    _observe_gemini_notebook_video_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
VIDEO_REF = "b2c41cbb-470f-46fb-8b39-578303b50c25"


class _FakeBridge:
    def __init__(self, *, completed: bool = False) -> None:
        self.completed = completed

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        if self.completed:
            return {
                "ok": True,
                "productId": "gemini-notebook-web",
                "notebookUrl": payload["notebookUrl"],
                "observedArtifactRef": payload["observedArtifactRef"],
                "artifactStatus": "COMPLETED",
                "artifactTitle": "Video title",
                "artifactDetails": "Video details",
                "artifactIcons": ["videocam", "play_arrow", "more_vert"],
                "completionProven": True,
                "reloadVerified": True,
                "finalityEvidence": GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY,
                "canonicalCompletionProven": False,
                "automaticRetry": False,
                "writePerformed": False,
                "navigationPerformed": True,
            }
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "observedArtifactRef": payload["observedArtifactRef"],
            "artifactStatus": "PENDING",
            "artifactTitle": "Generating...",
            "artifactDetails": "Pending",
            "artifactIcons": ["progress_activity"],
            "completionProven": False,
            "reloadVerified": False,
            "finalityEvidence": GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE,
            "canonicalCompletionProven": False,
            "automaticRetry": False,
            "writePerformed": False,
            "navigationPerformed": False,
        }


def test_video_observation_stays_private() -> None:
    assert _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_OPERATION == (
        "gemini_notebook_video_artifact_observe"
    )
    assert not hasattr(
        adapter,
        "_observe_gemini_notebook_video_artifact",
    )


@pytest.mark.parametrize("completed", [False, True])
def test_video_observation_contract(completed: bool) -> None:
    result = _observe_gemini_notebook_video_artifact(
        notebook=NOTEBOOK,
        observed_artifact_ref=VIDEO_REF,
        bridge=_FakeBridge(completed=completed),
    )

    assert result["observed_artifact_ref"] == VIDEO_REF
    assert result["write_performed"] is False
    assert result["automatic_retry"] is False
    if completed:
        assert result["artifact_status"] == "COMPLETED"
        assert result["completion_proven"] is True
        assert result["reload_verified"] is True
        assert result["navigation_performed"] is True
        assert result["finality_evidence"] == (
            GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY
        )
    else:
        assert result["artifact_status"] == "PENDING"
        assert result["completion_proven"] is False
        assert result["reload_verified"] is False
        assert result["navigation_performed"] is False
        assert result["finality_evidence"] == GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE


def test_video_observe_rejects_wrong_pending_contract() -> None:
    class _WrongBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            response = super()._rpc(
                payload,
                timeout=timeout,
                on_event=on_event,
                **kwargs,
            )
            response["reloadVerified"] = True
            return response

    with pytest.raises(
        RequestError,
        match="GEMINI_NOTEBOOK_VIDEO_PENDING_CONTRACT_INVALID",
    ):
        _observe_gemini_notebook_video_artifact(
            notebook=NOTEBOOK,
            observed_artifact_ref=VIDEO_REF,
            bridge=_WrongBridge(),
        )


def test_exact_artifact_observer_allows_multiple_rows_and_matches_exact_ref() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    observe = worker.split(
        "async function _cwaGeminiNotebookWaitForStableExactArtifact(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoArtifactObservation(message)",
        1,
    )[0]

    assert "rows.length > 1" not in observe
    assert "rows.filter(" in observe
    assert 'String(row?.observedArtifactRef || "") === expectedArtifactRef' in observe
    assert "matches.length > 1" in observe
    assert '"PENDING_CANDIDATE"' in observe
    assert '"NON_PENDING_CANDIDATE"' in observe
    assert "CWA_GEMINI_NOTEBOOK_AUDIO_OBSERVATION_STABLE_MS" in observe


def test_video_observe_pending_returns_without_reload() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactObservation(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[0]

    pending_branch = probe.split(
        'if (firstRow.statusCandidate === "PENDING_CANDIDATE")',
        1,
    )[1].split(
        "await chrome.debugger.detach(debuggee);",
        1,
    )[0]
    assert "_cwaGeminiNotebookReloadExactNotebookTab" not in pending_branch
    assert "completionProven: false" in pending_branch
    assert "reloadVerified: false" in pending_branch
    assert "navigationPerformed: false" in pending_branch


def test_video_observe_completed_requires_same_ref_after_reload() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactObservation(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookReloadExactNotebookTab(" in probe
    assert probe.count("_cwaGeminiNotebookWaitForStableExactArtifact(") == 2
    assert 'durableRow.statusCandidate !== "NON_PENDING_CANDIDATE"' in probe
    assert "completionProven: true" in probe
    assert "reloadVerified: true" in probe
    assert "navigationPerformed: true" in probe


def test_video_observation_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_artifact_observe",' in host
    assert '"gemini_notebook_video_artifact_observe": 60_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
