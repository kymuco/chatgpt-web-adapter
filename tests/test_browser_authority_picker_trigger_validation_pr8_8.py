from __future__ import annotations

import pytest
from chatgpt_web_adapter.browser_authority_picker_trigger_timeline_preflight_pr8_8 import _validate_trigger_support
from chatgpt_web_adapter.browser_authority_picker_trigger_popup_validation_pr8_8 import _validate_popup_without_presence_requirement
from chatgpt_web_adapter.browser_authority_picker_trigger_timeline_validation_pr8_8 import _validate_timeline

CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"

def test_no_mode_popup_and_click_timeline_are_valid_evidence():
    popup = {"schema":1,"captured_at_failure":True,"capture_status":"NO_MODE_POPUP_FOUND","route_kind":"CONVERSATION","observed_conversation_id":CONVERSATION,"raw_url_exported":False,"raw_text_exported":False,"raw_html_exported":False,"lease_id_exported":False,"zero_product_writes":True,"automatic_retry":False,"candidate_cap_dealiased":True,"global_candidate_cap_used":False}
    _validate_popup_without_presence_requirement(popup, CONVERSATION)
    timeline = {"schema":1,"captured_at_failure":True,"capture_status":"TRIGGER_TIMELINE_CAPTURED","route_kind":"CONVERSATION","observed_conversation_id":CONVERSATION,"picker_point_available":True,"click_dispatch_completed":True,"timeline_sample_count":3,"poll_sample_count":1,"timeline_samples":[{"phase":"PRE_CLICK"},{"phase":"POST_CLICK_IMMEDIATE"},{"phase":"OPTION_POLL"}],"materialization_outcome":"CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION","raw_url_exported":False,"raw_text_exported":False,"raw_html_exported":False,"lease_id_exported":False,"zero_product_writes":True,"automatic_retry":False}
    _validate_timeline(timeline, CONVERSATION, target=True)


def test_missing_trigger_capability_fails_closed():
    support = {"picker_trigger_identity_supported":True,"click_actuation_verification_supported":True,"per_poll_menu_materialization_timeline_supported":False,"false_open_surface_dealiasing_supported":True,"trigger_timeline_persistence_supported":True,"raw_trigger_text_redaction_supported":True}
    with pytest.raises(RuntimeError, match="TRIGGER_TIMELINE_EXTENSION_RELOAD_REQUIRED"):
        _validate_trigger_support(support)
