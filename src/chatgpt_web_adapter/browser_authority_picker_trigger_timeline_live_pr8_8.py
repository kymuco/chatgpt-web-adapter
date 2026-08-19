from __future__ import annotations

import argparse
import json
from pathlib import Path

from .browser_authority_picker_trigger_timeline_live_runner_pr8_8 import PickerTriggerTimelineLiveRunner
from .browser_authority_picker_trigger_timeline_pr8_8 import PickerTriggerTimelineForensicsProvider
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="PR8.8 model-picker trigger identity, click-actuation and per-poll materialization timeline"
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
    provider = PickerTriggerTimelineForensicsProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = PickerTriggerTimelineLiveRunner(runtime, provider=provider).run(
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
