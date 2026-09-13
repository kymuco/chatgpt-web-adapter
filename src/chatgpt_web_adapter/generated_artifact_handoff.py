from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse

from .exceptions import WebChatAdapterError
from .types import ChatConversation, ConversationRef

CHATGPT_ORIGIN = "https://chatgpt.com"
GENERATED_ARTIFACT_HANDOFF_SCHEMA = "cwa.generated_artifact_handoff.v1"
DEFAULT_GENERATED_ARTIFACT_MAX_BYTES = 1024 * 1024 * 1024

_COLLECTION_KEYS = ("files", "items", "data")
_FILENAME_KEYS = ("filename", "file_name", "name")
_SIZE_KEYS = ("size_bytes", "size")
_LOCATOR_KEYS = ("download_url", "url", "href")
_CURL_FILESIZE_EXCEEDED = 63

GeneratedArtifactHandoffStage = Literal[
    "authority",
    "discovery",
    "resolution",
    "retrieval",
    "publish",
    "verification",
]
GeneratedArtifactDestinationState = Literal[
    "unchanged",
    "materialized_verified",
    "published_unverified",
    "unknown_after_publish_attempt",
]


class GeneratedArtifactHandoffError(WebChatAdapterError):
    """Fail-closed generated-artifact handoff failure.

    The error deliberately exposes no product ``file_id``, resolver locator, signed
    query, response body, credentials, or artifact bytes.
    """

    def __init__(
        self,
        reason: str,
        *,
        stage: GeneratedArtifactHandoffStage,
        status_code: int | None = None,
        destination_state: GeneratedArtifactDestinationState = "unchanged",
    ) -> None:
        self.reason = str(reason)
        self.stage = stage
        self.status_code = status_code
        self.destination_state = destination_state
        super().__init__(f"{self.reason} during generated-artifact {self.stage}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "stage": self.stage,
            "status_code": self.status_code,
            "destination_state": self.destination_state,
        }


@dataclass(frozen=True)
class GeneratedArtifactHandoffResult:
    """Verified local materialization of one conversation-owned generated artifact."""

    conversation_id: str
    source_filename: str
    destination: Path
    size_bytes: int
    sha256: str
    overwritten: bool
    integrity_verified: bool = True

    def __post_init__(self) -> None:
        ref = ConversationRef(self.conversation_id)
        object.__setattr__(self, "conversation_id", ref.conversation_id)
        object.__setattr__(
            self, "source_filename", _safe_filename(self.source_filename)
        )
        object.__setattr__(self, "destination", Path(self.destination).absolute())
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise TypeError("size_bytes must be an int")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        try:
            int(self.sha256, 16)
        except ValueError as error:
            raise ValueError("sha256 must be hexadecimal") from error
        object.__setattr__(self, "sha256", self.sha256.lower())
        if self.integrity_verified is not True:
            raise ValueError("successful handoff result must be integrity verified")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GENERATED_ARTIFACT_HANDOFF_SCHEMA,
            "conversation_id": self.conversation_id,
            "source_filename": self.source_filename,
            "destination": str(self.destination),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "overwritten": self.overwritten,
            "integrity_verified": self.integrity_verified,
        }


