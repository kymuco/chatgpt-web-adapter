from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_artifact_byte_probe import (
    DEFAULT_AUDIO_ARTIFACT_MAX_BYTES,
    GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE,
    GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION,
    _AudioArtifactByteChunkCollector,
    _normalize_max_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"


def test_byte_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION == (
        "gemini_notebook_audio_artifact_byte_probe"
    )
    assert GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE == (
        "gemini_notebook_audio_artifact_byte_chunk"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_artifact_bytes")


def test_byte_probe_max_bytes_is_bounded() -> None:
    assert DEFAULT_AUDIO_ARTIFACT_MAX_BYTES == 64 * 1024 * 1024
    assert _normalize_max_bytes(1) == 1
    assert _normalize_max_bytes(DEFAULT_AUDIO_ARTIFACT_MAX_BYTES) == (
        DEFAULT_AUDIO_ARTIFACT_MAX_BYTES
    )
    with pytest.raises(ValueError):
        _normalize_max_bytes(DEFAULT_AUDIO_ARTIFACT_MAX_BYTES + 1)


def test_byte_chunk_collector_verifies_staging_integrity(tmp_path: Path) -> None:
    payload = b"notebook-audio-bytes\x00\x01"
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode("ascii")
    midpoint = len(encoded) // 2
    midpoint -= midpoint % 4
    chunks = [encoded[:midpoint], encoded[midpoint:]]
    staging = tmp_path / "artifact.part"
    collector = _AudioArtifactByteChunkCollector(
        request_id="r1",
        staging_path=staging,
        max_bytes=1024,
    )
    try:
        for index, data in enumerate(chunks):
            collector.add(
                {
                    "request_id": "r1",
                    "chunkIndex": index,
                    "chunkCount": len(chunks),
                    "totalBytes": len(payload),
                    "sha256": digest,
                    "data": data,
                }
            )
        size, actual_digest = collector.finish(
            {
                "chunkCount": len(chunks),
                "totalBytes": len(payload),
                "sha256": digest,
            }
        )
    finally:
        collector.close()

    assert size == len(payload)
    assert actual_digest == digest
    assert staging.read_bytes() == payload


def test_byte_chunk_collector_rejects_digest_mismatch(tmp_path: Path) -> None:
    payload = b"wrong-digest"
    staging = tmp_path / "artifact.part"
    collector = _AudioArtifactByteChunkCollector(
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
                "sha256": "0" * 64,
                "data": base64.b64encode(payload).decode("ascii"),
            }
        )
        with pytest.raises(
            ValueError,
            match="AUDIO_ARTIFACT_BYTE_DIGEST_MISMATCH",
        ):
            collector.finish(
                {
                    "chunkCount": 1,
                    "totalBytes": len(payload),
                    "sha256": "0" * 64,
                }
            )
    finally:
        collector.close()


def test_worker_keeps_private_locator_out_of_sanitized_sink_read() -> None:
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
    read = worker.split(
        "function _cwaGeminiNotebookReadDownloadSinkProbeExpression()",
        1,
    )[1].split(
        "function _cwaGeminiNotebookRestoreDownloadSinkProbeExpression()",
        1,
    )[0]

    assert "privateWindowOpenLocators" in install
    assert "privateWindowOpenLocators" not in read
    assert "locator" not in read.lower()


def test_worker_byte_probe_uses_product_created_googleusercontent_locator() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    policy = worker.split(
        "function _cwaGeminiNotebookAudioLocatorPolicy(value)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookDecodeIoBytes(data, base64Encoded)",
        1,
    )[0]

    assert 'parsed.protocol !== "https:"' in policy
    assert 'hostname.endsWith(".googleusercontent.com")' in policy
    assert 'originClass: "GOOGLEUSERCONTENT"' in policy
    assert "batchexecute" not in policy
    assert "_cwaGeminiNotebookConfirmTabAbsent" not in worker
    assert "_cwaGeminiNotebookRetireOwnedAcquisitionTab" not in worker


def test_worker_byte_probe_uses_network_resource_stream_without_navigation() -> None:
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

    assert '"Page.getFrameTree"' in acquire
    assert '"Network.loadNetworkResource"' in acquire
    assert "includeCredentials: false" in acquire
    assert "disableCache: true" in acquire
    assert '"IO.read"' in acquire
    assert '"IO.close"' in acquire
    assert 'crypto.subtle.digest("SHA-256", combined)' in acquire
    assert "totalBytes > maxBytes" in acquire
    assert "Page.navigate" not in acquire
    assert "chrome.tabs.create" not in acquire
    assert "Fetch.takeResponseBodyAsStream" not in acquire
    assert "fetch(" not in acquire
    assert "XMLHttpRequest" not in acquire


def test_worker_byte_probe_chunks_verified_bytes_without_raw_locator_export() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "CWA_GEMINI_NOTEBOOK_AUDIO_BYTE_CHUNK_BASE64_CHARS" in probe
    assert "CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE" in probe
    assert "safePortPost(port" in probe
    assert "browserBytesProven: true" in probe
    assert "networkResourceLoadProven:" in probe
    assert "acquisitionTabCreated: false" in probe
    assert "rawDownloadUrlExported: false" in probe
    assert "privateProtocolBodyRead: false" in probe
    assert "finalDestinationWritten: false" in probe
    assert "automaticRetry: false" in probe


def test_byte_probe_host_forwards_chunks_on_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_audio_artifact_byte_probe",' in host
    assert '"gemini_notebook_audio_artifact_byte_probe": 120_000' in host
    assert '"gemini_notebook_audio_artifact_byte_chunk"' in host
    assert 'message.get("type") in {"turn_event", "canonical_read_chunk"}' in host
    assert (
        '"gemini_notebook_audio_artifact_byte_probe",'
        in host.split("event_sink=emit_event", 1)[1]
    )
    assert "_claim_authority_lane(operation, lease_id)" in host


def test_worker_remains_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is unavailable")
    subprocess.run(
        [
            node,
            "--check",
            str(EXT / "service_worker_gemini_notebook_capability.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
