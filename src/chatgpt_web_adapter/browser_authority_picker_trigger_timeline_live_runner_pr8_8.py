from __future__ import annotations

from .browser_authority_instant_failure_forensics_pr8_8 import (
    FreshInstantFailureForensicsRunner,
    PROMPT,
)
from .browser_authority_instant_failure_forensics_success_pr8_8 import characterize_success
from .browser_authority_picker_trigger_timeline_pr8_8 import (
    PickerTriggerTimelineForensicsProvider,
    characterize_failure_with_picker_trigger,
    run_preflight_with_picker_trigger,
)


class PickerTriggerTimelineLiveRunner(FreshInstantFailureForensicsRunner):
    def run(
        self,
        *,
        acknowledge_live_writes,
        confirm_instant_auto_switch_disabled,
        conversation,
        timeout=150.0,
        poll_interval=0.5,
        forensics_timeout=20.0,
    ):
        if acknowledge_live_writes is not True:
            raise ValueError("this characterization performs exactly one real product-write attempt")
        if confirm_instant_auto_switch_disabled is not True:
            raise ValueError("confirm_instant_auto_switch_disabled=True is required")
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if timeout <= 0 or poll_interval <= 0 or forensics_timeout <= 0:
            raise ValueError("timeouts and poll_interval must be positive")
        conversation = conversation.strip()
        report = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "model_picker_trigger_identity_click_actuation_timeline",
            "conversation": conversation,
            "requested_model_mode": "INSTANT",
            "product_write_budget": 1,
            "write_attempts": 0,
            "write_completions": 0,
            "automatic_write_retry": False,
            "retained_tab_close_performed": False,
            "failure_phase": None,
            "failure": None,
        }
        phase = ["support_preflight"]
        try:
            run_preflight_with_picker_trigger(self, report, conversation, timeout, phase)
            phase[0] = "single_live_instant_attempt"
            report["write_attempts"] = 1
            try:
                execution = self.runtime.send_text_observed(
                    PROMPT,
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    conversation_mode="normal",
                )
            except Exception as write_error:
                return characterize_failure_with_picker_trigger(
                    self, report, write_error, conversation, forensics_timeout, phase
                )
            return characterize_success(
                self, report, execution, conversation, forensics_timeout, phase
            )
        except Exception as error:
            report["failure_phase"] = phase[0]
            report["failure"] = self._failure(error)
            return report

