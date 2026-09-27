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

GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_OPERATION = (
    "gemini_notebook_audio_overview_generate_probe"
)
GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID = "audio_overview"


def probe_gemini_notebook_audio_overview_generate(
    *,
    notebook: str,
    timeout: float = 30.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Commit default Audio Overview generation once and prove artifact acceptance."""

    if timeout < 5.0:
        raise ValueError("timeout must be at least 5 seconds")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
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
                f"GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_FAILED: {error}",
                request_stage="gemini_notebook_audio_overview_generate_probe",
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
                f"GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_FAILED: {error}",
                request_stage="gemini_notebook_audio_overview_generate_probe",
            )
        raise RequestError(
            f"GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_FAILED: {error}",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )

    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PRODUCT_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("probeId") != GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("notebookUrl") != notebook_url:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_NOTEBOOK_IDENTITY_MISMATCH",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("generationCommitMayHaveExecuted") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATION_EFFECT_BOUNDARY_UNPROVEN",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("generationAcceptedProven") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ACCEPTANCE_UNPROVEN",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("startEvidence") != "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED":
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_START_EVIDENCE_INVALID",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("canonicalCompletionProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_COMPLETION_MUST_REMAIN_UNPROVEN",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )
    if response.get("automaticRetry") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_AUTOMATIC_RETRY_FORBIDDEN",
            request_stage="gemini_notebook_audio_overview_generate_probe",
        )

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "probe_id": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
        "notebook_url": notebook_url,
        "tab_id": response.get("tabId")
        if isinstance(response.get("tabId"), int)
        else None,
        "elapsed_ms": response.get("elapsedMs")
        if isinstance(response.get("elapsedMs"), int)
        else None,
        "generation_commit_may_have_executed": True,
        "generation_accepted_proven": True,
        "post_artifact_state": response.get("postArtifactState")
        if isinstance(response.get("postArtifactState"), dict)
        else {},
        "start_evidence": "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED",
        "canonical_completion_proven": False,
        "automatic_retry": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-click default Gemini Notebook Audio Overview generation probe."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_overview_generate(
        notebook=args.notebook,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
