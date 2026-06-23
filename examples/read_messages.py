from __future__ import annotations

"""Read messages from the current branch of a conversation.

Purpose: inspect conversation history with optional role filtering.
Surface: stable
Prerequisites: valid ``auth_data.json`` and an existing conversation.
"""

import argparse

from chatgpt_web_adapter import ChatGPTWebClient


def _preview(text: str, *, max_chars: int = 500) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read messages from the current branch of a ChatGPT web conversation.",
    )
    parser.add_argument("conversation", help="ChatGPT conversation URL or raw conversation id")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--role", action="append", dest="roles")
    parser.add_argument("--include-empty", action="store_true")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    messages = client.get_messages(
        args.conversation,
        limit=args.limit,
        roles=args.roles,
        include_empty=args.include_empty,
    )

    print("message_count:", len(messages))
    for message in messages:
        print("---")
        print("role:", message.role)
        print("message_id:", message.message_id)
        print("node_id:", message.node_id)
        print("model:", message.model)
        print("finish_reason:", message.finish_reason)
        print(_preview(message.text))


if __name__ == "__main__":
    main()
