from __future__ import annotations

from .browser_authority_instant_failure_forensics_preflight_pr8_8 import run_preflight as _base_run_preflight
from .browser_authority_instant_failure_forensics_support_pr8_8 import _require


def _validate_trigger_support(support):
    if "picker_trigger_identity_supported" not in support:
        return
    _require(
        support["picker_trigger_identity_supported"]
        and support["click_actuation_verification_supported"]
        and support["per_poll_menu_materialization_timeline_supported"]
        and support["false_open_surface_dealiasing_supported"]
        and support["trigger_timeline_persistence_supported"]
        and support["raw_trigger_text_redaction_supported"],
        "PR8_8_FRESH_FORENSICS_TRIGGER_TIMELINE_EXTENSION_RELOAD_REQUIRED",
    )


def run_preflight_with_picker_trigger(runner, report, conversation, timeout, phase):
    support = runner.provider.instant_failure_forensics_support()
    report["failure_forensics_support"] = support
    _validate_trigger_support(support)
    return _base_run_preflight(runner, report, conversation, timeout, phase)
