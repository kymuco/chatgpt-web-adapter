from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_video_artifact_download_intent_probe import (
    GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION,
    probe_gemini_notebook_video_artifact_download_intent,
)
from chatgpt_web_adapter.gemini_notebook_web import (
    GeminiNotebookOutcomeAmbiguousError,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
VIDEO_REF = "b2c41cbb-470f-46fb-8b39-578303b50c25"


class _FakeBridge:
    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "observedArtifactRef": payload["expectedArtifactRef"],
            "artifactTitle": "Video title",
            "artifactDetails": "1:21",
            "artifactIcons": ["videocam", "play_arrow", "more_vert"],
            "downloadAttemptMayHaveExecuted": True,
            "downloadClickPerformed": True,
            "payloadResponseObserved": False,
            "fetchRequestId": "",
            "responseStatusCode": None,
            "resourceType": "",
            "contentDispositionPresent": False,
            "contentDispositionAttachment": False,
            "contentType": "",
            "normalizedContentType": "",
            "downloadUrlOrigin": "",
            "downloadUrlHasQuery": False,
            "downloadUrlPathSuffix": [],
            "observedResponses": [],
            "downloadSinkObserved": True,
            "downloadSinkEvents": [
                {
                    "kind": "window_open",
                    "target": "_blank",
                    "url": {
                        "scheme": "https:",
                        "origin": "https://example.invalid",
                        "hasQuery": True,
                        "pathSuffix": ["video", "artifact"],
                    },
                }
            ],
            "downloadSinkWindowOpenPatched": True,
            "downloadSinkObjectUrlPatched": True,
            "responseBlockedBeforeBody": False,
            "responseBodyRead": False,
            "filesystemArtifactProven": False,
            "productWritePerformed": False,
            "navigationPerformed": False,
            "automaticRetry": False,
            "rawDownloadUrlExported": False,
        }


def test_video_download_intent_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION == (
        "gemini_notebook_video_artifact_download_intent_probe"
    )
    assert not hasattr(
        adapter,
        "probe_gemini_notebook_video_artifact_download_intent",
    )


def test_video_download_intent_contract_keeps_sink_sanitized() -> None:
    result = probe_gemini_notebook_video_artifact_download_intent(
        notebook=NOTEBOOK,
        expected_artifact_ref=VIDEO_REF,
        bridge=_FakeBridge(),
    )

    assert result["observed_artifact_ref"] == VIDEO_REF
    assert result["artifact_icons"] == ["videocam", "play_arrow", "more_vert"]
    assert result["download_sink_observed"] is True
    assert result["download_sink_events"][0]["kind"] == "window_open"
    assert result["payload_response_observed"] is False
    assert result["response_body_read"] is False
    assert result["filesystem_artifact_proven"] is False
    assert result["automatic_retry"] is False
    assert result["raw_download_url_exported"] is False


def test_video_download_response_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        probe_gemini_notebook_video_artifact_download_intent(
            notebook=NOTEBOOK,
            expected_artifact_ref=VIDEO_REF,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_video_download_intent_uses_exact_completed_ref_and_structural_save_alt() -> (
    None
):
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookWaitForStableExactArtifact(" in probe
    assert 'statusCandidate !== "NON_PENDING_CANDIDATE"' in probe
    assert "_cwaGeminiNotebookClickExactArtifactMoreMenuExpression(" in probe
    assert 'item.icons.includes("save_alt")' in probe
    assert "_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()" in probe
    assert "Скачать" not in probe


def test_video_download_effect_boundary_and_sink_precede_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    sink = probe.index("_cwaGeminiNotebookInstallDownloadSinkProbeExpression()")
    listener = probe.index("chrome.debugger.onEvent.addListener(observer)")
    fetch_enable = probe.index('"Fetch.enable"')
    boundary = probe.index("downloadAttemptMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()")
    assert sink < listener < fetch_enable < boundary < click
    assert probe.count("downloadAttemptMayHaveExecuted = false") == 1
    assert "if (downloadAttemptMayHaveExecuted)" in probe
    assert "_cwaGeminiNotebookAmbiguousError(error)" in probe


def test_video_direct_payload_classifier_is_video_specific() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert 'normalizedContentType.startsWith("video/")' in probe
    assert 'normalizedContentType.startsWith("audio/")' not in probe
    assert 'normalizedContentType === "application/octet-stream"' in probe
    assert "controlPlaneLikely" in probe
    assert '"batchexecute"' not in probe
    assert "observedResponses.length < 16" in probe
    assert "responseBodyRead: false" in probe
    assert "filesystemArtifactProven: false" in probe


def test_video_download_intent_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_artifact_download_intent_probe",' in host
    assert '"gemini_notebook_video_artifact_download_intent_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
