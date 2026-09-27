from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .gemini_notebook_web import (
    GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
    GeminiNotebookWebCapability,
)

GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION = "gemini_notebook_audio_overview_probe"
GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID = "audio_overview"


def probe_gemini_notebook_audio_overview(
    *,
    notebook: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Read bounded Studio/Audio Overview structure without mutating the notebook."""

    if timeout < 3.0:
        raise ValueError("timeout must be at least 3 seconds")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
        "notebookUrl": notebook_url,
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
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_audio_overview_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PRODUCT_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_probe",
        )
    if response.get("probeId") != GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID_MISMATCH",
            request_stage="gemini_notebook_audio_overview_probe",
        )
    if response.get("notebookUrl") != notebook_url:
        raise RequestError(
            "GEMINI_NOTEBOOK_AUDIO_OVERVIEW_NOTEBOOK_IDENTITY_MISMATCH",
            request_stage="gemini_notebook_audio_overview_probe",
        )
    for key in ("rawDomExported", "writePerformed", "navigationPerformed"):
        if response.get(key) is not False:
            raise RequestError(
                f"GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_SAFETY_MISMATCH:{key}",
                request_stage="gemini_notebook_audio_overview_probe",
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
        "source_panel_found": response.get("sourcePanelFound") is True,
        "source_picker_found": response.get("sourcePickerFound") is True,
        "source_row_count": response.get("sourceRowCount")
        if isinstance(response.get("sourceRowCount"), int)
        else 0,
        "target_controls": response.get("targetControls")
        if isinstance(response.get("targetControls"), list)
        else [],
        "control_sample": response.get("controlSample")
        if isinstance(response.get("controlSample"), list)
        else [],
        "region_candidates": response.get("regionCandidates")
        if isinstance(response.get("regionCandidates"), list)
        else [],
        "raw_dom_exported": False,
        "write_performed": False,
        "navigation_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Gemini Notebook Audio Overview characterization probe."
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_audio_overview(
        notebook=args.notebook,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
