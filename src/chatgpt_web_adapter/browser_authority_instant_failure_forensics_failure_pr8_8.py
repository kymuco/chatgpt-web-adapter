from __future__ import annotations

from .browser_authority_instant_failure_forensics_support_pr8_8 import (
    POPUP_SUBTREE_SCHEMA,
    _dict,
    _require,
    _validate_route,
    _validate_surface,
)


def characterize_failure(runner, report, write_error, conversation: str, forensics_timeout: float, phase: list[str]):
    report["write_failure"] = runner._failure(write_error)
    lease = runner._lease(write_error)
    report["failed_browser_authority"] = {
        "lease_id_present_in_local_error": bool(lease["lease_id"]),
        "generation": lease["generation"],
        "state": lease["state"],
        "authority_release_proven": lease["authority_release_proven"],
    }
    lease_id = lease["lease_id"]
    _require(isinstance(lease_id, str) and bool(lease_id), "PR8_8_FRESH_FORENSICS_FAILED_WRITE_LEASE_ID_MISSING")

    phase[0] = "failure_record_reconciliation"
    failure_record = runner.provider.instant_failure_forensics_record(
        lease_id, timeout=min(5.0, forensics_timeout)
    )
    report["instant_failure_record"] = failure_record
    selection = failure_record["selection"]
    _require(failure_record["failure_captured"] is True, "PR8_8_FRESH_FORENSICS_FAILURE_RECORD_NOT_CAPTURED")
    _require(
        failure_record["pre_input_failure_boundary_proven"] is True
        and failure_record["prompt_insertion_reached"] is False
        and failure_record["submit_reached"] is False,
        "PR8_8_FRESH_FORENSICS_PRE_INPUT_BOUNDARY_NOT_PROVEN",
    )
    _require(
        failure_record["raw_error_exported"] is False
        and failure_record["lease_id_exported"] is False,
        "PR8_8_FRESH_FORENSICS_FAILURE_PRIVACY_BOUNDARY_VIOLATED",
    )
    _require(
        failure_record["zero_product_writes"] is True
        and failure_record["automatic_retry"] is False,
        "PR8_8_FRESH_FORENSICS_FAILURE_RECORD_GOVERNANCE_CHANGED",
    )
    _require(
        selection["conversation_write_count_during_selection"] == 0
        and selection["unexpected_conversation_write_before_selection_complete"] is False,
        "PR8_8_FRESH_FORENSICS_CONVERSATION_WRITE_DURING_SELECTION",
    )

    target = failure_record["failure_code"] == "OPTION_NOT_FOUND" and failure_record["failure_reason"] in {
        "instant_option_missing",
        "instant_option_timeout",
    }
    popup_supported = report.get("failure_forensics_support", {}).get("popup_subtree_capture_supported") is True
    popup = failure_record.get("popup_subtree")
    if popup_supported:
        phase[0] = "in_failure_popup_subtree_validation"
        _require(
            failure_record.get("popup_subtree_record_available") is True and isinstance(popup, dict),
            "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_RECORD_NOT_AVAILABLE",
        )
        report["in_failure_popup_subtree"] = popup
        _require(popup.get("schema") == POPUP_SUBTREE_SCHEMA, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_SCHEMA_MISMATCH")
        _require(popup.get("captured_at_failure") is True, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_NOT_CAPTURED_AT_FAILURE")
        _require(
            popup.get("capture_status") in {"POPUP_SUBTREE_CAPTURED", "NO_MODE_POPUP_FOUND"},
            "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_CAPTURE_FAILED",
        )
        _require(
            popup.get("raw_url_exported") is False
            and popup.get("raw_text_exported") is False
            and popup.get("raw_html_exported") is False
            and popup.get("lease_id_exported") is False,
            "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_PRIVACY_BOUNDARY_VIOLATED",
        )
        _require(
            popup.get("zero_product_writes") is True
            and popup.get("automatic_retry") is False
            and popup.get("candidate_cap_dealiased") is True
            and popup.get("global_candidate_cap_used") is False,
            "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_GOVERNANCE_CHANGED",
        )
        _require(
            popup.get("route_kind") == "CONVERSATION"
            and popup.get("observed_conversation_id") == conversation,
            "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_FAILURE_ROUTE_MISMATCH",
        )
        if target:
            _require(
                popup.get("capture_status") == "POPUP_SUBTREE_CAPTURED"
                and popup.get("surface_found") is True,
                "PR8_8_FRESH_FORENSICS_TARGET_FAILURE_POPUP_SUBTREE_MISSING",
            )
            _require(
                popup.get("selected_surface") is not None
                and popup["selected_surface"].get("known_mode_descendant_count", 0) > 0,
                "PR8_8_FRESH_FORENSICS_TARGET_FAILURE_MODE_BEARING_SURFACE_MISSING",
            )

    phase[0] = "retained_tab_resolution"
    retained = runner.provider.characterization_status()
    report["retained_authority_status"] = retained.to_dict()
    tab_id = retained.runtime_tab_id
    _require(isinstance(tab_id, int) and not isinstance(tab_id, bool), "PR8_8_FRESH_FORENSICS_RETAINED_RUNTIME_TAB_MISSING")
    _require(retained.lease_id_present is True, "PR8_8_FRESH_FORENSICS_RETAINED_LEASE_METADATA_MISSING")

    phase[0] = "immediate_route_forensics"
    route = runner.provider.retained_route_identity_forensics(
        conversation,
        expected_runtime_tab_id=tab_id,
        timeout=min(10.0, forensics_timeout),
    )
    report["route_forensics"] = route
    _validate_route(route, conversation, tab_id)
    route_identity = _dict(route.get("route_identity"))
    exact_route = route_identity.get("conversation_matches_expected") is True
    report["surface_forensics_performed"] = False

    if exact_route:
        phase[0] = "immediate_picker_surface_forensics"
        surface = runner.provider.retained_picker_surface_forensics(
            conversation,
            expected_runtime_tab_id=tab_id,
            timeout=forensics_timeout,
        )
        report["picker_surface_forensics"] = surface
        report["surface_forensics_performed"] = True
        _validate_surface(surface, conversation, tab_id)
        report["topology_summary"] = {
            "picker_surface_open": surface["picker_surface_open"],
            "recognized_modes": surface["recognized_modes"],
            "instant_dom_candidate_count": surface["instant_dom_candidate_count"],
            "instant_ax_candidate_count": surface["instant_ax_candidate_count"],
            "dom_candidate_count": len(surface["dom_topology"]["dom_candidates"]),
            "ax_candidate_count": surface["accessibility_topology"]["candidate_count"],
            "popup_surface_count": len(surface["dom_topology"]["popup_surfaces"]),
        }

    phase[0] = "post_forensics_recheck"
    post_health = runner.runtime.health(conversation)
    report["post_forensics_runtime_health"] = runner._health(post_health)
    _require(
        post_health.ready is True and post_health.canonical_status == "completed",
        "PR8_8_FRESH_FORENSICS_POST_PROBE_CANONICAL_STATE_CHANGED",
    )
    final_status = runner.provider.characterization_status()
    report["final_authority_status"] = final_status.to_dict()
    _require(
        final_status.runtime_tab_id == tab_id and final_status.lease_id_present is True,
        "PR8_8_FRESH_FORENSICS_EVIDENCE_BEARING_AUTHORITY_CHANGED",
    )

    report["write_outcome"] = "FAILED_BEFORE_INPUT_FORENSICALLY_CHARACTERIZED"
    report["target_failure_reproduced"] = target
    report["evidence_preservation"] = {
        "retained_runtime_tab_id": tab_id,
        "retained_tab_left_untouched": True,
        "lease_metadata_preserved": True,
        "automatic_retry_attempted": False,
        "additional_product_writes_after_failure": 0,
        "route_forensics_zero_write": True,
        "picker_surface_forensics_zero_write": report["surface_forensics_performed"],
        "in_failure_popup_subtree_persisted": popup_supported and isinstance(popup, dict),
    }
    popup_modes = popup.get("recognized_modes", []) if isinstance(popup, dict) else []
    report["summary"] = {
        "single_live_attempt_completed": True,
        "target_instant_option_failure_reproduced": target,
        "pre_input_failure_boundary_proven": True,
        "prompt_insertion_reached": False,
        "submit_reached": False,
        "conversation_writes_during_selection": 0,
        "route_identity_status": route_identity.get("route_identity_status"),
        "conversation_route_matches_expected": exact_route,
        "surface_forensics_performed": report["surface_forensics_performed"],
        "in_failure_popup_subtree_captured": popup_supported and isinstance(popup, dict) and popup.get("capture_status") == "POPUP_SUBTREE_CAPTURED",
        "popup_candidate_cap_dealiased": popup.get("candidate_cap_dealiased") if isinstance(popup, dict) else None,
        "popup_recognized_modes": popup_modes,
        "popup_instant_mode_label_present": "INSTANT" in popup_modes,
        "popup_mode_label_count": popup.get("mode_label_count") if isinstance(popup, dict) else None,
        "popup_actionable_descendant_count": popup.get("actionable_descendant_count") if isinstance(popup, dict) else None,
        "retained_tab_preserved_for_followup": True,
        "automatic_write_retry_attempted": False,
        "write_budget_respected": True,
    }
    report["ok"] = True
    return report
