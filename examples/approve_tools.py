from __future__ import annotations

"""Approve pending tool actions from a ChatGPT web conversation.

This example approves pending tool actions. Review the target conversation before
using it, and add your own allowlist checks for repositories, files, or actions.
"""

import argparse
from typing import Any

from webchat_adapter import ChatConversation, ChatGPTWebClient


def print_event(event: dict[str, Any]) -> None:
    event_type = event.get("type", "event")
    if event_type == "assistant_token":
        return
    print(f"[event] {event_type}: {event}")


def print_token(token: str) -> None:
    print(token, end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approve pending tool actions through an existing ChatGPT web session.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompt", help="Send a prompt and auto-approve follow-up tool actions.")
    mode.add_argument("--conversation", help="Watch an existing conversation URL or id for pending approvals.")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-5-5-thinking")
    parser.add_argument("--reasoning-effort", default="extended")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--pending-poll-interval", type=float, default=3.0)
    parser.add_argument("--settle-delay", type=float, default=2.0)
    parser.add_argument("--max-rounds", type=int, default=0)
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)

    if args.prompt:
        response = client.send_and_auto_approve(
            args.prompt,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            pending_poll_interval=args.pending_poll_interval,
            settle_delay=args.settle_delay,
            max_rounds=args.max_rounds,
            on_token=print_token,
            on_event=print_event,
        )
    else:
        attached = client.attach_conversation(args.conversation)
        response = client.wait_and_approve_pending_actions(
            attached.conversation,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            pending_poll_interval=args.pending_poll_interval,
            settle_delay=args.settle_delay,
            max_rounds=args.max_rounds,
            on_token=print_token,
            on_event=print_event,
        )

    print()
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print(response.text)


if __name__ == "__main__":
    main()
