from __future__ import annotations

import argparse
import json
import re
import uuid
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .gemini_notebook_web import (
    GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
    GeminiNotebookOutcomeAmbiguousError,
    GeminiNotebookWebCapability,
)

GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION = (
    "gemini_notebook_audio_artifact_download_intent_probe"
)
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_audio_artifact_download_intent(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Click one exact Download action while browser download behavior is denied."""

    if timeout < 3.0:
        raise ValueError("timeout must be at least 3 seconds")
    if not isinstance(expected_artifact_ref, str) or not _ARTIFACT_REF_RE.fullmatch(
        expected_artifact_ref
    ):
        raise ValueError("expected_artifact_ref is invalid")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "expectedArtifactRef": expected_artifact_ref,
        "timeoutMs": 1,
    }

    try:
        response = provider._rpc(  # noqa: SLF001
            request,
            timeout=float(timeout),
            delegated_timeout_ms_key="timeoutMs",
            delegated_response_margin=1.0,
        )
    except RequestError as error:
        if str(error).startswith(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION:"
        ):
            raise GeminiNotebookOutcomeAmbiguousError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_FAILED: "
                + str(error),
                request_stage="gemini_notebook_audio_artifact_download_intent_probe",
            ) from error
        raise

    if response.get("ok") is not True:
        error = str(response.get("error") or "unknown error")
        if error.startswith(
            "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
        ) or error in {
            "BROWSER_NATIVE_EXTENSION_TIMEOUT",
            "BROWSER_NATIVE_HOST_SHUTDOWN",
        }:
            raise GeminiNotebookOutcomeAmbiguousError(
                "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_FAILED: "
                + error,
                request_stage="gemini_notebook_audio_artifact_download_intent_probe",
            )
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_FAILED: "
            + error,
            request_stage="gemini_notebook_audio_artifact_download_intent_probe",
        )

    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("observedArtifactRef") != expected_artifact_ref:
        raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH")
    if response.get("downloadAttemptMayHaveExecuted") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_EFFECT_BOUNDARY_UNPROVEN"
        )
    if response.get("downloadClickPerformed") is not True:
        raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_CLICK_UNPROVEN")
    if response.get("attachmentResponseObserved") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ATTACHMENT_RESPONSE_UNPROVEN"
        )
    if response.get("contentDispositionAttachment") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ATTACHMENT_IDENTITY_UNPROVEN"
        )
    if response.get("responseBlockedBeforeBody") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_RESPONSE_BLOCK_UNPROVEN"
        )
    if response.get("responseBodyRead") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_RESPONSE_BODY_READ_FORBIDDEN"
        )
    if response.get("filesystemArtifactProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_FILESYSTEM_ARTIFACT_FORBIDDEN"
        )
    if response.get("productWritePerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_PRODUCT_WRITE_MISMATCH")
    if response.get("navigationPerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_NAVIGATION_MISMATCH")
    if response.get("automaticRetry") is not False:
        raise RequestError("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_AUTOMATIC_RETRY_FORBIDDEN")
    if response.get("rawDownloadUrlExported") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_RAW_DOWNLOAD_URL_EXPORTED"
        )

    request_id = response.get("fetchRequestId")
    if not isinstance(request_id, str) or not request_id:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_FETCH_REQUEST_ID_INVALID"
        )

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "observed_artifact_ref": expected_artifact_ref,
        "tab_id": (
            response.get("tabId") if isinstance(response.get("tabId"), int) else None
        ),
        "elapsed_ms": (
            response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None
        ),
        "fetch_request_id": request_id,
        "response_status_code": (
            response.get("responseStatusCode")
            if isinstance(response.get("responseStatusCode"), int)
            else None
        ),
        "resource_type": str(response.get("resourceType") or ""),
        "content_disposition_present": (
            response.get("contentDispositionPresent") is True
        ),
        "content_disposition_attachment": True,
        "content_type": str(response.get("contentType") or ""),
        "download_url_origin": str(response.get("downloadUrlOrigin") or ""),
        "download_url_has_query": response.get("downloadUrlHasQuery") is True,
        "download_url_path_suffix": (
            response.get("downloadUrlPathSuffix")
            if isinstance(response.get("downloadUrlPathSuffix"), list)
            else []
        ),
        "download_attempt_may_have_executed": True,
        "download_click_performed": True,
        "attachment_response_observed": True,
        "response_blocked_before_body": True,
        "response_body_read": False,
        "filesystem_artifact_proven": False,
        "product_write_performed": False,
        "navigation_performed": False,
        "automatic_retry": False,
        "raw_download_url_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Characterize one identity-bound Gemini Notebook Audio download intent "
            "while browser download behavior is denied."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_artifact_download_intent(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
