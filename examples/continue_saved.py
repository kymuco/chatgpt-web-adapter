from __future__ import annotations

"""Persist and continue a conversation across separate runs.

Purpose: show how to save ``ChatConversation`` state and reuse it later.
Surface: stable
Prerequisites: valid ``auth_data.json`` and write access to a local state file.
"""

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter import ChatConversation, ChatGPTWebClient


DEFAULT_FIRST_PROMPT = "Start a short conversation about SQLite."
DEFAULT_FOLLOW_UP = "Continue from the saved conversation and compare it with PostgreSQL."


def _load_conversation(path: Path) -> ChatConversation | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return ChatConversation.from_dict(payload)


def _save_conversation(path: Path, conversation: ChatConversation) -> None:
    path.write_text(
        json.dumps(conversation.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save ChatConversation metadata and continue it later.",
    )
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--state-file", default="conversation_state.json")
    parser.add_argument("--first-prompt", default=DEFAULT_FIRST_PROMPT)
    parser.add_argument("--follow-up", default=DEFAULT_FOLLOW_UP)
    parser.add_argument("--reset", action="store_true", help="Ignore any existing state file.")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    state_path = Path(args.state_file)
    conversation = None if args.reset else _load_conversation(state_path)

    if conversation is None:
        first = client.send(args.first_prompt, model=args.model)
        conversation = first.conversation
        _save_conversation(state_path, conversation)
        print("started conversation")
        print("conversation_id:", conversation.conversation_id)
        print("message_id:", conversation.message_id)
        print(first.text)

    follow_up = client.send(
        args.follow_up,
        model=args.model,
        conversation=conversation,
    )
    _save_conversation(state_path, follow_up.conversation)

    print("continued conversation")
    print("conversation_id:", follow_up.conversation.conversation_id)
    print("message_id:", follow_up.conversation.message_id)
    print(follow_up.text)


if __name__ == "__main__":
    main()
