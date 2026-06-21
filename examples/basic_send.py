from __future__ import annotations

import argparse

from webchat_adapter import ChatGPTWebClient


DEFAULT_PROMPT = "Reply with one short sentence and nothing else."


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one prompt through a ChatGPT web session.")
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-stream", action="store_true")
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    tokens: list[str] = []

    def on_token(token: str) -> None:
        tokens.append(token)
        if not args.no_stream:
            print(token, end="", flush=True)

    response = client.send(
        args.prompt,
        model=args.model,
        on_token=on_token,
    )

    if not args.no_stream:
        print()

    print("text:", response.text)
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print("total_latency:", response.metrics.total)
    print("tokens_seen:", len(tokens))


if __name__ == "__main__":
    main()