def _safe_filename(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("artifact filename must be a string")
    filename = value.strip()
    if not filename or len(filename) > 255:
        raise ValueError("artifact filename is required")
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValueError("artifact filename must be a basename")
    if any(ord(char) < 32 for char in filename):
        raise ValueError("artifact filename contains control characters")
    return filename


def _safe_file_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    file_id = value.strip()
    if not file_id or len(file_id) > 192:
        return None
    if any(char in file_id for char in ("/", "?", "#", "\x00")):
        return None
    return file_id


def _safe_size(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _normalize_max_bytes(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_bytes must be a positive integer")
    return value


def _absolute_destination(value: str | Path) -> Path:
    destination = Path(value).expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    return destination.absolute()


def _authorize_destination(destination: Path, *, overwrite: bool) -> bool:
    parent = destination.parent
    if not parent.exists() or not parent.is_dir():
        raise GeneratedArtifactHandoffError(
            "DESTINATION_PARENT_UNAVAILABLE",
            stage="authority",
        )
    if destination.is_symlink():
        raise GeneratedArtifactHandoffError(
            "DESTINATION_SYMLINK_REJECTED",
            stage="authority",
        )
    if not destination.exists():
        return False
    if not destination.is_file():
        raise GeneratedArtifactHandoffError(
            "DESTINATION_NOT_REGULAR_FILE",
            stage="authority",
        )
    if not overwrite:
        raise GeneratedArtifactHandoffError(
            "DESTINATION_EXISTS",
            stage="authority",
        )
    return True


def _header_status(header_text: str) -> int:
    status = 0
    for raw_line in header_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("HTTP/"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    return status


def _run_read_curl(
    client: Any,
    *,
    url: str,
    headers: dict[str, str],
    output_path: Path | None = None,
    max_bytes: int | None = None,
) -> tuple[int, bytes]:
    """Perform one non-redirecting GET without tracing sensitive response bodies."""

    with tempfile.NamedTemporaryFile(delete=False) as header_file:
        header_path = Path(header_file.name)
    try:
        command = client._build_curl_command(
            "GET",
            url,
            headers,
            str(header_path),
            follow_redirects=False,
        )
        if max_bytes is not None:
            command.extend(["--max-filesize", str(max_bytes)])
        if output_path is not None:
            command.extend(["--output", str(output_path)])
        result = subprocess.run(command, capture_output=True)
        header_text = header_path.read_text(encoding="utf-8", errors="replace")
        status = _header_status(header_text)
        if result.returncode == _CURL_FILESIZE_EXCEEDED and max_bytes is not None:
            raise GeneratedArtifactHandoffError(
                "ARTIFACT_SIZE_LIMIT_EXCEEDED",
                stage="retrieval",
                status_code=status or None,
            )
        if result.returncode != 0:
            raise GeneratedArtifactHandoffError(
                "READ_TRANSPORT_FAILED",
                stage="retrieval",
                status_code=status or None,
            )
        return status, b"" if output_path is not None else result.stdout
    except GeneratedArtifactHandoffError:
        raise
    except (OSError, subprocess.SubprocessError) as error:
        raise GeneratedArtifactHandoffError(
            "READ_TRANSPORT_FAILED",
            stage="retrieval",
        ) from error
    finally:
        try:
            header_path.unlink(missing_ok=True)
        except OSError:
            pass


def _authenticated_headers(
    client: Any,
    *,
    conversation_id: str,
    accept: str,
) -> dict[str, str]:
    return client._build_headers(
        {
            "accept": accept,
            "referer": f"{CHATGPT_ORIGIN}/c/{conversation_id}",
        }
    )


def _json_get(
    client: Any,
    *,
    url: str,
    headers: dict[str, str],
    stage: GeneratedArtifactHandoffStage,
) -> tuple[int, Any]:
    try:
        status, raw_body = _run_read_curl(client, url=url, headers=headers)
    except GeneratedArtifactHandoffError as error:
        raise GeneratedArtifactHandoffError(
            error.reason,
            stage=stage,
            status_code=error.status_code,
        ) from error
    if not raw_body:
        return status, None
    try:
        return status, json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeneratedArtifactHandoffError(
            "JSON_RESPONSE_INVALID",
            stage=stage,
            status_code=status or None,
        ) from error


def _collection(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in _COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return None


def _record_filename(record: dict[str, Any]) -> str | None:
    for key in _FILENAME_KEYS:
        value = record.get(key)
        if not isinstance(value, str):
            continue
        try:
            return _safe_filename(value)
        except ValueError:
            continue
    return None


def _record_size(record: dict[str, Any]) -> int | None:
    for key in _SIZE_KEYS:
        value = _safe_size(record.get(key))
        if value is not None:
            return value
    return None


def _select_artifact_record(payload: Any, filename: str) -> tuple[str, int | None]:
    records = _collection(payload)
    if records is None:
        raise GeneratedArtifactHandoffError(
            "FILES_RESPONSE_SHAPE_UNSUPPORTED",
            stage="discovery",
        )
    matches = [
        record
        for record in records
        if isinstance(record, dict) and _record_filename(record) == filename
    ]
    if not matches:
        raise GeneratedArtifactHandoffError(
            "ARTIFACT_NOT_FOUND",
            stage="discovery",
        )
    if len(matches) != 1:
        raise GeneratedArtifactHandoffError(
            "ARTIFACT_SELECTOR_AMBIGUOUS",
            stage="discovery",
        )
    record = matches[0]
    file_id = _safe_file_id(record.get("file_id"))
    if file_id is None:
        raise GeneratedArtifactHandoffError(
            "PRODUCT_FILE_ID_REQUIRED",
            stage="discovery",
        )
    return file_id, _record_size(record)


def _extract_locator(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise GeneratedArtifactHandoffError(
            "RESOLVER_RESPONSE_SHAPE_UNSUPPORTED",
            stage="resolution",
        )
    for key in _LOCATOR_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise GeneratedArtifactHandoffError(
        "RESOLVER_LOCATOR_MISSING",
        stage="resolution",
    )


def _locator_policy(locator: str) -> tuple[str, bool]:
    parsed = urlparse(locator)
    hostname = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as error:
        raise GeneratedArtifactHandoffError(
            "LOCATOR_REJECTED",
            stage="resolution",
        ) from error
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.fragment)
        or port not in {None, 443}
    ):
        raise GeneratedArtifactHandoffError(
            "LOCATOR_REJECTED",
            stage="resolution",
        )
    if hostname == "chatgpt.com":
        return "CHATGPT_SAME_ORIGIN", True
    if hostname == "oaiusercontent.com" or hostname.endswith(".oaiusercontent.com"):
        return "OAIUSERCONTENT", False
    raise GeneratedArtifactHandoffError(
        "LOCATOR_REJECTED",
        stage="resolution",
    )


def _files_endpoint(conversation_id: str) -> str:
    encoded = quote(conversation_id, safe="")
    return f"{CHATGPT_ORIGIN}/backend-api/conversations/{encoded}/files"


def _resolver_endpoint(conversation_id: str, file_id: str) -> str:
    encoded_file_id = quote(file_id, safe="")
    encoded_conversation = quote(conversation_id, safe="")
    return (
        f"{CHATGPT_ORIGIN}/backend-api/files/download/{encoded_file_id}"
        f"?conversation_id={encoded_conversation}&inline=false"
    )


def _file_integrity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _publish_staging(
    staging: Path,
    destination: Path,
    *,
    overwrite: bool,
    destination_existed: bool,
) -> bool:
    try:
        if overwrite:
            os.replace(staging, destination)
            return destination_existed
        os.link(staging, destination)
        staging.unlink()
        return False
    except FileExistsError as error:
        raise GeneratedArtifactHandoffError(
            "DESTINATION_EXISTS",
            stage="publish",
            destination_state="unchanged",
        ) from error
    except OSError as error:
        raise GeneratedArtifactHandoffError(
            "ATOMIC_PUBLISH_FAILED",
            stage="publish",
            destination_state="unknown_after_publish_attempt",
        ) from error


def handoff_generated_artifact(
    self: Any,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
    filename: str,
    destination: str | Path,
    *,
    overwrite: bool = False,
    max_bytes: int = DEFAULT_GENERATED_ARTIFACT_MAX_BYTES,
) -> GeneratedArtifactHandoffResult:
    """Materialize one generated artifact under explicit local destination authority.

    The operation performs one bounded read chain and one local atomic publish. It
    never follows redirects, never forwards ChatGPT credentials to an
    ``oaiusercontent.com`` locator, and never retries a publish after filesystem
    state may have become ambiguous.
    """

    ref = ConversationRef.from_any(conversation)
    source_filename = _safe_filename(filename)
    max_bytes = _normalize_max_bytes(max_bytes)
    destination_path = _absolute_destination(destination)
    destination_existed = _authorize_destination(
        destination_path,
        overwrite=bool(overwrite),
    )

    discovery_headers = _authenticated_headers(
        self,
        conversation_id=ref.conversation_id,
        accept="application/json",
    )
    discovery_status, discovery_payload = _json_get(
        self,
        url=_files_endpoint(ref.conversation_id),
        headers=discovery_headers,
        stage="discovery",
    )
    if not 200 <= discovery_status < 300:
        raise GeneratedArtifactHandoffError(
            "FILES_REQUEST_FAILED",
            stage="discovery",
            status_code=discovery_status or None,
        )
    file_id, source_size = _select_artifact_record(
        discovery_payload,
        source_filename,
    )
    if source_size is not None and source_size > max_bytes:
        raise GeneratedArtifactHandoffError(
            "ARTIFACT_SIZE_LIMIT_EXCEEDED",
            stage="discovery",
        )

    resolution_headers = _authenticated_headers(
        self,
        conversation_id=ref.conversation_id,
        accept="application/json",
    )
    resolution_status, resolution_payload = _json_get(
        self,
        url=_resolver_endpoint(ref.conversation_id, file_id),
        headers=resolution_headers,
        stage="resolution",
    )
    if not 200 <= resolution_status < 300:
        raise GeneratedArtifactHandoffError(
            "RESOLVER_REQUEST_FAILED",
            stage="resolution",
            status_code=resolution_status or None,
        )
    locator = _extract_locator(resolution_payload)
    _origin_class, attach_chatgpt_auth = _locator_policy(locator)

    if attach_chatgpt_auth:
        locator_headers = _authenticated_headers(
            self,
            conversation_id=ref.conversation_id,
            accept="*/*",
        )
    else:
        locator_headers = {
            "accept": "*/*",
            "user-agent": self.base_headers.get("user-agent", ""),
        }

    staging: Path | None = None
    published = False
    try:
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination_path.name}.cwa-",
                suffix=".part",
                dir=destination_path.parent,
                delete=False,
            ) as staging_file:
                staging = Path(staging_file.name)
        except OSError as error:
            raise GeneratedArtifactHandoffError(
                "STAGING_CREATE_FAILED",
                stage="authority",
            ) from error

        try:
            locator_status, _ = _run_read_curl(
                self,
                url=locator,
                headers=locator_headers,
                output_path=staging,
                max_bytes=max_bytes,
            )
        except GeneratedArtifactHandoffError as error:
            raise GeneratedArtifactHandoffError(
                error.reason,
                stage="retrieval",
                status_code=error.status_code,
            ) from error
        if 300 <= locator_status < 400:
            raise GeneratedArtifactHandoffError(
                "LOCATOR_REDIRECT_NOT_FOLLOWED",
                stage="retrieval",
                status_code=locator_status,
            )
        if not 200 <= locator_status < 300:
            raise GeneratedArtifactHandoffError(
                "LOCATOR_FETCH_FAILED",
                stage="retrieval",
                status_code=locator_status or None,
            )

        try:
            _fsync_file(staging)
            staged_size, staged_sha256 = _file_integrity(staging)
        except OSError as error:
            raise GeneratedArtifactHandoffError(
                "STAGING_VERIFICATION_FAILED",
                stage="verification",
            ) from error
        if staged_size > max_bytes:
            raise GeneratedArtifactHandoffError(
                "ARTIFACT_SIZE_LIMIT_EXCEEDED",
                stage="retrieval",
            )
        if source_size is not None and source_size != staged_size:
            raise GeneratedArtifactHandoffError(
                "SOURCE_SIZE_MISMATCH",
                stage="verification",
            )

        overwritten = _publish_staging(
            staging,
            destination_path,
            overwrite=bool(overwrite),
            destination_existed=destination_existed,
        )
        published = True

        try:
            materialized_size, materialized_sha256 = _file_integrity(destination_path)
        except OSError as error:
            raise GeneratedArtifactHandoffError(
                "POST_WRITE_INTEGRITY_UNAVAILABLE",
                stage="verification",
                destination_state="published_unverified",
            ) from error
        if materialized_size != staged_size or materialized_sha256 != staged_sha256:
            raise GeneratedArtifactHandoffError(
                "POST_WRITE_INTEGRITY_MISMATCH",
                stage="verification",
                destination_state="published_unverified",
            )

        return GeneratedArtifactHandoffResult(
            conversation_id=ref.conversation_id,
            source_filename=source_filename,
            destination=destination_path,
            size_bytes=materialized_size,
            sha256=materialized_sha256,
            overwritten=overwritten,
        )
    finally:
        if staging is not None and staging.exists():
            try:
                staging.unlink()
            except OSError:
                if not published:
                    pass


__all__ = [
    "DEFAULT_GENERATED_ARTIFACT_MAX_BYTES",
    "GENERATED_ARTIFACT_HANDOFF_SCHEMA",
    "GeneratedArtifactHandoffError",
    "GeneratedArtifactHandoffResult",
    "handoff_generated_artifact",
]
