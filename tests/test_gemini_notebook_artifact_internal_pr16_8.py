from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"


def test_artifact_byte_core_is_internal_only() -> None:
    assert not hasattr(adapter, "HostedArtifactLifecycle")
    assert not hasattr(adapter, "ArtifactLifecycleRegistry")


def test_audio_and_video_byte_wrappers_delegate_to_one_internal_core() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    assert worker.count(
        "async function _cwaGeminiNotebookProbeArtifactBytes("
    ) == 1

    audio = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[0]
    video = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookProbeArtifactBytes(message, port" in audio
    assert "_cwaGeminiNotebookProbeArtifactBytes(message, port" in video
    assert 'mediaFamily: "audio"' in audio
    assert 'mediaFamily: "video"' in video


def test_internal_core_owns_proven_retrieval_primitives() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    shared = worker.split(
        "async function _cwaGeminiNotebookProbeArtifactBytes(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)",
        1,
    )[0]

    for token in (
        "_cwaGeminiNotebookClickExactArtifactMoreMenuExpression(",
        'item.icons.includes("save_alt")',
        "_cwaGeminiNotebookInstallDownloadSinkProbeExpression()",
        "_cwaGeminiNotebookTakeUniqueWindowOpenLocatorExpression()",
        "_cwaGeminiNotebookLoadLocatorBytes(",
        "safePortPost(port",
    ):
        assert token in shared

    assert "downloadAttemptMayHaveExecuted = true;" in shared
    assert "_cwaGeminiNotebookAmbiguousError(error)" in shared
    assert "automaticRetry: false" in shared
    assert "rawDownloadUrlExported: false" in shared
    assert "privateProtocolBodyRead: false" in shared
    assert "finalDestinationWritten: false" in shared


def test_media_family_and_historical_completion_contracts_remain_distinct() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    audio = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)",
        1,
    )[0]
    video = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert 'mediaFamily: "audio"' in audio
    assert "requireCompletedExactRef: false" in audio
    assert "includeMediaFamily: false" in audio

    assert 'mediaFamily: "video"' in video
    assert "requireCompletedExactRef: true" in video
    assert "includeMediaFamily: true" in video
