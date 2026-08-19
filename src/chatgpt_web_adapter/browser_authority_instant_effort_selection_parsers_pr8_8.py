from __future__ import annotations

from typing import Any

from .browser_authority_instant_latency_pr8_8 import _int, _string


def parse_support(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "supported": response.get("instantEffortSelectionSupported") is True,
        "schema": _int(response.get("instantEffortSelectionSchemaVersion")),
        "production_instant_working_path_supported": response.get("productionInstantWorkingPathSupported") is True,
        "quick_picker_only": response.get("quickPickerOnly") is True,
        "exact_discrete_range_required": response.get("exactDiscreteRangeRequired") is True,
        "semantic_home_key_selection_supported": response.get("semanticHomeKeySelectionSupported") is True,
        "selected_instant_proof_required": response.get("selectedInstantProofRequired") is True,
        "pre_input_failure_boundary_preserved": response.get("preInputFailureBoundaryPreserved") is True,
        "advanced_picker_click_forbidden": response.get("advancedPickerClickForbidden") is True,
        "model_control_click_forbidden": response.get("modelControlClickForbidden") is True,
        "automatic_retry": response.get("automaticRetry") is True,
    }


def parse_selection_record(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": _int(response.get("instantEffortSelectionSchemaVersion")),
        "selection_mechanism": _string(response.get("selectionMechanism")),
        "selection_performed": response.get("selectionPerformed") is True,
        "selection_complete": response.get("selectionComplete") is True,
        "selected_mode_before_selection": _string(response.get("selectedModeBeforeSelection")),
        "selected_mode_after_selection": _string(response.get("selectedModeAfterSelection")),
        "selected_mode_after_selection_proven": response.get("selectedModeAfterSelectionProven") is True,
        "instant_effort_picker_click_performed": response.get("instantEffortPickerClickPerformed") is True,
        "effort_slider_candidate_count": _int(response.get("effortSliderCandidateCount")),
        "effort_slider_aria_value_min": response.get("effortSliderAriaValueMin"),
        "effort_slider_aria_value_max": response.get("effortSliderAriaValueMax"),
        "effort_slider_aria_value_now_before": response.get("effortSliderAriaValueNowBefore"),
        "effort_slider_aria_value_now_after": response.get("effortSliderAriaValueNowAfter"),
        "effort_slider_step_count": _int(response.get("effortSliderStepCount")),
        "effort_slider_focus_proven": response.get("effortSliderFocusProven") is True,
        "effort_slider_home_dispatched": response.get("effortSliderHomeDispatched") is True,
        "effort_slider_min_reached_proven": response.get("effortSliderMinReachedProven") is True,
        "effort_slider_observed_after_home": response.get("effortSliderObservedAfterHome") is True,
        "advanced_control_clicked": response.get("advancedControlClicked") is True,
        "model_control_clicked": response.get("modelControlClicked") is True,
        "unexpected_conversation_write_before_selection_complete": response.get("unexpectedConversationWriteBeforeSelectionComplete") is True,
        "conversation_write_count_during_selection": _int(response.get("conversationWriteCountDuringSelection")) or 0,
        "model_selection_materialization_status": _string(response.get("modelSelectionMaterializationStatus")),
    }
