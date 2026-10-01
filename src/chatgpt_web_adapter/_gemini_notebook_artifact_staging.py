from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
from typing import Any


class _ArtifactByteChunkCollector:
    def __init__(
        self,
        *,
        request_id: str,
        staging_path: Path,
        max_bytes: int,
        error_prefix: str,
    ) -> None:
        self.request_id = request_id
        self.staging_path = staging_path
        self.max_bytes = max_bytes
        self.error_prefix = error_prefix
        self.chunk_count: int | None = None
        self.total_bytes: int | None = None
        self.sha256: str | None = None
        self.next_index = 0
        self.received_bytes = 0
        self.digest = hashlib.sha256()
        self.handle = staging_path.open("wb")

    def _error(self, suffix: str) -> ValueError:
        return ValueError(f"{self.error_prefix}_BYTE_{suffix}")

    def add(self, frame: dict[str, Any]) -> None:
        if frame.get("request_id") != self.request_id:
            raise self._error("CHUNK_REQUEST_MISMATCH")

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
            raise self._error("CHUNK_INDEX_INVALID")
        if (
            isinstance(total_bytes, bool)
            or not isinstance(total_bytes, int)
            or total_bytes < 0
            or total_bytes > self.max_bytes
        ):
            raise self._error("TOTAL_INVALID")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise self._error("DIGEST_INVALID")
        if not isinstance(data, str):
            raise self._error("CHUNK_DATA_INVALID")

        manifest = (count, total_bytes, digest.lower())
        if self.chunk_count is not None and manifest != (
            self.chunk_count,
            self.total_bytes,
            self.sha256,
        ):
            raise self._error("CHUNK_MANIFEST_MISMATCH")

        try:
            decoded = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as error:
            raise self._error("CHUNK_BASE64_INVALID") from error

        self.received_bytes += len(decoded)
        if self.received_bytes > self.max_bytes:
            raise self._error("LIMIT_EXCEEDED")

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
            raise self._error("FINAL_MANIFEST_MISMATCH")
        if self.chunk_count is None or self.next_index != self.chunk_count:
            raise self._error("CHUNK_MISSING")
        if self.total_bytes != self.received_bytes:
            raise self._error("TOTAL_MISMATCH")

        self.handle.flush()
        os.fsync(self.handle.fileno())
        actual_digest = self.digest.hexdigest()
        if self.sha256 is None or not hmac.compare_digest(
            actual_digest,
            self.sha256,
        ):
            raise self._error("DIGEST_MISMATCH")

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
            raise self._error("STAGING_SIZE_MISMATCH")
        if not hmac.compare_digest(file_digest.hexdigest(), actual_digest):
            raise self._error("STAGING_DIGEST_MISMATCH")
        return file_size, actual_digest

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()


def _normalize_artifact_max_bytes(value: int, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_bytes must be a positive integer")
    if value > maximum:
        raise ValueError(f"max_bytes must be <= {maximum}")
    return value
