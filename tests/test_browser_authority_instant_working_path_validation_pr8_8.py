from chatgpt_web_adapter.browser_authority_instant_working_path_validation_pr8_8 import (
    validate_instant_route, validate_selection, validate_support,
)


def test_shipping_validators_accept_proven_path():
    validate_support({
        "supported": True, "schema": 1, "production_instant_working_path_supported": True,
        "quick_picker_only": True, "exact_discrete_range_required": True,
        "semantic_home_key_selection_supported": True, "selected_instant_proof_required": True,
        "pre_input_failure_boundary_preserved": True, "advanced_picker_click_forbidden": True,
        "model_control_click_forbidden": True, "automatic_retry": False,
    })
    validate_selection({
        "schema": 1, "selection_complete": True, "selected_mode_after_selection_proven": True,
        "selected_mode_after_selection": "INSTANT",
        "unexpected_conversation_write_before_selection_complete": False,
        "conversation_write_count_during_selection": 0, "advanced_control_clicked": False,
        "model_control_clicked": False, "selection_performed": True,
        "selection_mechanism": "REASONING_EFFORT_SLIDER_HOME", "effort_slider_candidate_count": 1,
        "effort_slider_aria_value_min": 0, "effort_slider_aria_value_max": 2,
        "effort_slider_step_count": 3, "effort_slider_focus_proven": True,
        "effort_slider_home_dispatched": True, "effort_slider_observed_after_home": True,
        "effort_slider_min_reached_proven": True,
    })
    validate_instant_route({
        "requested_model_mode": "INSTANT", "require_no_reasoning_route": True,
        "selected_mode_before_write_proven": True, "selected_mode_before_write": "INSTANT",
        "conversation_request_observed": True, "reasoning_route_observed": False,
    })
