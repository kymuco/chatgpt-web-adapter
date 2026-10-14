"""Qwen SDK runner. Send your own messages; no tests, probes or sample sends.

Requires: pip install -e .   (from chatgpt-web-adapter checkout)
Usage:
    python qwen_sdk.py --import-auth
    python qwen_sdk.py "Привет!"
    python qwen_sdk.py --transport browser "Привет!"
    python qwen_sdk.py
"""

from __future__ import annotations

import argparse
import sys

from chatgpt_web_adapter.qwen_client import QwenClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qwen SDK: background browser or direct HTTP")
    parser.add_argument(
        "--transport",
        choices=("http", "browser"),
        default="http",
        help="http (default): no browser; browser: existing Qwen tab only",
    )
    parser.add_argument(
        "--import-auth",
        action="store_true",
        help="save Qwen authorization from an existing signed-in Chrome tab; do not send",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Qwen model identifier (direct HTTP only; not validated by the SDK)",
    )
    parser.add_argument("message", nargs="*", help="message to send; omit for interactive mode")
    args = parser.parse_args(argv)

    if args.import_auth and args.transport != "http":
        parser.error("--import-auth is only supported with --transport http")
    if args.import_auth and args.message:
        parser.error("--import-auth does not send messages; run it separately")
    if args.model and args.transport == "browser":
        parser.error("--model is currently supported only with --transport http")

    client = QwenClient(
        transport=args.transport,
        **({"model": args.model} if args.model else {}),
    )

    if args.import_auth:
        client.import_browser_auth()
        print("Авторизация Qwen сохранена локально. Сообщений не отправлено.")
        return 0

    browser_conversation = None

    def send(message: str, *, interactive: bool) -> None:
        nonlocal browser_conversation
        if args.transport == "http" and interactive:
            print("Qwen: ", end="", flush=True)
            result = client.send_text(
                message, on_token=lambda fragment: print(fragment, end="", flush=True)
            )
            print()
        else:
            result = client.send_text(
                message,
                conversation=browser_conversation if args.transport == "browser" else None,
            )
            print(result.text)
        if args.transport == "browser":
            browser_conversation = result.conversation

    try:
        if args.message:
            send(" ".join(args.message), interactive=False)
            return 0

        print("Qwen SDK · transport=" + args.transport + " · /exit для выхода")
        while True:
            try:
                message = input("Вы: ").strip()
            except EOFError:
                break
            if message.lower() in {"/exit", "/quit"}:
                break
            if message:
                send(message, interactive=True)
        return 0
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as error:
        # Qwen HTTP failures redact access tokens and cookies in their messages.
        print("Qwen SDK error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
