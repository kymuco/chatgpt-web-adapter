from __future__ import annotations

from .browser_authority_instant_failure_forensics_support_pr8_8 import _require


def _validate_popup_without_presence_requirement(popup, conversation):
    _require(isinstance(popup, dict), "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_RECORD_NOT_AVAILABLE")
    _require(popup.get("schema") == 1, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_SCHEMA_MISMATCH")
    _require(popup.get("captured_at_failure") is True, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_NOT_CAPTURED_AT_FAILURE")
    _require(popup.get("capture_status") in {"POPUP_SUBTREE_CAPTURED", "NO_MODE_POPUP_FOUND"}, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_CAPTURE_FAILED")
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
