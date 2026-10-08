from __future__ import annotations

import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from tools.capability_capture_c2_browser import (
    capture_independent_delta,
    validate_independent_capture,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER = (
    ROOT
    / "src/chatgpt_web_adapter/browser_native_extension"
    / "service_worker_capability_capture_c2.js"
)


def _sample(*, source_count: int = 1, result_count: int = 1) -> dict:
    source = (
        "EVENT_TARGET_OBSERVED"
        if source_count == 1
        else ("MISSING" if source_count == 0 else "AMBIGUOUS")
    )
    result = (
        "ONE_STRUCTURAL_CHANGE_CANDIDATE"
        if result_count == 1
        else ("MISSING" if result_count == 0 else "AMBIGUOUS")
    )
    return {
        "ok": True,
        "type": "research_capture_independent_delta_v0_result",
        "schema": "CWA_CAPTURE_C2_INDEPENDENT_DELTA_V1",
        "productId": "google-translate-web",
        "captureMode": "EXPLICIT_SINGLE_TAB_EVENT_DELTA",
        "routeVerified": True,
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "inputEventCount": 5 if source_count else 0,
        "inputFilterCounts": {
            "observed": 5 if source_count else 0,
            "trusted": 5 if source_count else 0,
            "eligible": 5 if source_count else 0,
            "unsupportedTarget": 0,
            "invisibleTarget": 0,
        },
        "observerWindowMs": 15000,
        "source": {
            "status": source,
            "candidateCount": source_count,
            "descriptor": (
                {"role": "source_input", "kind": "textarea", "region": "left"}
                if source_count == 1
                else None
            ),
            "provenance": "TRUSTED_HUMAN_INPUT_EVENT",
        },
        "result": {
            "status": result,
            "candidateCount": result_count,
            "descriptor": (
                {"role": "changed_leaf", "kind": "span", "region": "right"}
                if result_count == 1
                else None
            ),
            "provenance": "POST_INPUT_GENERIC_DOM_MUTATIONS",
        },
        "structuralQuiet": result_count == 1,
        "referenceSelectorConsulted": False,
        "semanticFinalityProven": False,
        "learnedLocatorProven": False,
        "canonicalCompletionProven": False,
        "replayExecutable": False,
        "newWriteAuthority": False,
        "automaticRetry": False,
        "rawContentRetained": False,
    }


class FakeBridge:
    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self.response = _sample() if response is None else response
        self.error = error
        self.requests: list[tuple[dict, dict]] = []

    def _rpc(self, request: dict, **options):
        self.requests.append((request, options))
        if self.error:
            raise self.error
        return deepcopy(self.response)


def _admit(sample: dict) -> dict:
    return validate_independent_capture(
        sample, source_language="en", target_language="es"
    )


def test_explicit_capture_returns_no_authority_or_user_content() -> None:
    bridge = FakeBridge()
    report = capture_independent_delta(
        bridge,
        tab_id=1001,
        source_language="en",
        target_language="es",
        seconds=16,
        explicit_consent=True,
    )
    request, options = bridge.requests[0]
    assert len(bridge.requests) == 1
    assert request["tabId"] == 1001
    assert request["consent"] == "EXPLICIT_SINGLE_TAB_EVENT_DELTA"
    assert request["type"] == "research_capture_independent_delta_v0"
    assert request["timeoutMs"] == 22000
    assert options["timeout"] == 32.0
    assert options["delegated_response_margin"] == 10.0
    assert options["delegated_timeout_ms_key"] == "timeoutMs"
    assert report["capture_classification"] == "BOUNDED_SOURCE_AND_SINGLE_CHANGED_LEAF"
    assert report["source"]["provenance"] == "TRUSTED_HUMAN_INPUT_EVENT"
    assert report["result"]["provenance"] == "POST_INPUT_GENERIC_DOM_MUTATIONS"
    assert report["source_event_identity_proven"] is True
    assert report["input_filter_counts"] == {
        "observed": 5,
        "trusted": 5,
        "eligible": 5,
        "unsupportedTarget": 0,
        "invisibleTarget": 0,
    }
    assert report["observer_window_ms"] == 15000
    assert report["input_detection_diagnosis"] == "ELIGIBLE_TRUSTED_INPUT_OBSERVED"
    assert report["result_semantic_identity_proven"] is False
    assert report["source_selector_learned"] is False
    assert report["result_selector_learned"] is False
    assert report["reference_selector_consulted"] is False
    assert report["replay_executable"] is False
    assert report["new_write_authority"] is False
    assert report["automatic_retry"] is False
    assert report["raw_content_retained"] is False
    assert "tabId" not in report
    assert not {"text", "selector", "url", "nodeId", "dom"} & set(request)


@pytest.mark.parametrize(
    "change",
    [
        {"explicit_consent": False},
        {"tab_id": True},
        {"tab_id": 0},
        {"seconds": True},
        {"seconds": 5},
        {"seconds": 21},
        {"source_language": "en&text=secret"},
        {"target_language": "invalid code"},
    ],
)
def test_preflight_does_not_delegate_bad_request(change: dict) -> None:
    params = {
        "tab_id": 1001,
        "source_language": "en",
        "target_language": "es",
        "seconds": 16,
        "explicit_consent": True,
    }
    params.update(change)
    bridge = FakeBridge()
    with pytest.raises(ValueError, match="CAPTURE_C2_"):
        capture_independent_delta(bridge, **params)
    assert bridge.requests == []


def test_response_lost_after_delegation_never_retries() -> None:
    bridge = FakeBridge(
        error=RequestError(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION",
            request_stage="browser_native_bridge",
        )
    )
    with pytest.raises(RequestError, match="RESPONSE_LOST_AFTER_DELEGATION"):
        capture_independent_delta(
            bridge,
            tab_id=1001,
            source_language="en",
            target_language="es",
            explicit_consent=True,
        )
    assert len(bridge.requests) == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("productId", "other"),
        ("captureMode", "AUTOMATED"),
        ("routeVerified", False),
        ("sourceLanguage", "fr"),
        ("targetLanguage", "ja"),
        ("referenceSelectorConsulted", True),
        ("learnedLocatorProven", True),
        ("semanticFinalityProven", True),
        ("canonicalCompletionProven", True),
        ("replayExecutable", True),
        ("newWriteAuthority", True),
        ("automaticRetry", True),
        ("rawContentRetained", True),
        ("structuralQuiet", "true"),
        ("inputEventCount", True),
        ("inputEventCount", 65),
        ("observerWindowMs", True),
        ("observerWindowMs", 20001),
        ("inputFilterCounts", {"observed": 0}),
    ],
)
def test_spoofed_authority_or_identity_denied(key: str, value: object) -> None:
    sample = _sample()
    sample[key] = value
    with pytest.raises(ValueError, match="CAPTURE_C2_"):
        _admit(sample)


