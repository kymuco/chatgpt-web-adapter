from __future__ import annotations

import json
import uuid

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError


def main() -> int:
    bridge = BrowserNativeTurnProvider(connect_timeout=3.0, turn_timeout=10.0)
    health = bridge.status()
    if not health.available or not health.extension_connected:
        raise RuntimeError(
            "GOOGLE_TRANSLATE_CHARACTERIZATION_BROWSER_BRIDGE_UNAVAILABLE"
        )

    response = bridge._rpc(  # noqa: SLF001
        {
            "type": "characterize_translate_result",
            "request_id": uuid.uuid4().hex,
            "timeoutMs": 10_000,
        },
        timeout=10.0,
    )
    if response.get("ok") is not True:
        raise RequestError(
            "GOOGLE_TRANSLATE_CHARACTERIZATION_FAILED:"
            f"{response.get('error') or 'unknown error'}",
            request_stage="google_translate_characterization",
        )

    payload = {
        "result": "PASS",
        "read_only": True,
        "url": response.get("url"),
        "candidate_count": response.get("candidateCount"),
        "candidates": response.get("candidates"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
