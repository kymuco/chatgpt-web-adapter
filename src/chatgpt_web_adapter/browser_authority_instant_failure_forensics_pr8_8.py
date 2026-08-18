from __future__ import annotations

import argparse
import json
from pathlib import Path

from .browser_authority_instant_failure_forensics_failure_pr8_8 import characterize_failure
from .browser_authority_instant_failure_forensics_preflight_pr8_8 import run_preflight
from .browser_authority_instant_failure_forensics_success_pr8_8 import characterize_success
from .browser_authority_instant_failure_forensics_support_pr8_8 import (
    InstantFailureForensicsProvider,
    _int,
    _str,
)
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime

PROMPT = "Reply with exactly: SDK_PR8_8_INSTANT_FAILURE_FORENSIC_REPRO_OK"


class FreshInstantFailureForensicsRunner:
    def __init__(self, runtime, *, provider):
        self.runtime = runtime
        self.provider = provider

    @staticmethod
    def _failure(error):
        out = {
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
                out[name] = getattr(error, name)
        return out

    @staticmethod
    def _health(health):
        fn = getattr(health, "to_dict", None)
        return fn() if callable(fn) else {}

    @staticmethod
    def _lease(error):
        lease = getattr(error, "browser_authority_lease", None)
        state = getattr(getattr(lease, "state", None), "value", None)
        release_proven = getattr(lease, "authority_release_proven", None)
        return {
            "lease_id": _str(getattr(lease, "lease_id", None)),
            "generation": _int(getattr(lease, "generation", None)),
            "state": _str(state),
            "authority_release_proven": release_proven if isinstance(release_proven, bool) else None,
        }

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
            raise ValueError("this reproduction performs exactly one real product-write attempt")
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
            "probe_context": "fresh_instant_failure_reproduction_pre_input_route_picker_forensics",
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
            run_preflight(self, report, conversation, timeout, phase)
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
                return characterize_failure(
                    self, report, write_error, conversation, forensics_timeout, phase
                )
            return characterize_success(
                self, report, execution, conversation, forensics_timeout, phase
            )
        except Exception as error:
            report["failure_phase"] = phase[0]
            report["failure"] = self._failure(error)
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "PR8.8 single-write fresh Instant failure reproduction with immediate "
            "pre-input, route, and picker topology forensics"
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--forensics-timeout", type=float, default=20.0)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--confirm-instant-auto-switch-disabled", action="store_true")
    args = parser.parse_args(argv)
    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required: exactly one real product-write attempt is budgeted")
    if not args.confirm_instant_auto_switch_disabled:
        parser.error("--confirm-instant-auto-switch-disabled is required")

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = InstantFailureForensicsProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = FreshInstantFailureForensicsRunner(runtime, provider=provider).run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        forensics_timeout=args.forensics_timeout,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
