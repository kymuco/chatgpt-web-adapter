from __future__ import annotations

import socket
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ._gemini_notebook_artifact_staging import _ArtifactByteChunkCollector
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


def _retrieve_gemini_notebook_artifact_bytes(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float,
    max_bytes: int,
    bridge: BrowserNativeTurnProvider | None,
    operation: str,
    chunk_type: str,
    result_type: str,
    request_stage: str,
    error_prefix: str,
    staging_prefix: str,
    collector_factory: Callable[..., _ArtifactByteChunkCollector],
    media_family: str | None = None,
) -> dict[str, Any]:
    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")

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
        "type": operation,
        "request_id": request_id,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "expectedArtifactRef": artifact_ref,
        "timeoutMs": int(timeout * 1000),
        "maxBytes": max_bytes,
    }

    staging_path: Path | None = None
    collector: _ArtifactByteChunkCollector | None = None
    result: dict[str, Any] | None = None
    request_sent = False
    try:
        with tempfile.NamedTemporaryFile(
            prefix=staging_prefix,
            suffix=".part",
            delete=False,
        ) as staging:
            staging_path = Path(staging.name)

        collector = collector_factory(
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
                        f"{error_prefix}_BYTE_PROTOCOL_MISMATCH",
                        request_stage=request_stage,
                    )
                if frame.get("request_id") != request_id:
                    raise RequestError(
                        f"{error_prefix}_BYTE_RESPONSE_MISMATCH",
                        request_stage=request_stage,
                    )
                if frame.get("type") == chunk_type:
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
                    f"{error_prefix}_RETRIEVAL_FAILED: {error}",
                    request_stage=request_stage,
                )
            raise RequestError(
                f"{error_prefix}_RETRIEVAL_FAILED: {error}",
                request_stage=request_stage,
            )

        if response.get("type") != result_type:
            raise RequestError(
                f"{error_prefix}_BYTE_RESULT_TYPE_INVALID",
                request_stage=request_stage,
            )
        if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
            raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
        if response.get("notebookUrl") != notebook_url:
            raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
        if response.get("observedArtifactRef") != artifact_ref:
            raise RequestError(f"{error_prefix}_REF_MISMATCH")
        if response.get("locatorOriginClass") != "GOOGLEUSERCONTENT":
            raise RequestError(f"{error_prefix}_LOCATOR_ORIGIN_UNPROVEN")
        if response.get("browserBytesProven") is not True:
            raise RequestError(f"{error_prefix}_BROWSER_BYTES_UNPROVEN")
        if response.get("networkResourceLoadProven") is not True:
            raise RequestError(f"{error_prefix}_NETWORK_RESOURCE_LOAD_UNPROVEN")
        if response.get("authenticatedBrowserRequestProven") is not True:
            raise RequestError(f"{error_prefix}_AUTHENTICATED_REQUEST_UNPROVEN")
        if media_family is not None and response.get("mediaFamily") != media_family:
            raise RequestError(f"{error_prefix}_MEDIA_FAMILY_UNPROVEN")
        if response.get("acquisitionTabCreated") is not False:
            raise RequestError(f"{error_prefix}_ACQUISITION_TAB_UNEXPECTED")
        if response.get("rawDownloadUrlExported") is not False:
            raise RequestError(f"{error_prefix}_RAW_DOWNLOAD_URL_EXPORTED")
        if response.get("privateProtocolBodyRead") is not False:
            raise RequestError(f"{error_prefix}_PRIVATE_PROTOCOL_BODY_READ")
        if response.get("finalDestinationWritten") is not False:
            raise RequestError(f"{error_prefix}_FINAL_DESTINATION_WRITE_FORBIDDEN")
        if response.get("automaticRetry") is not False:
            raise RequestError(f"{error_prefix}_AUTOMATIC_RETRY_FORBIDDEN")

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
            "acquisition_tab_created": False,
            "raw_download_url_exported": False,
            "private_protocol_body_read": False,
            "final_destination_written": False,
            "automatic_retry": False,
        }
        if media_family is not None:
            result["media_family"] = media_family
    except GeminiNotebookOutcomeAmbiguousError:
        raise
    except (OSError, EOFError, ValueError) as error:
        if request_sent:
            raise GeminiNotebookOutcomeAmbiguousError(
                f"{error_prefix}_RETRIEVAL_FAILED: {error}",
                request_stage=request_stage,
            ) from error
        raise RequestError(
            f"{error_prefix}_BYTE_BRIDGE_FAILURE: {error}",
            request_stage=request_stage,
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
        raise AssertionError("unreachable artifact retrieval result")
    if not staging_deleted:
        raise RequestError(
            f"{error_prefix}_STAGING_RETIRE_UNPROVEN",
            request_stage=request_stage,
        )
    result["staging_deleted"] = True
    return result
