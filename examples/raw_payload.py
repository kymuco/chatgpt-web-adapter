from __future__ import annotations

"""Experimental raw ChatGPT web backend payload example.

Not the official OpenAI API. Web backend behavior may change. This creates real
ChatGPT web messages in the account behind your existing web-session auth data.
"""

import argparse
from typing import Any

from webchat_adapter import ChatGPTWebClient, PayloadBuilder, validate_payload


DEFAULT_PROMPT = "Reply with one short sentence from a raw payload."


def print_event(event: dict[str, Any]) -> None:
    event_type = event.get("type", "event")
    if event_type == "assistant_token":
        return
    print(f"[event] {event_type}: {event}")


def print_token(token: str) -> None:
    print(token, end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send an experimental raw ChatGPT web backend payload.",
    )
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--temporary", action="store_true")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    payload = PayloadBuilder.new_chat(
        args.prompt,
        model=args.model,
        temporary=args.temporary,
    )
    validate_payload(payload)

    response = client.send_payload(
        payload,
        on_token=print_token,
        on_event=print_event,
    )

    print()
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print(response.text)


if __name__ == "__main__":
    main()
