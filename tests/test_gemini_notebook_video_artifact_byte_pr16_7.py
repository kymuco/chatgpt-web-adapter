from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_video_artifact_byte_probe import (
    DEFAULT_VIDEO_ARTIFACT_MAX_BYTES,
    GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE,
    GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_OPERATION,
    _normalize_max_bytes,
    _VideoArtifactByteChunkCollector,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"


def test_video_byte_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_OPERATION == (
        "gemini_notebook_video_artifact_byte_probe"
    )
    assert GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE == (
        "gemini_notebook_video_artifact_byte_chunk"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_video_artifact_bytes")


def test_video_byte_probe_max_bytes_is_bounded() -> None:
    assert DEFAULT_VIDEO_ARTIFACT_MAX_BYTES == 64 * 1024 * 1024
    assert _normalize_max_bytes(1) == 1
    assert _normalize_max_bytes(DEFAULT_VIDEO_ARTIFACT_MAX_BYTES) == (
        DEFAULT_VIDEO_ARTIFACT_MAX_BYTES
    )
    with pytest.raises(ValueError):
        _normalize_max_bytes(DEFAULT_VIDEO_ARTIFACT_MAX_BYTES + 1)


def test_video_byte_chunk_collector_verifies_staging_integrity(
    tmp_path: Path,
) -> None:
    payload = b"notebook-video-bytes\x00\x01"
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode("ascii")
    staging = tmp_path / "artifact.part"
    collector = _VideoArtifactByteChunkCollector(
        request_id="r1",
        staging_path=staging,
        max_bytes=1024,
    )
    try:
        collector.add(
            {
                "request_id": "r1",
                "chunkIndex": 0,
                "chunkCount": 1,
                "totalBytes": len(payload),
                "sha256": digest,
                "data": encoded,
            }
        )
        size, actual_digest = collector.finish(
            {
                "chunkCount": 1,
                "totalBytes": len(payload),
                "sha256": digest,
            }
        )
    finally:
        collector.close()

    assert size == len(payload)
    assert actual_digest == digest
    assert staging.read_bytes() == payload


def test_worker_network_loader_is_media_family_bound() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    acquire = worker.split(
        "async function _cwaGeminiNotebookLoadLocatorBytes(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)",
        1,
    )[0]

    assert 'mediaFamily = "audio"' in acquire
    assert 'mediaFamily === "video" ? "video/" : "audio/"' in acquire
    assert '"Network.loadNetworkResource"' in acquire
    assert "includeCredentials: true" in acquire
    assert '"IO.read"' in acquire
    assert 'crypto.subtle.digest("SHA-256", combined)' in acquire
    assert "Page.navigate" not in acquire


def test_video_byte_probe_reuses_shared_core_with_video_profile() -> None:
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
    video = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookClickExactArtifactMoreMenuExpression(" in shared
    assert 'item.icons.includes("save_alt")' in shared
    assert "_cwaGeminiNotebookInstallDownloadSinkProbeExpression()" in shared
    assert "_cwaGeminiNotebookTakeUniqueWindowOpenLocatorExpression()" in shared
    assert "_cwaGeminiNotebookAudioLocatorPolicy(" in shared
    assert "_cwaGeminiNotebookLoadLocatorBytes(" in shared
    assert "safePortPost(port" in shared
    assert "rawDownloadUrlExported: false" in shared
    assert "privateProtocolBodyRead: false" in shared
    assert "finalDestinationWritten: false" in shared
    assert "automaticRetry: false" in shared

    assert 'mediaFamily: "video"' in video
    assert 'errorPrefix: "GEMINI_NOTEBOOK_VIDEO_ARTIFACT"' in video
    assert "CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE" in video
    assert "CWA_GEMINI_NOTEBOOK_VIDEO_BYTE_CHUNK_BASE64_CHARS" in video
    assert "requireCompletedExactRef: true" in video
    assert "includeMediaFamily: true" in video


def test_shared_byte_effect_boundary_precedes_download_click_and_retrieval() -> None:
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

    sink = shared.index("_cwaGeminiNotebookInstallDownloadSinkProbeExpression()")
    boundary = shared.index("downloadAttemptMayHaveExecuted = true;")
    click = shared.index("_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()")
    load = shared.index("_cwaGeminiNotebookLoadLocatorBytes(")
    assert sink < boundary < click < load
    assert shared.count("downloadAttemptMayHaveExecuted = false") == 1
    assert "if (downloadAttemptMayHaveExecuted)" in shared


def test_video_byte_host_forwards_chunks_on_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_artifact_byte_probe",' in host
    assert '"gemini_notebook_video_artifact_byte_probe": 120_000' in host
    assert '"gemini_notebook_video_artifact_byte_chunk"' in host
    assert (
        '"gemini_notebook_video_artifact_byte_probe",'
        in host.split("event_sink=emit_event", 1)[1]
    )
    assert "_claim_authority_lane(operation, lease_id)" in host
