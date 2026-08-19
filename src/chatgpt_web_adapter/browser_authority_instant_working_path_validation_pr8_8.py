from __future__ import annotations

from typing import Any

from .browser_authority_instant_effort_selection_pr8_8 import SCHEMA

UNIFIED_GPT56_ROUTE_STATUS = "UNIFIED_GPT_5_6_ROUTE_WITHOUT_EXPLICIT_REASONING"


def _evidence(instant: dict[str, Any], name: str) -> dict[str, Any]:
    value = instant.get(name)
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_gpt56_identifier(value: str) -> bool:
    text = value.strip().lower()
    return text == "gpt-5-6" or text.startswith(
        ("gpt-5-6-", "gpt-5-6_", "gpt-5-6.", "gpt-5-6:", "gpt-5-6/")
    )


def _unified_gpt56_route_contract(instant: dict[str, Any]) -> bool:
    evidence = (
        _evidence(instant, "request_evidence"),
        _evidence(instant, "response_evidence"),
    )
    identifiers = [
        identifier
        for item in evidence
        for identifier in _strings(item.get("model_identifiers"))
    ]
    explicit_reasoning_metadata = any(
        _strings(item.get("reasoning_hint_keys"))
        or _strings(item.get("reasoning_states"))
        for item in evidence
    )
    return (
        any(_is_gpt56_identifier(identifier) for identifier in identifiers)
        and not explicit_reasoning_metadata
    )


def validate_support(support: dict[str, Any]) -> None:
    required_true = (
        "supported", "production_instant_working_path_supported", "quick_picker_only",
        "exact_discrete_range_required", "semantic_home_key_selection_supported",
        "selected_instant_proof_required", "pre_input_failure_boundary_preserved",
        "advanced_picker_click_forbidden", "model_control_click_forbidden",
    )
    if support.get("schema") != SCHEMA or any(support.get(key) is not True for key in required_true):
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_EXTENSION_RELOAD_REQUIRED")
    if support.get("automatic_retry") is not False:
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_AUTOMATIC_RETRY_CHANGED")


def validate_selection(selection: dict[str, Any]) -> None:
    if selection.get("schema") != SCHEMA:
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_SELECTION_SCHEMA_MISMATCH")
    if selection.get("selection_complete") is not True:
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_SELECTION_NOT_COMPLETE")
    if selection.get("selected_mode_after_selection_proven") is not True or selection.get("selected_mode_after_selection") != "INSTANT":
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_INSTANT_NOT_PROVEN")
    if selection.get("unexpected_conversation_write_before_selection_complete") is True or selection.get("conversation_write_count_during_selection") != 0:
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_PREINPUT_WRITE_BOUNDARY_VIOLATED")
    if selection.get("advanced_control_clicked") is True or selection.get("model_control_clicked") is True:
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_FORBIDDEN_CONTROL_CLICKED")
    if selection.get("selection_performed") is True:
        if selection.get("selection_mechanism") != "REASONING_EFFORT_SLIDER_HOME":
            raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_WRONG_SELECTION_MECHANISM")
        if (
            selection.get("effort_slider_candidate_count") != 1
            or selection.get("effort_slider_aria_value_min") != 0
            or selection.get("effort_slider_aria_value_max") != 2
            or selection.get("effort_slider_step_count") != 3
            or selection.get("effort_slider_focus_proven") is not True
            or selection.get("effort_slider_home_dispatched") is not True
        ):
            raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_SLIDER_CONTRACT_NOT_PROVEN")
        if selection.get("effort_slider_observed_after_home") is True and selection.get("effort_slider_min_reached_proven") is not True:
            raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_SLIDER_MIN_NOT_PROVEN")
    elif selection.get("selection_mechanism") != "NO_SELECTION_REQUIRED":
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_SELECTION_MECHANISM_MISSING")


def validate_instant_route(instant: dict[str, Any]) -> None:
    if (
        instant.get("requested_model_mode") != "INSTANT"
        or instant.get("require_no_reasoning_route") is not True
        or instant.get("selected_mode_before_write_proven") is not True
        or instant.get("selected_mode_before_write") != "INSTANT"
        or instant.get("conversation_request_observed") is not True
        or instant.get("reasoning_route_observed") is True
    ):
        raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_ROUTE_CONTRACT_FAILED")

    if (
        instant.get("network_route_status") == UNIFIED_GPT56_ROUTE_STATUS
        and not _unified_gpt56_route_contract(instant)
    ):
        raise RuntimeError(
            "PR8_8_INSTANT_WORKING_PATH_UNIFIED_GPT56_ROUTE_CONTRACT_FAILED"
        )
