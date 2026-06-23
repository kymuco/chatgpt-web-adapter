from __future__ import annotations

"""Poll the lifecycle status of an existing conversation.

Purpose: reference example for ``get_status()`` and pending approval discovery.
Surface: stable
Prerequisites: valid ``auth_data.json`` and an existing conversation.
"""

import argparse
import time

from chatgpt_web_adapter import ChatGPTWebClient

TERMINAL_STATUSES = {"completed", "awaiting_tool_approval", "user_last_message"}


def _print_status(client: ChatGPTWebClient, conversation: str) -> str:
    status = client.get_status(conversation)
    approval = client.get_pending_approval(conversation)

    print("status:", status.status)
    print("node_id:", status.node_id)
    print("message_id:", status.message_id)
    print("role:", status.role)
    print("recipient:", status.recipient)
    print("async_status:", status.async_status)
    print("finish_reason:", status.finish_reason)
    print("pending_approval:", status.pending_approval)

    if approval is not None:
        print("approval_tool_message_id:", approval.tool_message_id)
        print("approval_target_message_id:", approval.target_message_id)
        print("approval_recipient:", approval.recipient)

    return status.status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll the lifecycle status of an existing ChatGPT web conversation.",
    )
    parser.add_argument("conversation", help="ChatGPT conversation URL or raw conversation id")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--max-polls", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    polls = 1 if args.once else max(1, args.max_polls)

    for index in range(polls):
        print("poll:", index + 1)
        status = _print_status(client, args.conversation)
        if args.once or status in TERMINAL_STATUSES:
            break
        time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    main()
