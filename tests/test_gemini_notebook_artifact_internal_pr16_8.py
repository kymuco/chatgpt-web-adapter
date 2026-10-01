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

    assert worker.count("async function _cwaGeminiNotebookProbeArtifactBytes(") == 1

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


def test_audio_and_video_staging_collectors_share_one_internal_core() -> None:
    shared = (PACKAGE / "_gemini_notebook_artifact_staging.py").read_text(
        encoding="utf-8"
    )
    audio = (PACKAGE / "gemini_notebook_audio_artifact_byte_probe.py").read_text(
        encoding="utf-8"
    )
    video = (PACKAGE / "gemini_notebook_video_artifact_byte_probe.py").read_text(
        encoding="utf-8"
    )

    assert "class _ArtifactByteChunkCollector:" in shared
    assert "def _normalize_artifact_max_bytes(" in shared
    assert "os.fsync(self.handle.fileno())" in shared
    assert "hmac.compare_digest(" in shared
    assert 'error_prefix="AUDIO_ARTIFACT"' in audio
    assert 'error_prefix="VIDEO_ARTIFACT"' in video
    assert (
        "class _AudioArtifactByteChunkCollector(_ArtifactByteChunkCollector)" in audio
    )
    assert (
        "class _VideoArtifactByteChunkCollector(_ArtifactByteChunkCollector)" in video
    )


def test_staging_core_is_not_exported_from_package_root() -> None:
    assert not hasattr(adapter, "_ArtifactByteChunkCollector")
    assert not hasattr(adapter, "_normalize_artifact_max_bytes")


def test_audio_and_video_python_probes_share_one_private_orchestration_core() -> None:
    shared = (PACKAGE / "_gemini_notebook_artifact_byte_orchestration.py").read_text(
        encoding="utf-8"
    )
    audio = (PACKAGE / "gemini_notebook_audio_artifact_byte_probe.py").read_text(
        encoding="utf-8"
    )
    video = (PACKAGE / "gemini_notebook_video_artifact_byte_probe.py").read_text(
        encoding="utf-8"
    )

    assert "def _probe_gemini_notebook_artifact_bytes(" in shared
    assert "send_local_message(sock, request)" in shared
    assert "recv_local_message(sock)" in shared
    assert "collector.finish(response)" in shared
    assert 'result["staging_deleted"] = True' in shared

    assert "_probe_gemini_notebook_artifact_bytes(" in audio
    assert 'error_prefix="GEMINI_NOTEBOOK_AUDIO_ARTIFACT"' in audio
    assert 'staging_prefix=".cwa-notebook-audio-"' in audio
    assert "media_family=" not in audio

    assert "_probe_gemini_notebook_artifact_bytes(" in video
    assert 'error_prefix="GEMINI_NOTEBOOK_VIDEO_ARTIFACT"' in video
    assert 'staging_prefix=".cwa-notebook-video-"' in video
    assert 'media_family="video"' in video


def test_python_orchestration_core_is_not_exported_from_package_root() -> None:
    assert not hasattr(adapter, "_probe_gemini_notebook_artifact_bytes")
