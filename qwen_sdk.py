"""Qwen SDK runner. Send your own messages; no tests, probes or sample sends.

Requires: pip install -e .   (from chatgpt-web-adapter checkout)
Usage:
    python qwen_sdk.py --import-auth
    python qwen_sdk.py "Привет!"
    python qwen_sdk.py --transport reverse "Привет!"  # optional qwen-reverse library
    python qwen_sdk.py --transport browser "Привет!"
    python qwen_sdk.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from chatgpt_web_adapter.qwen_auth_store import load_qwen_credentials

from chatgpt_web_adapter.qwen_client import QwenClient


async def _run_reverse(messages: list[str], *, model: str | None = None) -> int:
    """Opt-in, browserless Qwen Web adapter. No probe messages or browser tabs."""
    try:
        from qwen_reverse import Conversation
    except ImportError as error:
        raise RuntimeError(
            "QWEN_REVERSE_NOT_INSTALLED: "
            "python -m pip install qwen-reverse==0.1.6 "
            "(unofficial third-party library)"
        ) from error

    # Explicit account identity: never silently switch to anonymous traffic.
    credentials = load_qwen_credentials()
    token = credentials.access_token
    conversation = Conversation(
        model=model or "qwen3.8-max",
        token=token,
        reasoning_effort="none",
    )

    async def send(message: str) -> None:
        seen = False
        completed = False
        async for event in conversation.stream(message):
            if event.get("type") == "content":
                fragment = event.get("data")
                if isinstance(fragment, str) and fragment:
                    print(fragment, end="", flush=True)
                    seen = True
            elif event.get("type") == "done":
                completed = True
        if seen:
            print()
        if not completed or not seen:
            raise RuntimeError("QWEN_REVERSE_COMPLETION_NOT_PROVEN")

    try:
        if messages:
            await send(" ".join(messages))
            return 0
        print("Qwen SDK · transport=reverse · /exit для выхода")
        while True:
            try:
                message = input("Вы: ").strip()
            except EOFError:
                return 0
            if message.lower() in {"/exit", "/quit"}:
                return 0
            if message:
                print("Qwen: ", end="", flush=True)
                await send(message)
    except Exception as error:
        # The third-party client may include server data in exception details;
        # never let imported auth values leak into a terminal log.
        message = str(error).replace(token, "[REDACTED]")
        for cookie in credentials.cookies.values():
            if cookie:
                message = message.replace(cookie, "[REDACTED]")
        print("Qwen SDK error: " + message, file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qwen SDK: background browser or direct HTTP")
    parser.add_argument(
        "--transport",
        choices=("http", "browser", "reverse"),
        default="http",
        help="http: raw HTTPS; browser: existing tab; reverse: optional unofficial Python HTTPS",
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

    if args.transport == "reverse":
        return asyncio.run(_run_reverse(args.message, model=args.model))

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
