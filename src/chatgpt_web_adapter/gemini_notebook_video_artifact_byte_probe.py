from __future__ import annotations

import argparse
import json
import socket
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from ._gemini_notebook_artifact_staging import (
    _ArtifactByteChunkCollector,
    _normalize_artifact_max_bytes,
)
from .browser_native_protocol import (
    PROTOCOL_VERSION,
    recv_local_message,
    send_local_message,
)
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .gemini_notebook_web import (
    GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
    GeminiNotebookOutcomeAmbiguousError,
    GeminiNotebookWebCapability,
)

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

    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")
    max_bytes = _normalize_max_bytes(max_bytes)
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    artifact_ref = GeminiNotebookWebCapability._artifact_ref(expected_artifact_ref)
    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )

    descriptor = provider._load_descriptor()  # noqa: SLF001
    request_id = uuid.uuid4().hex
    request = {
        "protocol": PROTOCOL_VERSION,
        "token": descriptor["token"],
        "type": GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_OPERATION,
        "request_id": request_id,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "expectedArtifactRef": artifact_ref,
        "timeoutMs": int(timeout * 1000),
        "maxBytes": max_bytes,
    }

    staging_path: Path | None = None
    collector: _VideoArtifactByteChunkCollector | None = None
    result: dict[str, Any] | None = None
    request_sent = False
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".cwa-notebook-video-",
            suffix=".part",
            delete=False,
        ) as staging:
            staging_path = Path(staging.name)

        collector = _VideoArtifactByteChunkCollector(
            request_id=request_id,
            staging_path=staging_path,
            max_bytes=max_bytes,
        )
        deadline = time.monotonic() + timeout + 6.0
        remaining = max(0.1, deadline - time.monotonic())
        with socket.create_connection(
            (descriptor["host"], descriptor["port"]),
            timeout=min(provider.connect_timeout, remaining),
        ) as sock:
            sock.settimeout(remaining)
            send_local_message(sock, request)
            request_sent = True

            while True:
                frame = recv_local_message(sock)
                if frame.get("protocol") != PROTOCOL_VERSION:
                    raise RequestError(
                        "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROTOCOL_MISMATCH",
                        request_stage="gemini_notebook_video_artifact_byte_probe",
                    )
                if frame.get("request_id") != request_id:
                    raise RequestError(
                        "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_RESPONSE_MISMATCH",
                        request_stage="gemini_notebook_video_artifact_byte_probe",
                    )
                if frame.get("type") == GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_CHUNK_TYPE:
                    collector.add(frame)
                    continue
                response = frame
                break

        if response.get("ok") is not True:
            error = str(response.get("error") or "unknown error")
            if error.startswith(
                "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ) or error in {
                "BROWSER_NATIVE_EXTENSION_TIMEOUT",
                "BROWSER_NATIVE_HOST_SHUTDOWN",
            }:
                raise GeminiNotebookOutcomeAmbiguousError(
                    "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_FAILED: " + error,
                    request_stage="gemini_notebook_video_artifact_byte_probe",
                )
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_FAILED: " + error,
                request_stage="gemini_notebook_video_artifact_byte_probe",
            )

        if response.get("type") != "gemini_notebook_video_artifact_byte_probe_result":
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_RESULT_TYPE_INVALID",
                request_stage="gemini_notebook_video_artifact_byte_probe",
            )
        if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
            raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
        if response.get("notebookUrl") != notebook_url:
            raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
        if response.get("observedArtifactRef") != artifact_ref:
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_REF_MISMATCH")
        if response.get("locatorOriginClass") != "GOOGLEUSERCONTENT":
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_LOCATOR_ORIGIN_UNPROVEN")
        if response.get("browserBytesProven") is not True:
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BROWSER_BYTES_UNPROVEN")
        if response.get("networkResourceLoadProven") is not True:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_NETWORK_RESOURCE_LOAD_UNPROVEN"
            )
        if response.get("authenticatedBrowserRequestProven") is not True:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_AUTHENTICATED_REQUEST_UNPROVEN"
            )
        if response.get("mediaFamily") != "video":
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MEDIA_FAMILY_UNPROVEN")
        if response.get("acquisitionTabCreated") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_ACQUISITION_TAB_UNEXPECTED"
            )
        if response.get("rawDownloadUrlExported") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RAW_DOWNLOAD_URL_EXPORTED"
            )
        if response.get("privateProtocolBodyRead") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_PRIVATE_PROTOCOL_BODY_READ"
            )
        if response.get("finalDestinationWritten") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_FINAL_DESTINATION_WRITE_FORBIDDEN"
            )
        if response.get("automaticRetry") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_AUTOMATIC_RETRY_FORBIDDEN"
            )

        size_bytes, sha256 = collector.finish(response)
        result = {
            "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
            "notebook_url": notebook_url,
            "observed_artifact_ref": artifact_ref,
            "locator_origin_class": "GOOGLEUSERCONTENT",
            "response_status_code": (
                response.get("responseStatusCode")
                if isinstance(response.get("responseStatusCode"), int)
                else None
            ),
            "content_type": str(response.get("contentType") or ""),
            "normalized_content_type": str(response.get("normalizedContentType") or ""),
            "content_disposition_present": (
                response.get("contentDispositionPresent") is True
            ),
            "size_bytes": size_bytes,
            "sha256": sha256,
            "chunk_count": response.get("chunkCount"),
            "browser_bytes_proven": True,
            "staging_materialized_proven": True,
            "staging_integrity_verified": True,
            "network_resource_load_proven": True,
            "authenticated_browser_request_proven": True,
            "media_family": "video",
            "acquisition_tab_created": False,
            "raw_download_url_exported": False,
            "private_protocol_body_read": False,
            "final_destination_written": False,
            "automatic_retry": False,
        }
    except GeminiNotebookOutcomeAmbiguousError:
        raise
    except (OSError, EOFError, ValueError) as error:
        if request_sent:
            raise GeminiNotebookOutcomeAmbiguousError(
                "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_PROBE_FAILED: " + str(error),
                request_stage="gemini_notebook_video_artifact_byte_probe",
            ) from error
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_BYTE_BRIDGE_FAILURE: " + str(error),
            request_stage="gemini_notebook_video_artifact_byte_probe",
        ) from error
    finally:
        if collector is not None:
            collector.close()
        staging_deleted = True
        if staging_path is not None:
            try:
                staging_path.unlink(missing_ok=True)
            except OSError:
                staging_deleted = False
            else:
                staging_deleted = not staging_path.exists()

    if result is None:
        raise AssertionError("unreachable byte-probe result")
    if not staging_deleted:
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_STAGING_RETIRE_UNPROVEN",
            request_stage="gemini_notebook_video_artifact_byte_probe",
        )
    result["staging_deleted"] = True
    return result


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
