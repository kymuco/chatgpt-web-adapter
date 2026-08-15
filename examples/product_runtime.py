from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter import assemble_product_runtime


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Primary production ChatGPT product runtime example"
    )
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--send", dest="text")
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    args = parser.parse_args()

    runtime = assemble_product_runtime(
        transport="browser-owned",
        auth_file=args.auth_file,
    )
    health = runtime.health(args.conversation)
    report = {
        "surface": "PRIMARY_PRODUCTION",
        "transport": runtime.transport,
        "health": health.to_dict(),
        "capabilities": runtime.capabilities().to_dict(),
        "governance": runtime.governance(),
    }

    if args.text is not None:
        execution = runtime.send_text_observed(
            args.text,
            conversation=args.conversation,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
        response = execution.response
        report["send"] = {
            "ok": True,
            "text": response.text,
            "conversation_id": response.conversation.conversation_id,
            "message_id": response.conversation.message_id,
            "finish_reason": response.conversation.finish_reason,
            "observed_model": response.request.observed_model,
            "backend_status": response.metrics.backend_status,
            "runtime_observation": execution.observation.to_dict(),
            "provenance": execution.provenance.to_dict(),
        }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
