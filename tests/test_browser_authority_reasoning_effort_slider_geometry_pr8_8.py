from __future__ import annotations

from chatgpt_web_adapter.browser_authority_reasoning_effort_slider_geometry_pr8_8 import (
    ReasoningEffortSliderGeometryProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_geometry_worker_is_additive_and_strictly_zero_click_zero_write():
    root = browser_native_extension_dir()
    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    prior = 'importScripts("service_worker_reasoning_effort_slider_governance_pr8_8.js")'
    new = 'importScripts("service_worker_reasoning_effort_slider_geometry_pr8_8.js")'
    assert prior in observability and new in observability
    assert observability.index(prior) < observability.index(new)

    worker = (root / "service_worker_reasoning_effort_slider_geometry_pr8_8.js").read_text(encoding="utf-8")
    for token in (
        "thumbTrackSeparationSupported",
        "ariaDiscreteRangeSemanticsSupported",
        "siblingTickAssociationSupported",
        "advancedControlDealiasingSupported",
        "fullThreeStepMappingProven",
        "advancedLogicalControlCount",
        "uiNavigationClickForbidden",
        "selectionControlClickForbidden",
    ):
        assert token in worker
    for forbidden in (
        "Input.dispatchMouseEvent",
        "Input.insertText",
        "submitOfficialPageTurn(",
        "chrome.tabs.create(",
        "chrome.tabs.update(",
        "chrome.tabs.remove(",
        "Network.enable",
        "Network.getResponseBody",
        "document.cookie",
    ):
        assert forbidden not in worker


def test_provider_parses_discrete_aria_track_mapping_and_advanced_aliases(monkeypatch):
    provider = ReasoningEffortSliderGeometryProvider()

    def rpc(payload, *, timeout):
        if payload.get("characterizeReasoningEffortGeometrySupport") is True:
            return {
                "reasoningEffortGeometrySupported": True,
                "reasoningEffortGeometrySchemaVersion": 1,
                "thumbTrackSeparationSupported": True,
                "ariaDiscreteRangeSemanticsSupported": True,
                "siblingTickAssociationSupported": True,
                "advancedControlDealiasingSupported": True,
                "retainedExistingTabProbeSupported": True,
                "selectionControlClickForbidden": True,
                "uiNavigationClickForbidden": True,
                "zeroProductWrites": True,
                "automaticRetry": False,
                "rawTextRedactionSupported": True,
                "leaseIdExported": False,
            }
        assert payload["expectedRuntimeTabId"] == 123
        return {
            "conversationId": "c",
            "runtimeTabId": 123,
            "runtimeTabIdAfter": 123,
            "leaseIdPresent": True,
            "rawUrlExported": False,
            "rawTextExported": False,
            "rawHtmlExported": False,
            "leaseIdExported": False,
            "zeroProductWrites": True,
            "conversationWriteCount": 0,
            "chatgptMutationCount": 0,
            "automaticRetry": False,
            "topology": {
                "currentEffortControl": {"mode": "HIGH", "rect": {"x": 1, "y": 2, "width": 3, "height": 4}},
                "sliderCandidateCount": 1,
                "primarySlider": {"tag": "SPAN", "role": "slider", "rect": {"x": 90, "y": 20, "width": 28, "height": 28}, "orientation": "horizontal", "ariaValueMin": 0, "ariaValueMax": 2, "ariaValueNow": 2, "discrete": True, "stepCount": 3},
                "thumbGeometryProven": True,
                "ariaRangeSemantics": {"min": 0, "max": 2, "now": 2, "discrete": True, "stepCount": 3, "currentStepIndex": 2},
                "trackCandidateCount": 1,
                "trackCandidates": [{"tag": "DIV", "role": None, "rect": {"x": 10, "y": 30, "width": 100, "height": 4}, "relationToThumb": "PEER", "axisLengthPx": 100, "crossLengthPx": 4, "crossOffsetPx": 0, "thumbCenterInsideAxis": True}],
                "bestTrack": {"tag": "DIV", "role": None, "rect": {"x": 10, "y": 30, "width": 100, "height": 4}, "relationToThumb": "PEER", "axisLengthPx": 100, "crossLengthPx": 4, "crossOffsetPx": 0, "thumbCenterInsideAxis": True},
                "effortLabels": [{"mode": "INSTANT", "rect": {"x": 10, "y": 50, "width": 20, "height": 10}, "distanceToTrackPx": 10, "normalizedPosition": 0.0}],
                "recognizedEffortModes": ["HIGH", "INSTANT", "MEDIUM"],
                "orderedStepMapping": [{"mode": "INSTANT", "rank": 0, "ariaStepCandidate": 0, "normalizedPosition": 0.0}, {"mode": "MEDIUM", "rank": 1, "ariaStepCandidate": 1, "normalizedPosition": 0.5}, {"mode": "HIGH", "rank": 2, "ariaStepCandidate": 2, "normalizedPosition": 1.0}],
                "currentStepConsistent": True,
                "fullThreeStepMappingProven": True,
                "advancedDomCandidateCount": 2,
                "advancedLogicalControlCount": 1,
                "advancedLogicalControls": [{"index": 0, "candidateCount": 2, "actionableCandidateCount": 1, "candidates": [], "preferredTarget": {"tag": "BUTTON", "role": None, "rect": {"x": 1, "y": 1, "width": 10, "height": 10}, "actionable": True}}],
                "advancedDealiased": True,
                "selectionControlClickPerformed": False,
                "uiNavigationClickPerformed": False,
            },
        }

    monkeypatch.setattr(provider, "_characterization_rpc", rpc)
    support = provider.reasoning_effort_geometry_support()
    assert support["supported"] is True
    assert support["ui_navigation_click_forbidden"] is True
    assert support["zero_product_writes"] is True
    assert support["automatic_retry"] is False

    result = provider.reasoning_effort_geometry("c", expected_runtime_tab_id=123)
    topology = result["topology"]
    assert topology["thumb_geometry_proven"] is True
    assert topology["aria_range_semantics"]["step_count"] == 3
    assert topology["aria_range_semantics"]["current_step_index"] == 2
    assert [x["mode"] for x in topology["ordered_step_mapping"]] == ["INSTANT", "MEDIUM", "HIGH"]
    assert topology["full_three_step_mapping_proven"] is True
    assert topology["advanced_dom_candidate_count"] == 2
    assert topology["advanced_logical_control_count"] == 1
    assert topology["advanced_dealiased"] is True
    assert result["conversation_write_count"] == 0
