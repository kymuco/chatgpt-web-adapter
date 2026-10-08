"""Opt-in, research-only, structural Google Translate browser demonstration capture.

This uses the existing installed CWA native host *from this research checkout*.
It never calls the product translation operation and never saves page text,
network responses, credentials, or arbitrary DOM. The human performs the input.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from typing import Any

from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider

_OPERATION = "research_capture_translate_demo_v0"
_RESPONSE_TYPE = "research_capture_translate_demo_v0_result"
_LANG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,19}$")
_PHASES = (
    "source_ready",
    "source_input_event",
    "result_candidate_seen",
    "result_candidate_presence_stable",
)
_RESULT_KEYS = frozenset(
    {
        "schema",
        "productId",
        "captureMode",
        "observedTabId",
        "sourceLanguage",
        "targetLanguage",
        "events",
        "inputEventCount",
        "routeVerified",
        "candidatePresenceStable",
        "candidateIdentityResolved",
        "canonicalCompletionProven",
        "semanticFinalityProven",
        "effectBoundary",
        "automaticRetry",
        "replayExecutable",
        "rawContentRetained",
    }
)


def _language(value: str) -> str:
    if not isinstance(value, str) or not _LANG_RE.fullmatch(value):
        raise ValueError("CAPTURE_V0_LANGUAGE_CODE_INVALID")
    return value


def validate_capture_trace(
    response: dict[str, Any],
    *,
    tab_id: int,
    source_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Accept an exact schema only; never echo arbitrary browser data."""
    if response.get("ok") is not True:
        raise ValueError("CAPTURE_V0_OBSERVATION_FAILED")
    if response.get("type") != _RESPONSE_TYPE:
        raise ValueError("CAPTURE_V0_RESPONSE_TYPE_INVALID")
    payload = {key: value for key, value in response.items() if key in _RESULT_KEYS}
    if set(payload) != _RESULT_KEYS:
        raise ValueError("CAPTURE_V0_MISSING_EVIDENCE")
    if (
        payload["schema"] != "CWA_CAPTURE_V0_STRUCTURAL_TRACE"
        or payload["productId"] != "google-translate-web"
        or payload["captureMode"] != "EXPLICIT_OBSERVE_ONLY"
        or type(payload["observedTabId"]) is not int
        or payload["observedTabId"] != tab_id
        or payload["sourceLanguage"] != source_language
        or payload["targetLanguage"] != target_language
        or payload["routeVerified"] is not True
        or payload["canonicalCompletionProven"] is not False
        or payload["semanticFinalityProven"] is not False
        or payload["effectBoundary"] != "MANUAL_REFERENCE_ONLY_SOURCE_INPUT"
        or payload["automaticRetry"] is not False
        or payload["replayExecutable"] is not False
        or payload["rawContentRetained"] is not False
    ):
        raise ValueError("CAPTURE_V0_SAFETY_OR_IDENTITY_MISMATCH")
    for name in ("candidatePresenceStable", "candidateIdentityResolved"):
        if type(payload[name]) is not bool:
            raise ValueError("CAPTURE_V0_BAD_BOOLEAN")
    count = payload["inputEventCount"]
    if type(count) is not int or count < 0 or count > 64:
        raise ValueError("CAPTURE_V0_BAD_INPUT_COUNT")
    events = payload["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 4:
        raise ValueError("CAPTURE_V0_BAD_EVENTS")
    seen = []
    last_ms = -1
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("CAPTURE_V0_BAD_EVENT")
        phase = event.get("phase")
        if phase not in _PHASES or phase in seen:
            raise ValueError("CAPTURE_V0_BAD_PHASE")
        keys = (
            {"phase", "t_ms", "role"}
            if phase == "source_ready"
            else {
                "phase",
                "t_ms",
            }
        )
        if set(event) != keys or (
            phase == "source_ready" and event["role"] != "textbox"
        ):
            raise ValueError("CAPTURE_V0_UNBOUNDED_EVENT")
        t_ms = event["t_ms"]
        if type(t_ms) is not int or t_ms < last_ms or t_ms < 0 or t_ms > 25000:
            raise ValueError("CAPTURE_V0_BAD_EVENT_TIME")
        last_ms = t_ms
        seen.append(phase)
    if seen != list(_PHASES[: len(seen)]):
        raise ValueError("CAPTURE_V0_PHASE_ORDER_INVALID")
    if (count > 0) != ("source_input_event" in seen):
        raise ValueError("CAPTURE_V0_INPUT_EVIDENCE_MISMATCH")
    has_stable = "result_candidate_presence_stable" in seen
    if payload["candidatePresenceStable"] != has_stable:
        raise ValueError("CAPTURE_V0_STABILITY_EVIDENCE_MISMATCH")
    if payload["candidateIdentityResolved"] != has_stable:
        raise ValueError("CAPTURE_V0_IDENTITY_EVIDENCE_MISMATCH")
    # This is a structural presence observation, not proof of translated content.
    return payload


def capture_demo(
    bridge: BrowserNativeTurnProvider,
    *,
    tab_id: int,
    source_language: str,
    target_language: str,
    seconds: int = 12,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    if explicit_consent is not True:
        raise ValueError("CAPTURE_V0_EXPLICIT_CONSENT_REQUIRED")
    if type(tab_id) is not int or tab_id <= 0:
        raise ValueError("CAPTURE_V0_TAB_ID_INVALID")
    if type(seconds) is not int or not 3 <= seconds <= 20:
        raise ValueError("CAPTURE_V0_CAPTURE_SECONDS_INVALID")
    source = _language(source_language)
    target = _language(target_language)
    payload = {
        "type": _OPERATION,
        "request_id": uuid.uuid4().hex,
        "consent": "EXPLICIT_OBSERVE_ONLY",
        "tabId": tab_id,
        "captureSeconds": seconds,
        "sourceLanguage": source,
        "targetLanguage": target,
        "timeoutMs": (seconds + 4) * 1000,
    }
    response = bridge._rpc(  # noqa: SLF001
        payload,
        timeout=seconds + 7.0,
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=2.0,
    )
    return validate_capture_trace(
        response, tab_id=tab_id, source_language=source, target_language=target
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research-only opt-in structural observation (no product write)"
    )
    parser.add_argument("--tab-id", required=True, type=int)
    parser.add_argument("--source-language", required=True)
    parser.add_argument("--target-language", required=True)
    parser.add_argument("--seconds", type=int, default=12)
    parser.add_argument(
        "--i-consent-to-structural-capture", action="store_true", default=False
    )
    args = parser.parse_args()
    result = capture_demo(
        BrowserNativeTurnProvider(),
        tab_id=args.tab_id,
        source_language=args.source_language,
        target_language=args.target_language,
        seconds=args.seconds,
        explicit_consent=args.i_consent_to_structural_capture,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
