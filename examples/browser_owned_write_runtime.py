from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter.browser_owned_write_runtime import BrowserOwnedProductWriteRuntime
from chatgpt_web_adapter.client import ChatGPTWebClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR8.2.4 minimal browser-owned ChatGPT product write runtime"
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
        "pr": "PR8.2.4",
        "health": health.to_dict(),
        "governance": runtime.governance(),
    }
    if args.text is not None:
        if not health.ready:
            report["send"] = {
                "attempted": False,
                "reason": health.reason,
            }
        else:
            response = runtime.send_text(
                args.text,
                conversation=args.conversation,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
            report["send"] = {
                "attempted": True,
                "ok": True,
                "conversation_id": response.conversation.conversation_id,
                "message_id": response.conversation.message_id,
                "finish_reason": response.conversation.finish_reason,
                "observed_model": response.request.observed_model,
                "backend_status": response.metrics.backend_status,
            }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
