from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._gemini_notebook_artifact_byte_orchestration import (
    _probe_gemini_notebook_artifact_bytes,
)
from ._gemini_notebook_artifact_staging import (
    _ArtifactByteChunkCollector,
    _normalize_artifact_max_bytes,
)
from .browser_native_provider import BrowserNativeTurnProvider

GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_OPERATION = (
    "gemini_notebook_video_artifact_byte_probe"
)
GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE = (
    "gemini_notebook_video_artifact_byte_chunk"
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


def probe_gemini_notebook_video_artifact_bytes(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 120.0,
    max_bytes: int = DEFAULT_VIDEO_ARTIFACT_MAX_BYTES,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Acquire exact product-created Video bytes into verified temporary staging."""

    max_bytes = _normalize_max_bytes(max_bytes)
    return _probe_gemini_notebook_artifact_bytes(
        notebook=notebook,
        expected_artifact_ref=expected_artifact_ref,
        timeout=timeout,
        max_bytes=max_bytes,
        bridge=bridge,
        operation=GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_OPERATION,
        chunk_type=GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE,
        result_type="gemini_notebook_video_artifact_byte_probe_result",
        request_stage="gemini_notebook_video_artifact_byte_probe",
        error_prefix="GEMINI_NOTEBOOK_VIDEO_ARTIFACT",
        staging_prefix=".cwa-notebook-video-",
        collector_factory=_VideoArtifactByteChunkCollector,
        media_family="video",
    )

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire one exact Gemini Notebook Video artifact into bounded temporary "
            "staging, verify SHA-256, then delete the staging file."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_VIDEO_ARTIFACT_MAX_BYTES,
    )
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_video_artifact_bytes(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
