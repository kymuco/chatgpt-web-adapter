from __future__ import annotations

from .browser_authority_instant_selection_repair_pr8_8 import InstantSelectionRepairLatencyRunner
from .browser_authority_instant_failure_forensics_support_pr8_8 import SCHEMA, _require


def run_preflight(runner, report, conversation: str, timeout: float, phase: list[str]) -> None:
    phase[0] = "support_preflight"
    failure_support = runner.provider.instant_failure_forensics_support()
    selection_support = runner.provider.instant_selection_support()
    route_support = runner.provider.retained_route_identity_support()
    picker_support = runner.provider.retained_picker_forensics_support()
    report["failure_forensics_support"] = failure_support
    report["instant_selection_support"] = selection_support
    report["route_forensics_support"] = route_support
    report["picker_forensics_support"] = picker_support

    _require(
        failure_support["supported"]
        and failure_support["schema"] == SCHEMA
        and failure_support["failure_record_persistence_supported"]
        and failure_support["pre_input_failure_boundary_supported"]
        and failure_support["retained_route_forensics_composition_supported"]
        and failure_support["retained_picker_forensics_composition_supported"]
        and failure_support["raw_error_redaction_supported"]
        and not failure_support["lease_id_exported"]
        and failure_support["zero_product_writes"]
        and not failure_support["automatic_retry"],
        "PR8_8_FRESH_FORENSICS_EXTENSION_RELOAD_REQUIRED",
    )
    _require(
        selection_support.get("instant_selection_repair_supported") is True
        and selection_support.get("product_ui_selection_supported") is True,
        "PR8_8_FRESH_FORENSICS_SELECTION_SUPPORT_UNAVAILABLE",
    )
    _require(
        route_support.get("retained_route_identity_supported") is True
        and route_support.get("zero_product_writes") is True,
        "PR8_8_FRESH_FORENSICS_ROUTE_SUPPORT_UNAVAILABLE",
    )
    _require(
        picker_support.get("retained_picker_forensics_supported") is True
        and picker_support.get("zero_product_writes") is True,
        "PR8_8_FRESH_FORENSICS_PICKER_SUPPORT_UNAVAILABLE",
    )

    phase[0] = "clean_baseline_preflight"
    status = runner.provider.characterization_status()
    report["initial_authority_status"] = status.to_dict()
    _require(status.runtime_tab_id is None, "PR8_8_FRESH_FORENSICS_INITIAL_RUNTIME_TAB_PRESENT")
    _require(status.lease_id_present is False, "PR8_8_FRESH_FORENSICS_INITIAL_LEASE_PRESENT")
    health = runner.runtime.health(conversation)
    report["initial_runtime_health"] = runner._health(health)
    _require(
        health.ready is True and health.canonical_status == "completed",
        "PR8_8_FRESH_FORENSICS_CONVERSATION_NOT_STABLE_COMPLETED",
    )

    phase[0] = "fresh_tab_mode_preflight"
    preflight = runner.provider.selected_mode_preflight(conversation, timeout=min(20.0, timeout))
    report["fresh_tab_mode_preflight"] = preflight
    InstantSelectionRepairLatencyRunner._validate_preflight_mode(preflight, conversation)
    post = runner.provider.characterization_status()
    report["post_mode_preflight_authority_status"] = post.to_dict()
    _require(
        post.runtime_tab_id is None and post.lease_id_present is False,
        "PR8_8_FRESH_FORENSICS_MODE_PREFLIGHT_DID_NOT_RESTORE_CLEAN_BASELINE",
    )
