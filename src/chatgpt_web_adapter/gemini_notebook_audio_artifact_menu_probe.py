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

GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION = (
    "gemini_notebook_audio_artifact_menu_probe"
)
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")


def probe_gemini_notebook_audio_artifact_menu(
    *,
    notebook: str,
    expected_artifact_ref: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Open one exact artifact menu and read its items without activating one."""

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
        "type": GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION,
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
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_audio_artifact_menu_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_menu_probe",
        )
    if response.get("notebookUrl") != notebook_url:
        raise RequestError(
            "GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_menu_probe",
        )
    if response.get("observedArtifactRef") != expected_artifact_ref:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH",
            request_stage="gemini_notebook_audio_artifact_menu_probe",
        )
    if response.get("menuClickPerformed") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_CLICK_UNPROVEN",
            request_stage="gemini_notebook_audio_artifact_menu_probe",
        )
    for key in (
        "productWritePerformed",
        "navigationPerformed",
        "downloadPerformed",
        "rawDomExported",
    ):
        if response.get(key) is not False:
            raise RequestError(
                f"GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_SAFETY_MISMATCH:{key}",
                request_stage="gemini_notebook_audio_artifact_menu_probe",
            )

    menu = response.get("menu")
    if not isinstance(menu, dict):
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PAYLOAD_INVALID",
            request_stage="gemini_notebook_audio_artifact_menu_probe",
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
        "menu_trigger_aria_controls": str(
            response.get("menuTriggerAriaControls") or ""
        ),
        "menu_trigger_aria_expanded": str(
            response.get("menuTriggerAriaExpanded") or ""
        ),
        "menu": menu,
        "menu_click_performed": True,
        "product_write_performed": False,
        "navigation_performed": False,
        "download_performed": False,
        "raw_dom_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-click Gemini Notebook artifact menu characterization; "
            "menu items are never activated."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--expected-artifact-ref", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_artifact_menu(
        notebook=args.notebook,
        expected_artifact_ref=args.expected_artifact_ref,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
