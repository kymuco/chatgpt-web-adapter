from chatgpt_web_adapter.browser_authority_instant_effort_selection_pr8_8 import (
    SCHEMA,
    InstantEffortSelectionProvider,
)


def test_support_parser(monkeypatch):
    provider = object.__new__(InstantEffortSelectionProvider)
    monkeypatch.setattr(provider, "_characterization_rpc", lambda payload, timeout: {
        "instantEffortSelectionSupported": True,
        "instantEffortSelectionSchemaVersion": 1,
        "productionInstantWorkingPathSupported": True,
        "quickPickerOnly": True,
        "exactDiscreteRangeRequired": True,
        "semanticHomeKeySelectionSupported": True,
        "selectedInstantProofRequired": True,
        "preInputFailureBoundaryPreserved": True,
        "advancedPickerClickForbidden": True,
        "modelControlClickForbidden": True,
        "automaticRetry": False,
    })
    record = provider.instant_effort_selection_support()
    assert record["supported"] is True and record["schema"] == SCHEMA
    assert record["semantic_home_key_selection_supported"] is True
    assert record["automatic_retry"] is False


def test_selection_record_parser(monkeypatch):
    provider = object.__new__(InstantEffortSelectionProvider)
    monkeypatch.setattr(provider, "_characterization_rpc", lambda payload, timeout: {
        "instantEffortSelectionSchemaVersion": 1,
        "selectionMechanism": "REASONING_EFFORT_SLIDER_HOME",
        "selectionPerformed": True,
        "selectionComplete": True,
        "selectedModeBeforeSelection": "HIGH",
        "selectedModeAfterSelection": "INSTANT",
        "selectedModeAfterSelectionProven": True,
        "instantEffortPickerClickPerformed": True,
        "effortSliderCandidateCount": 1,
        "effortSliderAriaValueMin": 0,
        "effortSliderAriaValueMax": 2,
        "effortSliderAriaValueNowBefore": 2,
        "effortSliderAriaValueNowAfter": 0,
        "effortSliderStepCount": 3,
        "effortSliderFocusProven": True,
        "effortSliderHomeDispatched": True,
        "effortSliderMinReachedProven": True,
        "effortSliderObservedAfterHome": True,
        "advancedControlClicked": False,
        "modelControlClicked": False,
        "unexpectedConversationWriteBeforeSelectionComplete": False,
        "conversationWriteCountDuringSelection": 0,
    })
    record = provider.instant_effort_selection_for_lease("lease-1")
    assert record["selection_mechanism"] == "REASONING_EFFORT_SLIDER_HOME"
    assert record["selected_mode_after_selection"] == "INSTANT"
    assert record["effort_slider_aria_value_min"] == 0
    assert record["effort_slider_aria_value_max"] == 2
    assert record["effort_slider_aria_value_now_after"] == 0
    assert record["conversation_write_count_during_selection"] == 0
