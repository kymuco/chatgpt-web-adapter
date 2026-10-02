from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter._gemini_notebook_video_artifact_retrieval import (
    _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_CHUNK_TYPE,
    _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_OPERATION,
    DEFAULT_VIDEO_ARTIFACT_MAX_BYTES,
    _normalize_max_bytes,
    _VideoArtifactByteChunkCollector,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"


def test_video_retrieval_stays_private() -> None:
    assert _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_OPERATION == (
        "gemini_notebook_video_artifact_retrieval"
    )
    assert _GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_CHUNK_TYPE == (
        "gemini_notebook_video_artifact_retrieval_chunk"
    )
    assert not hasattr(adapter, "_retrieve_gemini_notebook_video_artifact_bytes")


def test_video_retrieval_max_bytes_is_bounded() -> None:
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


def test_video_retrieval_reuses_exact_ref_handoff_and_video_media_family() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookWaitForStableExactArtifact(" in probe
    assert 'statusCandidate !== "NON_PENDING_CANDIDATE"' in probe
    assert "_cwaGeminiNotebookClickExactArtifactMoreMenuExpression(" in probe
    assert 'item.icons.includes("save_alt")' in probe
    assert "_cwaGeminiNotebookInstallDownloadSinkProbeExpression()" in probe
    assert "_cwaGeminiNotebookTakeUniqueWindowOpenLocatorExpression()" in probe
    assert "_cwaGeminiNotebookAudioLocatorPolicy(" in probe
    assert "_cwaGeminiNotebookLoadLocatorBytes(" in probe
    assert '"video"' in probe
    assert "CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_CHUNK_TYPE" in probe
    assert "safePortPost(port" in probe
    assert 'mediaFamily: "video"' in probe
    assert "rawDownloadUrlExported: false" in probe
    assert "privateProtocolBodyRead: false" in probe
    assert "finalDestinationWritten: false" in probe
    assert "automaticRetry: false" in probe


def test_video_byte_effect_boundary_precedes_download_click_and_retrieval() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    sink = probe.index("_cwaGeminiNotebookInstallDownloadSinkProbeExpression()")
    boundary = probe.index("downloadAttemptMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()")
    load = probe.index("_cwaGeminiNotebookLoadLocatorBytes(")
    assert sink < boundary < click < load
    assert probe.count("downloadAttemptMayHaveExecuted = false") == 1
    assert "if (downloadAttemptMayHaveExecuted)" in probe


def test_video_retrieval_host_forwards_chunks_on_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_artifact_retrieval",' in host
    assert '"gemini_notebook_video_artifact_retrieval": 120_000' in host
    assert '"gemini_notebook_video_artifact_retrieval_chunk"' in host
    assert (
        '"gemini_notebook_video_artifact_retrieval",'
        in host.split("event_sink=emit_event", 1)[1]
    )
    assert "_claim_authority_lane(operation, lease_id)" in host
