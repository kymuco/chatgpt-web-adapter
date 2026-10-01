from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .gemini_notebook_web import (
    GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
    GeminiNotebookOutcomeAmbiguousError,
    GeminiNotebookWebCapability,
)

GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION = (
    "gemini_notebook_video_generation_probe"
)


def probe_gemini_notebook_video_generation(
    *,
    notebook: str,
    timeout: float = 60.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Start one default Video Overview generation and prove artifact acceptance."""

    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
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
                "GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_FAILED: " + str(error),
                request_stage="gemini_notebook_video_generation_probe",
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
                "GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_FAILED: " + error,
                request_stage="gemini_notebook_video_generation_probe",
            )
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_FAILED: " + error,
            request_stage="gemini_notebook_video_generation_probe",
        )

    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("generationCommitMayHaveExecuted") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_GENERATION_BOUNDARY_UNPROVEN")
    if response.get("generationAcceptedProven") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_GENERATION_ACCEPTANCE_UNPROVEN")
    if response.get("automaticRetry") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_GENERATION_RETRY_POLICY_INVALID")
    if response.get("canonicalCompletionProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_GENERATION_COMPLETION_STATE_INVALID"
        )

    before_refs = response.get("beforeArtifactRefs")
    after_refs = response.get("afterArtifactRefs")
    observed_ref = response.get("observedArtifactRef")
    if not isinstance(before_refs, list) or not isinstance(after_refs, list):
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_GENERATION_ARTIFACT_REFS_INVALID")
    if not isinstance(observed_ref, str) or not observed_ref:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_REF_INVALID")
    if observed_ref in before_refs or observed_ref not in after_refs:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DELTA_UNPROVEN")
    if len(set(after_refs) - set(before_refs)) != 1:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DELTA_AMBIGUOUS")

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "tab_id": (
            response.get("tabId") if isinstance(response.get("tabId"), int) else None
        ),
        "elapsed_ms": (
            response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None
        ),
        "before_artifact_refs": before_refs,
        "after_artifact_refs": after_refs,
        "generation_commit_may_have_executed": True,
        "generation_accepted_proven": True,
        "observed_artifact_ref": observed_ref,
        "artifact_status": str(response.get("artifactStatus") or ""),
        "artifact_title": str(response.get("artifactTitle") or ""),
        "artifact_details": str(response.get("artifactDetails") or ""),
        "artifact_icons": (
            response.get("artifactIcons")
            if isinstance(response.get("artifactIcons"), list)
            else []
        ),
        "start_evidence": str(response.get("startEvidence") or ""),
        "canonical_completion_proven": False,
        "automatic_retry": False,
        "navigation_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start one default Gemini Notebook Video Overview generation and prove "
            "stable artifact acceptance."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_video_generation(
        notebook=args.notebook,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