def test_privacy_refuses_extra_root_or_inner_fields() -> None:
    sample = _sample()
    sample["rawDom"] = "secret"
    with pytest.raises(ValueError, match="CAPTURE_C2_EXTRA_OR_MISSING_FIELDS"):
        _admit(sample)
    sample = _sample()
    sample["result"]["descriptor"]["textContent"] = "sensitive"
    with pytest.raises(ValueError, match="CAPTURE_C2_DESCRIPTOR_SHAPE_INVALID"):
        _admit(sample)
    sample = _sample()
    sample["source"]["nodeId"] = 100
    with pytest.raises(ValueError, match="CAPTURE_C2_SLOT_SHAPE_INVALID"):
        _admit(sample)


@pytest.mark.parametrize(
    "source_count,result_count,quiet",
    [
        (0, 1, True),
        (0, 1, False),
        (0, 0, True),
        (1, 0, True),
        (2, 1, True),
    ],
)
def test_event_and_status_constraints(source_count, result_count, quiet) -> None:
    sample = _sample(source_count=source_count, result_count=result_count)
    sample["structuralQuiet"] = quiet
    if source_count == 2:
        sample["source"]["status"] = "AMBIGUOUS"
    if result_count == 1 and not quiet:
        sample["result"]["status"] = "AMBIGUOUS"
        sample["result"]["descriptor"] = None
    if source_count == 2 and quiet and result_count == 1:
        # Ambiguous source may have a structural change, still cannot replay.
        report = _admit(sample)
        assert report["result_semantic_identity_proven"] is False
        assert report["replay_executable"] is False
    else:
        with pytest.raises(ValueError, match="CAPTURE_C2_"):
            _admit(sample)


def test_missing_input_and_missing_result_are_admitted_as_incomplete() -> None:
    sample = _sample(source_count=0, result_count=0)
    sample["structuralQuiet"] = False
    report = _admit(sample)
    assert report["capture_classification"] == (
        "INCOMPLETE_OR_AMBIGUOUS_STRUCTURAL_DEMONSTRATION"
    )
    assert report["result_selector_learned"] is False


def test_multiple_changed_nodes_never_assumed_to_be_result() -> None:
    sample = _sample(result_count=2)
    sample["structuralQuiet"] = False
    report = _admit(sample)
    assert report["result"]["status"] == "AMBIGUOUS"
    assert report["result"]["descriptor"] is None
    assert report["new_write_authority"] is False


def test_result_descriptor_count_spoofing_fails_closed() -> None:
    sample = _sample(result_count=2)
    sample["result"]["descriptor"] = {
        "role": "changed_leaf",
        "kind": "span",
        "region": "right",
    }
    with pytest.raises(ValueError, match="CAPTURE_C2_DESCRIPTOR_PROVENANCE_INVALID"):
        _admit(sample)


