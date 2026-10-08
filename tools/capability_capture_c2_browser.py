"""C2: bounded, read-only, reference-independent single-tab demonstration.

This tool accepts an explicitly consented human input demonstration. No
source/result text, hashes, selectors, DOM snapshots or node IDs are exported.
Presence of one changed node does not establish result semantics or replay.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from typing import Any

from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider

_OPERATION = "research_capture_independent_delta_v0"
_RESULT_TYPE = "research_capture_independent_delta_v0_result"
_LANGUAGE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,19}$")
_REPORT_KEYS = frozenset(
    {
        "schema",
        "productId",
        "captureMode",
        "routeVerified",
        "sourceLanguage",
        "targetLanguage",
        "inputEventCount",
        "inputFilterCounts",
        "observerWindowMs",
        "source",
        "result",
        "structuralQuiet",
        "referenceSelectorConsulted",
        "semanticFinalityProven",
        "learnedLocatorProven",
        "canonicalCompletionProven",
        "replayExecutable",
        "newWriteAuthority",
        "automaticRetry",
        "rawContentRetained",
    }
)
_STATUS_SOURCE = {"MISSING", "EVENT_TARGET_OBSERVED", "AMBIGUOUS"}
_STATUS_RESULT = {"MISSING", "ONE_STRUCTURAL_CHANGE_CANDIDATE", "AMBIGUOUS"}
_KINDS_SOURCE = {"textarea", "input", "contenteditable"}
_KINDS_RESULT = {"span", "div", "p", "section", "output", "other"}
_REGIONS = {"left", "center", "right", "unknown"}


def _language(code: str) -> str:
    if not isinstance(code, str) or _LANGUAGE.fullmatch(code) is None:
        raise ValueError("CAPTURE_C2_LANGUAGE_INVALID")
    return code


def _descriptor(value: Any, *, role: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"role", "kind", "region"}:
        raise ValueError("CAPTURE_C2_DESCRIPTOR_SHAPE_INVALID")
    kinds = _KINDS_SOURCE if role == "source_input" else _KINDS_RESULT
    if (
        value["role"] != role
        or type(value["kind"]) is not str
        or value["kind"] not in kinds
        or type(value["region"]) is not str
        or value["region"] not in _REGIONS
    ):
        raise ValueError("CAPTURE_C2_DESCRIPTOR_VALUE_INVALID")
    return {key: value[key] for key in ("role", "kind", "region")}


def _slot(value: Any, *, source: bool, quiet: bool) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "status",
        "candidateCount",
        "descriptor",
        "provenance",
    }:
        raise ValueError("CAPTURE_C2_SLOT_SHAPE_INVALID")
    status = value["status"]
    count = value["candidateCount"]
    provenance = (
        "TRUSTED_HUMAN_INPUT_EVENT" if source else "POST_INPUT_GENERIC_DOM_MUTATIONS"
    )
    if (
        type(status) is not str
        or status not in (_STATUS_SOURCE if source else _STATUS_RESULT)
        or type(count) is not int
        or count < 0
        or count > (2 if source else 8)
        or value["provenance"] != provenance
    ):
        raise ValueError("CAPTURE_C2_SLOT_IDENTITY_INVALID")
    if count == 0:
        expected = "MISSING"
    elif source:
        expected = "EVENT_TARGET_OBSERVED" if count == 1 else "AMBIGUOUS"
    elif count == 1 and quiet:
        expected = "ONE_STRUCTURAL_CHANGE_CANDIDATE"
    else:
        expected = "AMBIGUOUS"
    if status != expected:
        raise ValueError("CAPTURE_C2_STATUS_COUNT_MISMATCH")
    descriptor = _descriptor(
        value["descriptor"],
        role="source_input" if source else "changed_leaf",
    )
    single_status = (
        "EVENT_TARGET_OBSERVED" if source else "ONE_STRUCTURAL_CHANGE_CANDIDATE"
    )
    if (descriptor is not None) != (status == single_status):
        raise ValueError("CAPTURE_C2_DESCRIPTOR_PROVENANCE_INVALID")
    return {
        "status": status,
        "candidateCount": count,
        "descriptor": descriptor,
        "provenance": value["provenance"],
    }


_INPUT_FILTER_KEYS = frozenset(
    {"observed", "trusted", "eligible", "unsupportedTarget", "invisibleTarget"}
)


def _input_filter_counts(value: Any, *, accepted: int) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != _INPUT_FILTER_KEYS:
        raise ValueError("CAPTURE_C2_INPUT_FILTER_SHAPE_INVALID")
    if any(
        type(value[k]) is not int or not 0 <= value[k] <= 64 for k in _INPUT_FILTER_KEYS
    ):
        raise ValueError("CAPTURE_C2_INPUT_FILTER_BOUNDS_INVALID")
    if (
        value["eligible"] != accepted
        or value["observed"] < value["trusted"]
        or value["trusted"]
        != (value["eligible"] + value["unsupportedTarget"] + value["invisibleTarget"])
    ):
        raise ValueError("CAPTURE_C2_INPUT_FILTER_INCONSISTENT")
    return {
        key: value[key]
        for key in (
            "observed",
            "trusted",
            "eligible",
            "unsupportedTarget",
            "invisibleTarget",
        )
    }


def _input_diagnosis(counts: dict[str, int]) -> str:
    if counts["observed"] == 0:
        return "NO_INPUT_EVENT_OBSERVED_DURING_WINDOW"
    if counts["trusted"] == 0:
        return "ONLY_UNTRUSTED_INPUT_EVENTS"
    if counts["eligible"] > 0:
        return "ELIGIBLE_TRUSTED_INPUT_OBSERVED"
    if counts["unsupportedTarget"] > 0 and counts["invisibleTarget"] > 0:
        return "FILTERED_UNSUPPORTED_AND_INVISIBLE_TARGETS"
    if counts["unsupportedTarget"] > 0:
        return "FILTERED_UNSUPPORTED_TARGETS"
    return "FILTERED_INVISIBLE_TARGETS"


def validate_independent_capture(
    response: dict[str, Any],
    *,
    source_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Deny unexpected browser output, spoofed authority and content fields."""
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise ValueError("CAPTURE_C2_OBSERVATION_FAILED")
    if response.get("type") != _RESULT_TYPE:
        raise ValueError("CAPTURE_C2_RESULT_TYPE_INVALID")
    raw = {
        k: v
        for k, v in response.items()
        if k not in {"ok", "type", "protocol", "request_id"}
    }
    if set(raw) != _REPORT_KEYS:
        raise ValueError("CAPTURE_C2_EXTRA_OR_MISSING_FIELDS")
    if (
        raw["schema"] != "CWA_CAPTURE_C2_INDEPENDENT_DELTA_V1"
        or raw["productId"] != "google-translate-web"
        or raw["captureMode"] != "EXPLICIT_SINGLE_TAB_EVENT_DELTA"
        or raw["routeVerified"] is not True
        or raw["sourceLanguage"] != _language(source_language)
        or raw["targetLanguage"] != _language(target_language)
        or raw["referenceSelectorConsulted"] is not False
        or raw["semanticFinalityProven"] is not False
        or raw["learnedLocatorProven"] is not False
        or raw["canonicalCompletionProven"] is not False
        or raw["replayExecutable"] is not False
        or raw["newWriteAuthority"] is not False
        or raw["automaticRetry"] is not False
        or raw["rawContentRetained"] is not False
        or type(raw["structuralQuiet"]) is not bool
        or type(raw["inputEventCount"]) is not int
        or not 0 <= raw["inputEventCount"] <= 64
        or type(raw["observerWindowMs"]) is not int
        or not 0 <= raw["observerWindowMs"] <= 20000
    ):
        raise ValueError("CAPTURE_C2_AUTHORITY_OR_ROUTE_MISMATCH")
    filters = _input_filter_counts(
        raw["inputFilterCounts"], accepted=raw["inputEventCount"]
    )
    source = _slot(raw["source"], source=True, quiet=raw["structuralQuiet"])
    result = _slot(raw["result"], source=False, quiet=raw["structuralQuiet"])
    if (
        (raw["inputEventCount"] == 0 and source["candidateCount"] != 0)
        or (raw["inputEventCount"] > 0 and source["candidateCount"] == 0)
        or (source["candidateCount"] == 0 and result["candidateCount"] != 0)
        or (raw["structuralQuiet"] and result["candidateCount"] == 0)
    ):
        raise ValueError("CAPTURE_C2_EVENT_CAUSAL_ORDER_INVALID")
    return {
        "schema": raw["schema"],
        "capture_classification": (
            "BOUNDED_SOURCE_AND_SINGLE_CHANGED_LEAF"
            if source["status"] == "EVENT_TARGET_OBSERVED"
            and result["status"] == "ONE_STRUCTURAL_CHANGE_CANDIDATE"
            else "INCOMPLETE_OR_AMBIGUOUS_STRUCTURAL_DEMONSTRATION"
        ),
        "source": source,
        "result": result,
        "input_event_count": raw["inputEventCount"],
        "input_filter_counts": filters,
        "input_detection_diagnosis": _input_diagnosis(filters),
        "observer_window_ms": raw["observerWindowMs"],
        "structural_quiet": raw["structuralQuiet"],
        "source_event_identity_proven": source["status"] == "EVENT_TARGET_OBSERVED",
        "result_semantic_identity_proven": False,
        "source_selector_learned": False,
        "result_selector_learned": False,
        "reference_selector_consulted": False,
        "semantic_finality_proven": False,
        "replay_executable": False,
        "new_write_authority": False,
        "automatic_retry": False,
        "raw_content_retained": False,
        "decision": "C2_OBSERVATION_ONLY_NO_LOCATOR_PROMOTION",
    }


