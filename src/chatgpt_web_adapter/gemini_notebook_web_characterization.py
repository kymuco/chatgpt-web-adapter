from __future__ import annotations

import json
import uuid

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError


def main() -> int:
    bridge = BrowserNativeTurnProvider(
        connect_timeout=3.0,
        turn_timeout=10.0,
    )
    status = bridge.status()
    if not status.available or not status.extension_connected:
        raise RequestError(
            "GEMINI_NOTEBOOK_CHARACTERIZATION_BRIDGE_UNAVAILABLE",
            request_stage="gemini_notebook_characterization",
        )

    response = bridge._rpc(  # noqa: SLF001
        {
            "type": "characterize_gemini_notebook",
            "request_id": uuid.uuid4().hex,
            "timeoutMs": 10_000,
        },
        timeout=10.0,
    )
    if response.get("ok") is not True:
        raise RequestError(
            "GEMINI_NOTEBOOK_CHARACTERIZATION_FAILED:"
            + str(response.get("error") or "unknown error"),
            request_stage="gemini_notebook_characterization",
        )

    payload = {
        "result": "PASS",
        "read_only": response.get("readOnly") is True,
        "product_id": response.get("productId"),
        "tab_id": response.get("tabId"),
        "url": response.get("url"),
        "origin": response.get("origin"),
        "title": response.get("title"),
        "heading_count": response.get("headingCount"),
        "headings": response.get("headings"),
        "candidate_count": response.get("candidateCount"),
        "candidates": response.get("candidates"),
        "body_text": response.get("bodyText"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
