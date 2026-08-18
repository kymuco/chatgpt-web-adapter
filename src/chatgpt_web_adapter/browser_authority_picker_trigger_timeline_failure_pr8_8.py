from __future__ import annotations

from .browser_authority_instant_failure_forensics_failure_pr8_8 import characterize_failure as _base_characterize_failure
from .browser_authority_instant_failure_forensics_support_pr8_8 import _require
from .browser_authority_picker_trigger_enrichment_pr8_8 import enrich_trigger_report
from .browser_authority_picker_trigger_popup_validation_pr8_8 import _validate_popup_without_presence_requirement
from .browser_authority_picker_trigger_timeline_validation_pr8_8 import _validate_timeline


def characterize_failure_with_picker_trigger(runner, report, write_error, conversation, forensics_timeout, phase):
    support = dict(report.get("failure_forensics_support") or {})
    if support.get("picker_trigger_identity_supported") is not True:
        return _base_characterize_failure(runner, report, write_error, conversation, forensics_timeout, phase)

    # Live evidence disproved the prior requirement that target failure must end
    # with a mode-bearing popup. Preserve the base route/surface/canonical checks
    # while validating popup absence as evidence in this wrapper.
    shadow = dict(support)
    shadow["popup_subtree_capture_supported"] = False
    report["failure_forensics_support"] = shadow
    out = _base_characterize_failure(runner, report, write_error, conversation, forensics_timeout, phase)
    report["failure_forensics_support"] = support
    if out.get("ok") is not True:
        return out

    failure_record = out.get("instant_failure_record") or {}
    target = out.get("target_failure_reproduced") is True
    popup = failure_record.get("popup_subtree")
    if support.get("popup_subtree_capture_supported") is True:
        phase[0] = "in_failure_popup_subtree_validation"
        _require(failure_record.get("popup_subtree_record_available") is True, "PR8_8_FRESH_FORENSICS_POPUP_SUBTREE_RECORD_NOT_AVAILABLE")
        _validate_popup_without_presence_requirement(popup, conversation)
        out["in_failure_popup_subtree"] = popup
        out["evidence_preservation"]["in_failure_popup_subtree_persisted"] = True

    phase[0] = "picker_trigger_timeline_validation"
    _require(failure_record.get("trigger_timeline_record_available") is True, "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_RECORD_NOT_AVAILABLE")
    timeline = failure_record.get("trigger_timeline")
    _validate_timeline(timeline, conversation, target=target)
    out["picker_trigger_timeline"] = timeline
    out["evidence_preservation"]["picker_trigger_timeline_persisted"] = True
    out["ok"] = True
    return enrich_trigger_report(out, popup, timeline)
