from __future__ import annotations

"""Attach to an existing ChatGPT web conversation.

Purpose: inspect conversation metadata for a URL or raw conversation id.
Surface: stable
Prerequisites: valid ``auth_data.json`` and an existing conversation.
"""

import argparse

from chatgpt_web_adapter import ChatGPTWebClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attach to an existing ChatGPT web conversation by URL or id.",
    )
    parser.add_argument("conversation", help="ChatGPT conversation URL or raw conversation id")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    attached = client.attach_conversation(args.conversation)

    print("conversation_id:", attached.conversation_id)
    print("current_node:", attached.current_node)
    print("detected_model:", attached.detected_model)
    print("title:", attached.title)
    print("message_id:", attached.conversation.message_id)
    print("finish_reason:", attached.conversation.finish_reason)


if __name__ == "__main__":
    main()
