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

    try:
        ping = bridge._rpc(  # noqa: SLF001
            {
                "type": "characterize_translate_ping",
                "request_id": uuid.uuid4().hex,
                "timeoutMs": 5_000,
            },
            timeout=5.0,
        )
    except RequestError as error:
        raise RequestError(
            f"GOOGLE_TRANSLATE_CHARACTERIZATION_WORKER_PING_TRANSPORT_FAILED:{error}",
            request_stage="google_translate_characterization_ping",
        ) from error
    if ping.get("ok") is not True:
        raise RequestError(
            "GOOGLE_TRANSLATE_CHARACTERIZATION_WORKER_PING_FAILED:"
            f"{ping.get('error') or 'unknown error'}",
            request_stage="google_translate_characterization",
        )

    try:
        response = bridge._rpc(  # noqa: SLF001
            {
                "type": "characterize_translate_result",
                "request_id": uuid.uuid4().hex,
                "timeoutMs": 10_000,
            },
            timeout=10.0,
        )
    except RequestError as error:
        raise RequestError(
            f"GOOGLE_TRANSLATE_CHARACTERIZATION_DOM_SNAPSHOT_TRANSPORT_FAILED:{error}",
            request_stage="google_translate_characterization_dom_snapshot",
        ) from error
    if response.get("ok") is not True:
        raise RequestError(
            "GOOGLE_TRANSLATE_CHARACTERIZATION_FAILED:"
            f"{response.get('error') or 'unknown error'}",
            request_stage="google_translate_characterization",
        )

    payload = {
        "result": "PASS",
        "read_only": True,
        "worker_ping": {
            "worker": ping.get("worker"),
            "characterization_version": ping.get("characterizationVersion"),
        },
        "url": response.get("url"),
        "candidate_count": response.get("candidateCount"),
        "candidates": response.get("candidates"),
        "diagnostic_count": response.get("diagnosticCount"),
        "diagnostic_candidates": response.get("diagnosticCandidates"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
