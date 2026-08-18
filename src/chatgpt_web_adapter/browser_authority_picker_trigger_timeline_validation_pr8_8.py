from __future__ import annotations

from .browser_authority_instant_failure_forensics_support_pr8_8 import _require
from .browser_authority_picker_trigger_timeline_support_pr8_8 import TRIGGER_TIMELINE_SCHEMA


def _validate_timeline(timeline, conversation, *, target):
    _require(isinstance(timeline, dict), "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_RECORD_NOT_AVAILABLE")
    _require(
        timeline.get("schema") == TRIGGER_TIMELINE_SCHEMA
        and timeline.get("captured_at_failure") is True
        and timeline.get("capture_status") == "TRIGGER_TIMELINE_CAPTURED",
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_NOT_CAPTURED",
    )
    _require(
        timeline.get("raw_url_exported") is False
        and timeline.get("raw_text_exported") is False
        and timeline.get("raw_html_exported") is False
        and timeline.get("lease_id_exported") is False,
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_PRIVACY_BOUNDARY_VIOLATED",
    )
    _require(
        timeline.get("zero_product_writes") is True
        and timeline.get("automatic_retry") is False,
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_GOVERNANCE_CHANGED",
    )
    _require(
        timeline.get("route_kind") == "CONVERSATION"
        and timeline.get("observed_conversation_id") == conversation,
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_ROUTE_MISMATCH",
    )
    if not target:
        return
    _require(
        timeline.get("picker_point_available") is True
        and timeline.get("click_dispatch_completed") is True,
        "PR8_8_FRESH_FORENSICS_PICKER_CLICK_NOT_OBSERVED",
    )
    _require(
        timeline.get("timeline_sample_count", 0) >= 3
        and timeline.get("poll_sample_count", 0) >= 1,
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_INCOMPLETE",
    )
    phases = {item.get("phase") for item in timeline.get("timeline_samples", []) if isinstance(item, dict)}
    _require({"PRE_CLICK", "POST_CLICK_IMMEDIATE", "OPTION_POLL"}.issubset(phases), "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_PHASES_MISSING")
    _require(
        timeline.get("materialization_outcome") in {
            "MODE_BEARING_PICKER_MATERIALIZED",
            "TRIGGER_ACTUATED_WITHOUT_MODE_PICKER",
            "CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION",
        },
        "PR8_8_FRESH_FORENSICS_TRIGGER_MATERIALIZATION_OUTCOME_INVALID",
    )
