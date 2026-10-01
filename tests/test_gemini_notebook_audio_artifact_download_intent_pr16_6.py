from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_audio_artifact_download_intent_probe import (
    GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION,
    probe_gemini_notebook_audio_artifact_download_intent,
)
from chatgpt_web_adapter.gemini_notebook_web import (
    GeminiNotebookOutcomeAmbiguousError,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
ARTIFACT_REF = "261a5005-1c03-44d7-9aa9-ecfb5bcef8f2"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "observedArtifactRef": payload["expectedArtifactRef"],
            "downloadAttemptMayHaveExecuted": True,
            "downloadClickPerformed": True,
            "payloadResponseObserved": True,
            "fetchRequestId": "interception-job-2",
            "responseStatusCode": 200,
            "resourceType": "Other",
            "contentDispositionPresent": True,
            "contentDispositionAttachment": True,
            "contentType": "audio/mpeg",
            "normalizedContentType": "audio/mpeg",
            "downloadUrlOrigin": "https://notebook.google.com",
            "downloadUrlHasQuery": True,
            "downloadUrlPathSuffix": ["artifact", "download"],
            "observedResponses": [
                {
                    "requestId": "interception-job-1",
                    "contentType": "application/json; charset=utf-8",
                    "normalizedContentType": "application/json",
                    "urlPathSuffix": ["data", "batchexecute"],
                    "controlPlaneLikely": True,
                    "payloadCandidate": False,
                    "blocked": False,
                },
                {
                    "requestId": "interception-job-2",
                    "contentType": "audio/mpeg",
                    "normalizedContentType": "audio/mpeg",
                    "urlPathSuffix": ["artifact", "download"],
                    "controlPlaneLikely": False,
                    "payloadCandidate": True,
                    "blocked": True,
                },
            ],
            "downloadSinkObserved": True,
            "downloadSinkEvents": [
                {
                    "kind": "anchor_click",
                    "url": {
                        "scheme": "https:",
                        "origin": "https://example.invalid",
                        "hasQuery": True,
                        "pathSuffix": ["audio", "artifact"],
                    },
                    "downloadPresent": True,
                    "downloadValue": "artifact.wav",
                    "target": "",
                    "trusted": False,
                }
            ],
            "downloadSinkWindowOpenPatched": True,
            "downloadSinkObjectUrlPatched": True,
            "responseBlockedBeforeBody": True,
            "responseBodyRead": False,
            "filesystemArtifactProven": False,
            "productWritePerformed": False,
            "navigationPerformed": False,
            "automaticRetry": False,
            "rawDownloadUrlExported": False,
        }


def test_download_intent_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION == (
        "gemini_notebook_audio_artifact_download_intent_probe"
    )
    assert not hasattr(
        adapter,
        "probe_gemini_notebook_audio_artifact_download_intent",
    )


def test_download_intent_probe_contract_is_denied_and_non_retryable() -> None:
    bridge = _FakeBridge()
    result = probe_gemini_notebook_audio_artifact_download_intent(
        notebook=NOTEBOOK,
        expected_artifact_ref=ARTIFACT_REF,
        bridge=bridge,
    )

    assert result["observed_artifact_ref"] == ARTIFACT_REF
    assert result["fetch_request_id"] == "interception-job-2"
    assert result["payload_response_observed"] is True
    assert result["normalized_content_type"] == "audio/mpeg"
    assert len(result["observed_responses"]) == 2
    assert result["observed_responses"][0]["controlPlaneLikely"] is True
    assert result["download_sink_observed"] is True
    assert result["download_sink_events"][0]["kind"] == "anchor_click"
    assert result["content_disposition_attachment"] is True
    assert result["response_blocked_before_body"] is True
    assert result["response_body_read"] is False
    assert result["filesystem_artifact_proven"] is False
    assert result["automatic_retry"] is False
    assert result["raw_download_url_exported"] is False


