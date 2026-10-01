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

GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION = "gemini_notebook_video_config_probe"


def probe_gemini_notebook_video_config(
    *,
    notebook: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Open the exact Video Overview config surface without starting generation."""

    if timeout < 3.0:
        raise ValueError("timeout must be at least 3 seconds")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION,
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
                "GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_FAILED: " + str(error),
                request_stage="gemini_notebook_video_config_probe",
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
                "GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_FAILED: " + error,
                request_stage="gemini_notebook_video_config_probe",
            )
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_FAILED: " + error,
            request_stage="gemini_notebook_video_config_probe",
        )

    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("createControlIcon") != "videocam":
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CREATE_CONTROL_IDENTITY_UNPROVEN")
    if response.get("configurationSurfaceObserved") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_SURFACE_UNPROVEN")
    if response.get("artifactLibraryUnchanged") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_ARTIFACT_LIBRARY_CHANGED")
    if response.get("configurationOpenClickPerformed") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_CLICK_UNPROVEN")
    if response.get("generationStartedProven") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_GENERATION_STATE_INVALID")
    if response.get("durableProductWriteProven") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_WRITE_STATE_INVALID")
    if response.get("navigationPerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_NAVIGATION_MISMATCH")
    if response.get("automaticRetry") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_RETRY_POLICY_INVALID")
    if response.get("rawDomExported") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_RAW_DOM_EXPORTED")

    dialog = response.get("dialog")
    if not isinstance(dialog, dict):
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_DIALOG_INVALID")

    before_refs = response.get("beforeArtifactRefs")
    after_refs = response.get("afterArtifactRefs")
    if not isinstance(before_refs, list) or not isinstance(after_refs, list):
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_ARTIFACT_REFS_INVALID")
    if before_refs != after_refs:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_CONFIG_ARTIFACT_REFS_CHANGED")

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
        "create_control_icon": "videocam",
        "configuration_surface_observed": True,
        "dialog": dialog,
        "before_artifact_refs": before_refs,
        "after_artifact_refs": after_refs,
        "artifact_library_unchanged": True,
        "configuration_open_click_performed": True,
        "generation_started_proven": False,
        "durable_product_write_proven": False,
        "navigation_performed": False,
        "automatic_retry": False,
        "raw_dom_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open and characterize Gemini Notebook Video Overview configuration "
            "without starting generation."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_video_config(
        notebook=args.notebook,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
