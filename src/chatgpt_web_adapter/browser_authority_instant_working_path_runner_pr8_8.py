from __future__ import annotations

from typing import Any

from .browser_authority_instant_effort_selection_pr8_8 import InstantEffortSelectionProvider
from .browser_authority_instant_working_path_validation_pr8_8 import (
    validate_instant_route, validate_selection, validate_support,
)
from .browser_authority_policy_replication_pr8_8 import _observation_record

PROMPT = "Reply with exactly: SDK_PR8_8_INSTANT_WORKING_PATH_OK"


def _failure(error: BaseException) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": type(error).__name__,
        "message": str(error),
        "automatic_retry_attempted": False,
    }
    for name in (
        "failure_kind",
        "write_may_have_been_submitted",
        "reconciliation_required",
        "automatic_retry_allowed",
        "manual_retry_safe_after_repair",
        "request_stage",
    ):
        if hasattr(error, name):
            result[name] = getattr(error, name)
    return result


class InstantWorkingPathRunner:
    def __init__(self, runtime: Any, *, provider: InstantEffortSelectionProvider) -> None:
        self.runtime = runtime
        self.provider = provider

    def run(
        self,
        *,
        conversation: str,
        acknowledge_live_writes: bool,
        confirm_instant_auto_switch_disabled: bool,
        timeout: float = 150.0,
        poll_interval: float = 0.5,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "production_reasoning_effort_selection_repair_instant_working_path",
            "conversation": conversation,
            "product_write_budget": 1,
            "write_attempts": 0,
            "write_completions": 0,
            "automatic_write_retry": False,
            "failure_phase": None,
            "failure": None,
        }
        phase = "argument_validation"
        try:
            if acknowledge_live_writes is not True:
                raise ValueError("this smoke performs exactly one real product-write attempt")
            if confirm_instant_auto_switch_disabled is not True:
                raise ValueError("confirm_instant_auto_switch_disabled=True is required")
            if not isinstance(conversation, str) or not conversation.strip():
                raise ValueError("conversation is required")

            phase = "support_preflight"
            support = self.provider.instant_effort_selection_support()
            report["support"] = support
            validate_support(support)

            phase = "canonical_preflight"
            initial = self.runtime.health(conversation)
            report["initial_runtime_health"] = initial.to_dict()
            if initial.ready is not True or initial.canonical_status != "completed":
                raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_CANONICAL_NOT_STABLE")

            phase = "single_product_write"
            report["write_attempts"] = 1
            execution = self.runtime.send_text_observed(
                PROMPT,
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                conversation_mode="normal",
                browser_authority_policy="TURN_SCOPED",
            )
            report["write_completions"] = 1
            observation = _observation_record(execution)
            report["observation"] = observation
            lease_id = observation.get("browser_authority_lease_id")
            if not isinstance(lease_id, str) or not lease_id:
                raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_LEASE_ID_MISSING")

            phase = "selection_record_validation"
            selection = self.provider.instant_effort_selection_for_lease(lease_id)
            report["instant_effort_selection"] = selection
            validate_selection(selection)

            phase = "network_route_validation"
            instant = self.provider.instant_mode_for_lease(lease_id)
            report["instant_mode"] = instant
            validate_instant_route(instant)

            phase = "canonical_postcheck"
            final = self.runtime.health(conversation)
            report["final_runtime_health"] = final.to_dict()
            if final.ready is not True or final.canonical_status != "completed":
                raise RuntimeError("PR8_8_INSTANT_WORKING_PATH_CANONICAL_POSTCHECK_FAILED")

            report["summary"] = {
                "single_product_write_completed": True,
                "instant_selected_before_prompt_write": True,
                "selection_mechanism": selection.get("selection_mechanism"),
                "slider_contract_proven": (
                    selection.get("selection_performed") is not True
                    or (
                        selection.get("effort_slider_candidate_count") == 1
                        and selection.get("effort_slider_aria_value_min") == 0
                        and selection.get("effort_slider_aria_value_max") == 2
                        and selection.get("effort_slider_step_count") == 3
                        and selection.get("effort_slider_focus_proven") is True
                        and selection.get("effort_slider_home_dispatched") is True
                    )
                ),
                "advanced_or_model_controls_clicked": False,
                "conversation_writes_before_selection_complete": 0,
                "reasoning_route_observed": False,
                "automatic_retry_attempted": False,
            }
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = _failure(error)
            return report
