from __future__ import annotations

import argparse
import json
from pathlib import Path

from .browser_authority_instant_effort_selection_pr8_8 import InstantEffortSelectionProvider
from .browser_authority_instant_working_path_runner_pr8_8 import InstantWorkingPathRunner
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PR8.8 production reasoning-effort Instant working-path smoke"
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--confirm-instant-auto-switch-disabled", action="store_true")
    args = parser.parse_args(argv)

    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required")
    if not args.confirm_instant_auto_switch_disabled:
        parser.error("--confirm-instant-auto-switch-disabled is required")

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = InstantEffortSelectionProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = InstantWorkingPathRunner(runtime, provider=provider).run(
        conversation=args.conversation,
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
