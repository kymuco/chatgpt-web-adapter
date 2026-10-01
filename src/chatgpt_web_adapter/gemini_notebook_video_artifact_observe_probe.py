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
    GeminiNotebookWebCapability,
)

GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION = (
    "gemini_notebook_video_artifact_observe_probe"
)
GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE = "PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_PENDING"
GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY = (
    "PAGE_DOM_DURABLE_BACKGROUND_VIDEO_ARTIFACT_COMPLETION"
)
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_video_artifact_observation(
    *,
    notebook: str,
    observed_artifact_ref: str,
    timeout: float = 60.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Observe exact Video artifact finality without starting new generation."""

    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")
    if not isinstance(observed_artifact_ref, str) or not _ARTIFACT_REF_RE.fullmatch(
        observed_artifact_ref
    ):
        raise ValueError("observed_artifact_ref is invalid")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "observedArtifactRef": observed_artifact_ref,
        "timeoutMs": 1,
    }
    response = provider._rpc(  # noqa: SLF001
        request,
        timeout=float(timeout),
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=2.0,
    )

    if response.get("ok") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_video_artifact_observe_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("observedArtifactRef") != observed_artifact_ref:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_REF_MISMATCH")
    if response.get("canonicalCompletionProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_CANONICAL_COMPLETION_MUST_REMAIN_UNPROVEN"
        )
    if response.get("automaticRetry") is not False:
        raise RequestError("GEMINI_NOTEBOOK_AUTOMATIC_RETRY_FORBIDDEN")
    if response.get("writePerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_OBSERVATION_WRITE_MISMATCH")

    status = response.get("artifactStatus")
    completion = response.get("completionProven")
    reload_verified = response.get("reloadVerified")
    finality = response.get("finalityEvidence")
    navigated = response.get("navigationPerformed")

    if status == "PENDING":
        if (
            completion is not False
            or reload_verified is not False
            or finality != GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE
            or navigated is not False
        ):
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_PENDING_CONTRACT_INVALID")
    elif status == "COMPLETED":
        if (
            completion is not True
            or reload_verified is not True
            or finality != GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY
            or navigated is not True
        ):
            raise RequestError("GEMINI_NOTEBOOK_VIDEO_COMPLETION_CONTRACT_INVALID")
    else:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_STATUS_INVALID")

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "observed_artifact_ref": observed_artifact_ref,
        "artifact_status": status,
        "artifact_title": str(response.get("artifactTitle") or ""),
        "artifact_details": str(response.get("artifactDetails") or ""),
        "artifact_icons": (
            response.get("artifactIcons")
            if isinstance(response.get("artifactIcons"), list)
            else []
        ),
        "tab_id": (
            response.get("tabId") if isinstance(response.get("tabId"), int) else None
        ),
        "elapsed_ms": (
            response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None
        ),
        "completion_proven": completion is True,
        "reload_verified": reload_verified is True,
        "finality_evidence": finality,
        "canonical_completion_proven": False,
        "automatic_retry": False,
        "write_performed": False,
        "navigation_performed": navigated is True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Observe exact Gemini Notebook Video artifact pending/completion finality "
            "without starting a new generation."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--observed-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_video_artifact_observation(
        notebook=args.notebook,
        observed_artifact_ref=args.observed_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