def capture_independent_delta(
    bridge: BrowserNativeTurnProvider,
    *,
    tab_id: int,
    source_language: str,
    target_language: str,
    seconds: int = 16,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    if explicit_consent is not True:
        raise ValueError("CAPTURE_C2_CONSENT_REQUIRED")
    if type(tab_id) is not int or tab_id <= 0:
        raise ValueError("CAPTURE_C2_TAB_ID_INVALID")
    if type(seconds) is not int or not 6 <= seconds <= 20:
        raise ValueError("CAPTURE_C2_DURATION_INVALID")
    source = _language(source_language)
    target = _language(target_language)
    # Broker may wait delegated deadline + 5 s. Reserve 10 s so its explicit
    # outcome reaches this caller before the local socket expires.
    timeout = seconds + 16.0
    response = bridge._rpc(  # noqa: SLF001
        {
            "type": _OPERATION,
            "request_id": uuid.uuid4().hex,
            "tabId": tab_id,
            "sourceLanguage": source,
            "targetLanguage": target,
            "seconds": seconds,
            "consent": "EXPLICIT_SINGLE_TAB_EVENT_DELTA",
            "timeoutMs": (seconds + 6) * 1000,
        },
        timeout=timeout,
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=10.0,
    )
    return validate_independent_capture(
        response,
        source_language=source,
        target_language=target,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="C2: reference-independent input/delta capture, read-only"
    )
    parser.add_argument("--tab-id", type=int, required=True)
    parser.add_argument("--source-language", required=True)
    parser.add_argument("--target-language", required=True)
    parser.add_argument("--seconds", type=int, default=16)
    parser.add_argument("--i-consent-to-independent-capture", action="store_true")
    args = parser.parse_args()
    result = capture_independent_delta(
        BrowserNativeTurnProvider(),
        tab_id=args.tab_id,
        source_language=args.source_language,
        target_language=args.target_language,
        seconds=args.seconds,
        explicit_consent=args.i_consent_to_independent_capture,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