def test_download_intent_response_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        probe_gemini_notebook_audio_artifact_download_intent(
            notebook=NOTEBOOK,
            expected_artifact_ref=ARTIFACT_REF,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_download_click_identity_is_save_alt_and_not_localized() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    click = worker.split(
        "function _cwaGeminiNotebookClickVisibleArtifactDownloadExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[0]

    assert 'item.getAttribute("role") === "menuitem"' in click
    assert 'item.classList.contains("mat-mdc-menu-item")' in click
    assert 'icons.includes("save_alt")' in click
    assert "candidates.length !== 1" in click
    assert click.count(".click()") == 1
    assert "item.innerText" not in click
    assert "item.textContent" not in click
    assert "Скачать" not in click


def test_download_intent_uses_fetch_response_blocking_after_identity() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[0]

    assert '"Fetch.enable"' in probe
    assert '"Fetch.requestPaused"' in probe
    assert '"Fetch.continueResponse"' in probe
    assert '"Fetch.failRequest"' in probe
    assert 'errorReason: "Aborted"' in probe
    assert '"Fetch.disable"' in probe
    assert "Page.setDownloadBehavior" not in probe
    assert "Page.downloadWillBegin" not in probe

    listener = probe.index("chrome.debugger.onEvent.addListener(observer)")
    fetch_enable = probe.index('"Fetch.enable"')
    boundary = probe.index("downloadAttemptMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()")
    assert listener < fetch_enable < boundary < click
    assert probe.count("downloadAttemptMayHaveExecuted = false") == 1
    assert "if (downloadAttemptMayHaveExecuted)" in probe
    assert "_cwaGeminiNotebookAmbiguousError(error)" in probe


def test_download_intent_separates_batchexecute_control_plane_from_payload() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[0]

    assert 'responseHeader(params, "content-disposition")' in probe
    assert 'responseHeader(params, "content-type")' in probe
    assert '"batchexecute"' not in probe
    assert "jsonLike &&" in probe
    assert "attachmentLike &&" in probe
    assert 'String(params?.resourceType || "") === "XHR"' in probe
    assert "controlPlaneLikely" in probe
    assert 'normalizedContentType.startsWith("audio/")' in probe
    assert 'normalizedContentType === "application/octet-stream"' in probe
    assert "payloadCandidate" in probe
    assert "payloadCandidates.length > 1" in probe
    assert "observedResponses.length < 16" in probe
    assert "rawDownloadUrlExported: false" in probe
    assert "responseBodyRead: false" in probe
    assert "filesystemArtifactProven: false" in probe


def test_download_intent_allows_incomplete_characterization_without_retry() -> None:
    class _NoPayloadBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            response = super()._rpc(
                payload,
                timeout=timeout,
                on_event=on_event,
                **kwargs,
            )
            response.update(
                {
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
                    "responseBlockedBeforeBody": False,
                    "observedResponses": [
                        {
                            "requestId": "interception-job-1",
                            "normalizedContentType": "application/json",
                            "urlPathSuffix": ["data", "batchexecute"],
                            "controlPlaneLikely": True,
                            "payloadCandidate": False,
                            "blocked": False,
                        }
                    ],
                }
            )
            return response

    result = probe_gemini_notebook_audio_artifact_download_intent(
        notebook=NOTEBOOK,
        expected_artifact_ref=ARTIFACT_REF,
        bridge=_NoPayloadBridge(),
    )

    assert result["payload_response_observed"] is False
    assert result["fetch_request_id"] == ""
    assert result["response_blocked_before_body"] is False
    assert result["automatic_retry"] is False
    assert result["observed_responses"][0]["controlPlaneLikely"] is True


def test_download_sink_probe_blocks_page_facing_sinks_and_restores() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    install = worker.split(
        "function _cwaGeminiNotebookInstallDownloadSinkProbeExpression()",
        1,
    )[1].split(
        "function _cwaGeminiNotebookReadDownloadSinkProbeExpression()",
        1,
    )[0]
    restore = worker.split(
        "function _cwaGeminiNotebookRestoreDownloadSinkProbeExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[0]
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoArtifactDownloadIntent(message)",
        1,
    )[0]

    assert 'document.addEventListener("click", state.onClick, true)' in install
    assert 'document.addEventListener("submit", state.onSubmit, true)' in install
    assert "event.preventDefault()" in install
    assert "event.stopImmediatePropagation()" in install
    assert "window.open = function" in install
    assert "URL.createObjectURL = function" in install
    assert "raw" not in install.lower()
    assert 'document.removeEventListener("click", state.onClick, true)' in restore
    assert 'document.removeEventListener("submit", state.onSubmit, true)' in restore
    assert "window.open = state.originalWindowOpen" in restore
    assert "URL.createObjectURL = state.originalCreateObjectURL" in restore

    install_call = probe.index("_cwaGeminiNotebookInstallDownloadSinkProbeExpression()")
    boundary = probe.index("downloadAttemptMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()")
    assert install_call < boundary < click
    assert "_cwaGeminiNotebookRestoreDownloadSinkProbeExpression()" in probe


def test_download_intent_does_not_add_downloads_permission() -> None:
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    assert '"downloads"' not in manifest
    assert "chrome.downloads" not in worker
    assert "Page.setDownloadBehavior" not in worker
    assert "Browser.setDownloadBehavior" not in worker
    assert "rawDownloadUrlExported: false" in worker


def test_download_intent_host_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_audio_artifact_download_intent_probe",' in host
    assert '"gemini_notebook_audio_artifact_download_intent_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
