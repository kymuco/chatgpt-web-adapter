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

GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION = (
    "gemini_notebook_studio_creation_controls_probe"
)


def probe_gemini_notebook_studio_creation_controls(
    *,
    notebook: str,
    timeout: float = 15.0,
    bridge: BrowserNativeTurnProvider | None = None,
) -> dict[str, Any]:
    """Read visible Studio creation controls without activating one."""

    if timeout < 3.0:
        raise ValueError("timeout must be at least 3 seconds")

    provider = bridge or BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=timeout,
    )
    notebook_url = GeminiNotebookWebCapability._notebook_url(notebook)
    request = {
        "type": GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION,
        "request_id": uuid.uuid4().hex,
        "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
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
            "GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_FAILED: "
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_studio_creation_controls_probe",
        )
    if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
        raise RequestError("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH")
    if response.get("notebookUrl") != notebook_url:
        raise RequestError("GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH")
    if response.get("studioFound") is not True:
        raise RequestError("GEMINI_NOTEBOOK_STUDIO_OWNER_MISSING")
    for key in ("writePerformed", "navigationPerformed", "rawDomExported"):
        if response.get(key) is not False:
            raise RequestError(
                f"GEMINI_NOTEBOOK_STUDIO_PROBE_SAFETY_MISMATCH:{key}"
            )

    controls = response.get("creationControls")
    if not isinstance(controls, list):
        raise RequestError("GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_INVALID")

    return {
        "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
        "notebook_url": notebook_url,
        "tab_id": (
            response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None
        ),
        "elapsed_ms": (
            response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None
        ),
        "studio_found": True,
        "creation_controls": controls,
        "write_performed": False,
        "navigation_performed": False,
        "raw_dom_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read Gemini Notebook Studio creation controls without activating one."
        )
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    result = probe_gemini_notebook_studio_creation_controls(
        notebook=args.notebook,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
