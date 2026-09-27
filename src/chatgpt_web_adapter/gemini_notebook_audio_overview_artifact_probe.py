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

GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_OPERATION = (
    "gemini_notebook_audio_overview_artifact_probe"
)
GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID = "audio_overview"
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_audio_overview_artifact(
    *,
    notebook: str,
    expected_artifact_ref: str | None = None,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Observe one stable Audio Overview artifact without mutating the notebook."""

    if timeout < 3.0:
        raise ValueError("timeout must be at least 3 seconds")
    if expected_artifact_ref is not None and not _ARTIFACT_REF_RE.fullmatch(
        expected_artifact_ref
    ):
        raise ValueError("expected_artifact_ref is invalid")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
        "notebookUrl": notebook_url,
        "timeoutMs": 1,
    }
    if expected_artifact_ref is not None:
        request["expectedArtifactRef"] = expected_artifact_ref

    response = provider._rpc(  # noqa: SLF001
        request,
        timeout=float(timeout),
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=1.0,
    )

    if response.get("ok") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PRODUCT_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("probeId") != GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("notebookUrl") != notebook_url:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_NOTEBOOK_IDENTITY_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("artifactObservationStable") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_OBSERVATION_UNSTABLE",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    observed_ref = response.get("observedArtifactRef")
    if not isinstance(observed_ref, str) or not _ARTIFACT_REF_RE.fullmatch(
        observed_ref
    ):
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_REF_INVALID",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if expected_artifact_ref is not None and observed_ref != expected_artifact_ref:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_REF_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("completionProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_COMPLETION_MUST_REMAIN_UNPROVEN",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("canonicalCompletionProven") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CANONICAL_COMPLETION_MUST_REMAIN_UNPROVEN",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("automaticRetry") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_AUTOMATIC_RETRY_FORBIDDEN",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("writePerformed") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_WRITE_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    if response.get("navigationPerformed") is not False:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_NAVIGATION_MISMATCH",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )

    artifact = response.get("artifact")
    if not isinstance(artifact, dict):
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PAYLOAD_INVALID",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
        )
    status_candidate = artifact.get("statusCandidate")
    if status_candidate not in {
        "PENDING_CANDIDATE",
        "NON_PENDING_CANDIDATE",
        "UNKNOWN",
    }:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_STATUS_INVALID",
            request_stage="gemini_notebook_audio_overview_artifact_probe",
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
        "observed_artifact_ref": observed_ref,
        "artifact_observation_stable": True,
        "artifact": artifact,
        "empty_marker": response.get("emptyMarker") is True,
        "completion_proven": False,
        "canonical_completion_proven": False,
        "automatic_retry": False,
        "write_performed": False,
        "navigation_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only stable Audio Overview artifact observation."
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_overview_artifact(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
