from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import socket
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

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

GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION = (
    "gemini_notebook_audio_artifact_byte_probe"
)
GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE = (
    "gemini_notebook_audio_artifact_byte_chunk"
)
DEFAULT_AUDIO_ARTIFACT_MAX_BYTES = 64 * 1024 * 1024
_MAX_AUDIO_ARTIFACT_BYTES = 64 * 1024 * 1024


class _AudioArtifactByteChunkCollector:
    def __init__(
        self,
        *,
        request_id: str,
        staging_path: Path,
        max_bytes: int,
    ) -> None:
        self.request_id = request_id
        self.staging_path = staging_path
        self.max_bytes = max_bytes
        self.chunk_count: int | None = None
        self.total_bytes: int | None = None
        self.sha256: str | None = None
        self.next_index = 0
        self.received_bytes = 0
        self.digest = hashlib.sha256()
        self.handle = staging_path.open("wb")

    def add(self, frame: dict[str, Any]) -> None:
        if frame.get("request_id") != self.request_id:
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_REQUEST_MISMATCH")

        index = frame.get("chunkIndex")
        count = frame.get("chunkCount")
        total_bytes = frame.get("totalBytes")
        digest = frame.get("sha256")
        data = frame.get("data")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            or index != self.next_index
            or not 0 <= index < count
        ):
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_INDEX_INVALID")
        if (
            isinstance(total_bytes, bool)
            or not isinstance(total_bytes, int)
            or total_bytes < 0
            or total_bytes > self.max_bytes
        ):
            raise ValueError("AUDIO_ARTIFACT_BYTE_TOTAL_INVALID")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise ValueError("AUDIO_ARTIFACT_BYTE_DIGEST_INVALID")
        if not isinstance(data, str):
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_DATA_INVALID")

        manifest = (count, total_bytes, digest.lower())
        if self.chunk_count is not None and manifest != (
            self.chunk_count,
            self.total_bytes,
            self.sha256,
        ):
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_MANIFEST_MISMATCH")

        try:
            decoded = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_BASE64_INVALID") from error

        self.received_bytes += len(decoded)
        if self.received_bytes > self.max_bytes:
            raise ValueError("AUDIO_ARTIFACT_BYTE_LIMIT_EXCEEDED")

        self.chunk_count, self.total_bytes, self.sha256 = manifest
        self.handle.write(decoded)
        self.digest.update(decoded)
        self.next_index += 1

    def finish(self, response: dict[str, Any]) -> tuple[int, str]:
        final_manifest = (
            response.get("chunkCount"),
            response.get("totalBytes"),
            response.get("sha256"),
        )
        expected_manifest = (self.chunk_count, self.total_bytes, self.sha256)
        if final_manifest != expected_manifest:
            raise ValueError("AUDIO_ARTIFACT_BYTE_FINAL_MANIFEST_MISMATCH")
        if self.chunk_count is None or self.next_index != self.chunk_count:
            raise ValueError("AUDIO_ARTIFACT_BYTE_CHUNK_MISSING")
        if self.total_bytes != self.received_bytes:
            raise ValueError("AUDIO_ARTIFACT_BYTE_TOTAL_MISMATCH")

        self.handle.flush()
        os.fsync(self.handle.fileno())
        actual_digest = self.digest.hexdigest()
        if self.sha256 is None or not hmac.compare_digest(
            actual_digest,
            self.sha256,
        ):
            raise ValueError("AUDIO_ARTIFACT_BYTE_DIGEST_MISMATCH")

        file_digest = hashlib.sha256()
        file_size = 0
        with self.staging_path.open("rb") as staged:
            while True:
                chunk = staged.read(1024 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                file_digest.update(chunk)
        if file_size != self.received_bytes:
            raise ValueError("AUDIO_ARTIFACT_STAGING_SIZE_MISMATCH")
        if not hmac.compare_digest(file_digest.hexdigest(), actual_digest):
            raise ValueError("AUDIO_ARTIFACT_STAGING_DIGEST_MISMATCH")
        return file_size, actual_digest

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()


def _normalize_max_bytes(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_bytes must be a positive integer")
    if value > _MAX_AUDIO_ARTIFACT_BYTES:
        raise ValueError(
            f"max_bytes must be <= {_MAX_AUDIO_ARTIFACT_BYTES}"
        )
    return value


def probe_gemini_notebook_audio_artifact_bytes(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 120.0,
    max_bytes: int = DEFAULT_AUDIO_ARTIFACT_MAX_BYTES,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Acquire exact product-created Audio bytes into verified temporary staging."""

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
        "type": GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION,
        "request_id": request_id,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "expectedArtifactRef": artifact_ref,
        "timeoutMs": int(timeout * 1000),
        "maxBytes": max_bytes,
    }

    staging_path: Path | None = None
    collector: _AudioArtifactByteChunkCollector | None = None
    result: dict[str, Any] | None = None
    request_sent = False
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".cwa-notebook-audio-",
            suffix=".part",
            delete=False,
        ) as staging:
            staging_path = Path(staging.name)

        collector = _AudioArtifactByteChunkCollector(
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
                        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROTOCOL_MISMATCH",
                        request_stage="gemini_notebook_audio_artifact_byte_probe",
                    )
                if frame.get("request_id") != request_id:
                    raise RequestError(
                        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_RESPONSE_MISMATCH",
                        request_stage="gemini_notebook_audio_artifact_byte_probe",
                    )
                if frame.get("type") == GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE:
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
                    "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_FAILED: " + error,
                    request_stage="gemini_notebook_audio_artifact_byte_probe",
                )
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_FAILED: " + error,
                request_stage="gemini_notebook_audio_artifact_byte_probe",
            )

        if response.get("type") != "gemini_notebook_audio_artifact_byte_probe_result":
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_RESULT_TYPE_INVALID",
                request_stage="gemini_notebook_audio_artifact_byte_probe",
            )
        if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
            raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
        if response.get("notebookUrl") != notebook_url:
            raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
        if response.get("observedArtifactRef") != artifact_ref:
            raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH")
        if response.get("locatorOriginClass") != "GOOGLEUSERCONTENT":
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_ORIGIN_UNPROVEN"
            )
        if response.get("browserBytesProven") is not True:
            raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BROWSER_BYTES_UNPROVEN")
        if response.get("acquisitionTabRetired") is not True:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACQUISITION_TAB_RETIRE_UNPROVEN"
            )
        if response.get("rawDownloadUrlExported") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_RAW_DOWNLOAD_URL_EXPORTED"
            )
        if response.get("privateProtocolBodyRead") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_PRIVATE_PROTOCOL_BODY_READ"
            )
        if response.get("finalDestinationWritten") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_FINAL_DESTINATION_WRITE_FORBIDDEN"
            )
        if response.get("automaticRetry") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_AUTOMATIC_RETRY_FORBIDDEN"
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
            "normalized_content_type": str(
                response.get("normalizedContentType") or ""
            ),
            "content_disposition_present": (
                response.get("contentDispositionPresent") is True
            ),
            "size_bytes": size_bytes,
            "sha256": sha256,
            "chunk_count": response.get("chunkCount"),
            "browser_bytes_proven": True,
            "staging_materialized_proven": True,
            "staging_integrity_verified": True,
            "acquisition_tab_retired": True,
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
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_FAILED: " + str(error),
                request_stage="gemini_notebook_audio_artifact_byte_probe",
            ) from error
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_BRIDGE_FAILURE: " + str(error),
            request_stage="gemini_notebook_audio_artifact_byte_probe",
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
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_STAGING_RETIRE_UNPROVEN",
            request_stage="gemini_notebook_audio_artifact_byte_probe",
        )
    result["staging_deleted"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire one exact Gemini Notebook Audio artifact into bounded temporary "
            "staging, verify SHA-256, then delete the staging file."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_AUDIO_ARTIFACT_MAX_BYTES,
    )
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_artifact_bytes(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
