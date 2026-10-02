from __future__ import annotations

from pathlib import Path
from typing import Any

from ._gemini_notebook_artifact_byte_orchestration import (
    _retrieve_gemini_notebook_artifact_bytes,
)
from ._gemini_notebook_artifact_staging import (
    _ArtifactByteChunkCollector,
    _normalize_artifact_max_bytes,
)
from .browser_native_provider import BrowserNativeTurnProvider

_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_OPERATION = (
    "gemini_notebook_video_artifact_retrieval"
)
_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_CHUNK_TYPE = (
    "gemini_notebook_video_artifact_retrieval_chunk"
)
DEFAULT_VIDEO_ARTIFACT_MAX_BYTES = 64 * 1024 * 1024
_MAX_VIDEO_ARTIFACT_BYTES = 64 * 1024 * 1024


class _VideoArtifactByteChunkCollector(_ArtifactByteChunkCollector):
    def __init__(
        self,
        *,
        request_id: str,
        staging_path: Path,
        max_bytes: int,
    ) -> None:
        super().__init__(
            request_id=request_id,
            staging_path=staging_path,
            max_bytes=max_bytes,
            error_prefix="VIDEO_ARTIFACT",
        )


def _normalize_max_bytes(value: int) -> int:
    return _normalize_artifact_max_bytes(
        value,
        maximum=_MAX_VIDEO_ARTIFACT_BYTES,
    )


def _retrieve_gemini_notebook_video_artifact_bytes(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 120.0,
    max_bytes: int = DEFAULT_VIDEO_ARTIFACT_MAX_BYTES,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Acquire exact product-created Video bytes into verified temporary staging."""

    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")
    max_bytes = _normalize_max_bytes(max_bytes)
    return _retrieve_gemini_notebook_artifact_bytes(
        notebook=notebook,
        expected_artifact_ref=expected_artifact_ref,
        timeout=timeout,
        max_bytes=max_bytes,
        bridge=bridge,
        operation=_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_OPERATION,
        chunk_type=_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RETRIEVAL_CHUNK_TYPE,
        result_type="gemini_notebook_video_artifact_retrieval_result",
        request_stage="gemini_notebook_video_artifact_retrieval",
        error_prefix="GEMINI_NOTEBOOK_VIDEO_ARTIFACT",
        staging_prefix=".cwa-notebook-video-",
        collector_factory=_VideoArtifactByteChunkCollector,
        media_family="video",
    )
