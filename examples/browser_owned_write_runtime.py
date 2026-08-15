from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter.browser_owned_write_runtime import (
    BrowserOwnedProductWriteRuntime,
    BrowserOwnedWriteObservation,
    BrowserOwnedWriteRuntimeError,
)
from chatgpt_web_adapter.client import ChatGPTWebClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR8.2.4a.1 browser-owned ChatGPT write runtime with finality repair"
    )
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--send", dest="text")
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    args = parser.parse_args()

    # Session/read lifecycle may refresh browserlessly, but this production
    # runtime must never initiate interactive browser login or Sentinel repair.
    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    runtime = BrowserOwnedProductWriteRuntime(client)
    health = runtime.health(args.conversation)

    report = {
        "pr": "PR8.2.4a.1",
        "health": health.to_dict(),
        "governance": runtime.governance(),
    }
    exit_code = 0
    if args.text is not None:
        if not health.ready:
            report["send"] = {
                "attempted": False,
                "reason": health.reason,
            }
            exit_code = 2
        else:
            last_write_event = None

            def capture_event(event):
                nonlocal last_write_event
                if isinstance(event, dict) and event.get("type") == "browser_native_write_completed":
                    last_write_event = dict(event)

            try:
                execution = runtime.send_text_observed(
                    args.text,
                    conversation=args.conversation,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                    on_event=capture_event,
                )
            except BrowserOwnedWriteRuntimeError as error:
                observation = BrowserOwnedWriteObservation.from_event(last_write_event)
                report["send"] = {
                    "attempted": True,
                    "ok": False,
                    "error": str(error),
                    "failure_kind": error.failure_kind,
                    "write_may_have_been_submitted": error.write_may_have_been_submitted,
                    "reconciliation_required": error.reconciliation_required,
                    "automatic_retry_allowed": error.automatic_retry_allowed,
                    "manual_retry_safe_after_repair": error.manual_retry_safe_after_repair,
                    "runtime_observation": observation.to_dict(),
                }
                exit_code = 2
            else:
                response = execution.response
                report["send"] = {
                    "attempted": True,
                    "ok": True,
                    "conversation_id": response.conversation.conversation_id,
                    "message_id": response.conversation.message_id,
                    "finish_reason": response.conversation.finish_reason,
                    "observed_model": response.request.observed_model,
                    "backend_status": response.metrics.backend_status,
                    "runtime_observation": execution.observation.to_dict(),
                }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
