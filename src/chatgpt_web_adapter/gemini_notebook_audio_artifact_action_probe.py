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

GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION = (
    "gemini_notebook_audio_artifact_action_probe"
)
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_audio_artifact_action(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Read one exact completed artifact row and its row-scoped controls."""

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
        "type": GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebookUrl": notebook_url,
        "expectedArtifactRef": expected_artifact_ref,
        "timeoutMs": 1,
    }
    response = provider._rpc(  # noqa: SLF001
        request,
        timeout=float(timeout),
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=1.0,
    )

    if response.get("ok") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_audio_artifact_action_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_action_probe",
        )
    if response.get("notebookUrl") != notebook_url:
        raise RequestError(
            "GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_action_probe",
        )
    if response.get("observedArtifactRef") != expected_artifact_ref:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_action_probe",
        )
    for key in (
        "rawDomExported",
        "writePerformed",
        "navigationPerformed",
        "downloadPerformed",
    ):
        if response.get(key) is not False:
            raise RequestError(
                f"GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_SAFETY_MISMATCH:{key}",
                request_stage="gemini_notebook_audio_artifact_action_probe",
            )

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "observed_artifact_ref": expected_artifact_ref,
        "tab_id": response.get("tabId")
        if isinstance(response.get("tabId"), int)
        else None,
        "elapsed_ms": response.get("elapsedMs")
        if isinstance(response.get("elapsedMs"), int)
        else None,
        "row": response.get("row") if isinstance(response.get("row"), dict) else {},
        "controls": response.get("controls")
        if isinstance(response.get("controls"), list)
        else [],
        "more_vert_candidates": response.get("moreVertCandidates")
        if isinstance(response.get("moreVertCandidates"), list)
        else [],
        "raw_dom_exported": False,
        "write_performed": False,
        "navigation_performed": False,
        "download_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Gemini Notebook completed Audio artifact row/action probe."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_artifact_action(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
