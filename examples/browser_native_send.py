from __future__ import annotations

import argparse

from chatgpt_web_adapter import BrowserNativeTurnProvider, ChatGPTWebClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an ordinary text turn through the persistent browser-native ChatGPT runtime.")
    parser.add_argument("prompt")
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=max(10, int(args.timeout)))
    client.set_browser_native_turn_provider(BrowserNativeTurnProvider(turn_timeout=args.timeout))
    response = client.send_browser_native(
        args.prompt,
        conversation=args.conversation,
        timeout=args.timeout,
    )
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print("model:", response.request.observed_model)
    print(response.text)


if __name__ == "__main__":
    main()
