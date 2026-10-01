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

GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_PROBE_OPERATION = (
    "gemini_notebook_video_artifact_menu_probe"
)
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_video_artifact_menu(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Open the exact completed Video artifact menu without activating an item."""

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
        "type": GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_PROBE_OPERATION,
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
            "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_video_artifact_menu_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("observedArtifactRef") != expected_artifact_ref:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_REF_MISMATCH")
    if response.get("menuClickPerformed") is not True:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_CLICK_UNPROVEN")
    if response.get("productWritePerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_WRITE_MISMATCH")
    if response.get("navigationPerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_NAVIGATION_MISMATCH")
    if response.get("downloadPerformed") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DOWNLOAD_UNEXPECTED")
    if response.get("rawDomExported") is not False:
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_RAW_DOM_EXPORTED")

    menu = response.get("menu")
    if not isinstance(menu, dict):
        raise RequestError("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_INVALID")

    download_count = response.get("downloadCandidateCount")
    if isinstance(download_count, bool) or not isinstance(download_count, int):
        raise RequestError(
            "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DOWNLOAD_CANDIDATE_COUNT_INVALID"
        )

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "observed_artifact_ref": expected_artifact_ref,
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
        "menu_trigger_aria_controls": str(
            response.get("menuTriggerAriaControls") or ""
        ),
        "menu_trigger_aria_expanded": str(
            response.get("menuTriggerAriaExpanded") or ""
        ),
        "menu": menu,
        "download_candidate_count": download_count,
        "download_action_structurally_proven": (
            response.get("downloadActionStructurallyProven") is True
        ),
        "menu_click_performed": True,
        "product_write_performed": False,
        "navigation_performed": False,
        "download_performed": False,
        "raw_dom_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open and characterize the exact completed Gemini Notebook Video artifact "
            "menu without activating Download or any other menu item."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_video_artifact_menu(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
