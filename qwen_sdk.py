"""Qwen SDK runner. Send your own messages; no tests, probes or sample sends.

Requires: pip install -e .   (from chatgpt-web-adapter checkout)
Usage:
    python qwen_sdk.py --import-auth
    python qwen_sdk.py "Привет!"
    python qwen_sdk.py --transport http "Привет!"  # experimental
    python qwen_sdk.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import textwrap

from chatgpt_web_adapter.qwen_client import QwenClient


class _QwenLiveAnswer:
    """Redraw the same terminal region when Qwen revises earlier DOM text.

    Unlike append-only snapshots, this does not duplicate the whole answer on
    late citations or edits. Non-terminal output emits the final answer once.
    """

    def __init__(self, output=None) -> None:
        self._out = output if output is not None else sys.stdout
        self._interactive = bool(getattr(self._out, "isatty", lambda: False)())
        self._rows = 0
        self._current = ""

    def update(self, text: str) -> None:
        if not isinstance(text, str) or text == self._current:
            return
        # Model-generated terminal controls must never execute.
        safe = "".join(
            c for c in text if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127)
        )
        self._current = safe
        if not self._interactive:
            return
        width = max(24, shutil.get_terminal_size((80, 24)).columns - 8)
        lines = []
        for paragraph in safe.expandtabs(4).split("\n"):
            lines.extend(
                textwrap.wrap(
                    paragraph,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=False,
                )
                or [""]
            )
        rendered = "\n".join(lines)
        if self._rows:
            self._out.write(f"\x1b[{self._rows}F\x1b[J")
        self._out.write(rendered + "\n")
        self._out.flush()
        self._rows = len(lines)

    def finish(self, final_text: str) -> None:
        self.update(final_text)
        if not self._interactive:
            self._out.write(self._current + "\n")
            self._out.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Qwen SDK: background browser or direct HTTP"
    )
    parser.add_argument(
        "--transport",
        choices=("http", "browser"),
        default=None,
        help="browser (default): existing Qwen tab; http: experimental direct requests",
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
    parser.add_argument(
        "message", nargs="*", help="message to send; omit for interactive mode"
    )
    parser.add_argument(
        "--auto-confirm-age",
        action="store_true",
        help="confirm Qwen age dialog using --birth-year",
    )
    parser.add_argument(
        "--birth-year",
        type=int,
        default=2000,
        help="your birth year (default: 2000, matching site)",
    )
    parser.add_argument(
        "--foreground-tab",
        action="store_true",
        help="opt in: activate Qwen's Chrome tab before sending (diagnose hidden-tab stalls)",
    )
    parser.add_argument(
        "--stream",
        choices=("dom", "network"),
        default="dom",
        help="browser streaming source",
    )
    parser.add_argument(
        "--chat", help="existing Qwen chat URL or ID; omit for a new chat"
    )
    args = parser.parse_args(argv)

    args.transport = args.transport or ("http" if args.import_auth else "browser")

    if args.import_auth and args.transport != "http":
        parser.error("--import-auth is only supported with --transport http")
    if args.import_auth and args.message:
        parser.error("--import-auth does not send messages; run it separately")
    if args.model and args.transport == "browser":
        parser.error("--model is currently supported only with --transport http")
    if args.foreground_tab and args.transport != "browser":
        parser.error("--foreground-tab requires browser transport")

    client = QwenClient(
        transport=args.transport,
        **({"model": args.model} if args.model else {}),
        **({"foreground_tab": True} if args.foreground_tab else {}),
        **(
            {"auto_confirm_age": True, "birth_year": args.birth_year}
            if args.auto_confirm_age
            else {}
        ),
    )

    if args.chat and args.transport != "browser":
        parser.error("--chat currently requires browser transport")
    try:
        browser_conversation = QwenClient.chat(args.chat) if args.chat else None
    except ValueError as error:
        parser.error(str(error))

    def send(message: str, *, interactive: bool) -> None:
        nonlocal browser_conversation
        if args.transport == "http" and interactive:
            print("Qwen: ", end="", flush=True)
            result = client.send_text(
                message, on_token=lambda fragment: print(fragment, end="", flush=True)
            )
            print()
        elif args.transport == "browser" and args.stream == "network":
            network_chunks = []

            def show_network(fragment):
                network_chunks.append(fragment)
                print(fragment, end="", flush=True)

            result = client.send_text(
                message,
                conversation=browser_conversation,
                on_token=show_network,
            )
            if not network_chunks:
                print(
                    "[No live fragments received; displaying final answer]",
                    file=sys.stderr,
                )
                print(result.text, end="", flush=True)
            print()
        elif args.transport == "browser":
            live = _QwenLiveAnswer()
            result = client.send_text(
                message, conversation=browser_conversation, on_text=live.update
            )
            live.finish(result.text)
        else:
            result = client.send_text(
                message,
                conversation=browser_conversation
                if args.transport == "browser"
                else None,
            )
            print(result.text)
        if args.transport == "browser":
            browser_conversation = result.conversation

    try:
        if args.import_auth:
            client.import_browser_auth()
            print("Авторизация Qwen сохранена локально. Сообщений не отправлено.")
            return 0
        if args.transport == "http":
            print(
                "Qwen HTTP is experimental: valid credentials may still require browser verification.",
                file=sys.stderr,
            )
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
                try:
                    send(message, interactive=True)
                except Exception as error:
                    print("Qwen SDK error: " + str(error), file=sys.stderr)
                    print("For Qwen overload: /retry. Exit: /exit", file=sys.stderr)
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