def test_worker_reference_independence_and_synthetic_cdp() -> None:
    code = WORKER.read_text(encoding="utf-8")
    # CDP transport legitimately reads response.result.value; verify the
    # serialized page probe, not unrelated native-transport plumbing.
    page_probe = code.split("function _cwaC2PageProbe(", 1)[1].split(
        "function _cwaC2Expression(", 1
    )[0]
    for forbidden in (
        "querySelectorAll",
        "W297wb",
        "jqKxS",
        "jsname",
        ".textContent",
        ".innerText",
        ".outerHTML",
        ".value",
        "chrome.tabs.update",
        "chrome.tabs.create",
    ):
        assert forbidden not in page_probe
    subprocess.run(
        ["node", "--check", str(WORKER)],
        check=True,
        capture_output=True,
        text=True,
    )
    run = subprocess.run(
        ["node", str(ROOT / "tools/capability_capture_c2_dom_fixture.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr


def test_host_lane_and_domain_dispatch_are_explicit() -> None:
    host = (ROOT / "src/chatgpt_web_adapter/browser_native_host.py").read_text(
        encoding="utf-8"
    )
    outer = (
        ROOT
        / "src/chatgpt_web_adapter/browser_native_extension"
        / "service_worker_google_translate_capability.js"
    ).read_text(encoding="utf-8")
    assert host.count('"research_capture_independent_delta_v0"') >= 2
    assert 'importScripts("service_worker_capability_capture_c2.js")' in outer
    assert "message?.type === CWA_C2_OPERATION" in outer
    assert "_cwaOnNativeMessageWithIndependentDelta(message, port, next)" in outer


def test_c2_missing_source_with_full_window_proves_only_no_accepted_events() -> None:
    sample = _sample(source_count=0, result_count=0)
    report = _admit(sample)
    assert (
        report["input_detection_diagnosis"] == "NO_INPUT_EVENT_OBSERVED_DURING_WINDOW"
    )
    assert report["input_filter_counts"]["observed"] == 0
    assert report["observer_window_ms"] == 15000
    assert report["source_event_identity_proven"] is False
    assert report["result_selector_learned"] is False


@pytest.mark.parametrize(
    "diagnostics,expected",
    [
        (
            {
                "observed": 3,
                "trusted": 0,
                "eligible": 0,
                "unsupportedTarget": 0,
                "invisibleTarget": 0,
            },
            "ONLY_UNTRUSTED_INPUT_EVENTS",
        ),
        (
            {
                "observed": 5,
                "trusted": 5,
                "eligible": 0,
                "unsupportedTarget": 5,
                "invisibleTarget": 0,
            },
            "FILTERED_UNSUPPORTED_TARGETS",
        ),
        (
            {
                "observed": 2,
                "trusted": 2,
                "eligible": 0,
                "unsupportedTarget": 0,
                "invisibleTarget": 2,
            },
            "FILTERED_INVISIBLE_TARGETS",
        ),
        (
            {
                "observed": 2,
                "trusted": 2,
                "eligible": 0,
                "unsupportedTarget": 1,
                "invisibleTarget": 1,
            },
            "FILTERED_UNSUPPORTED_AND_INVISIBLE_TARGETS",
        ),
    ],
)
def test_filtered_event_counts_distinguish_missing_source_reasons(
    diagnostics: dict,
    expected: str,
) -> None:
    sample = _sample(source_count=0, result_count=0)
    sample["inputFilterCounts"] = diagnostics
    report = _admit(sample)
    assert report["input_event_count"] == 0
    assert report["input_detection_diagnosis"] == expected
    assert report["source"]["status"] == "MISSING"
    assert report["new_write_authority"] is False


@pytest.mark.parametrize(
    "diagnostics",
    [
        {
            "observed": 2,
            "trusted": 3,
            "eligible": 0,
            "unsupportedTarget": 3,
            "invisibleTarget": 0,
        },
        {
            "observed": 1,
            "trusted": 1,
            "eligible": 0,
            "unsupportedTarget": 0,
            "invisibleTarget": 0,
        },
        {
            "observed": 5,
            "trusted": 5,
            "eligible": 1,
            "unsupportedTarget": 2,
            "invisibleTarget": 1,
        },
        {
            "observed": True,
            "trusted": 0,
            "eligible": 0,
            "unsupportedTarget": 0,
            "invisibleTarget": 0,
        },
        {
            "observed": 0,
            "trusted": 0,
            "eligible": 0,
            "unsupportedTarget": 0,
            "invisibleTarget": 0,
            "text": "private hello",
        },
    ],
)
def test_fake_or_leaky_c2_input_filter_evidence_rejected(diagnostics: dict) -> None:
    sample = _sample(source_count=0, result_count=0)
    sample["inputFilterCounts"] = diagnostics
    with pytest.raises(ValueError, match="CAPTURE_C2_INPUT_FILTER"):
        _admit(sample)


def test_eligible_event_filter_count_must_match_admitted_event_count() -> None:
    sample = _sample()
    sample["inputFilterCounts"]["eligible"] = 4
    with pytest.raises(ValueError, match="CAPTURE_C2_INPUT_FILTER_INCONSISTENT"):
        _admit(sample)
