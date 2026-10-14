"""Explicit user-machine Qwen live gate. Never prints credentials."""

from __future__ import annotations

import argparse

from chatgpt_web_adapter.qwen_client import QwenClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qwen browser or direct HTTP live test (one write per turn)",
    )
    parser.add_argument("--transport", choices=("browser", "http"), required=True)
    parser.add_argument(
        "--import-browser-auth",
        action="store_true",
        help="explicitly import Qwen token/cookies from signed-in Chrome tab",
    )
    parser.add_argument("--model", default="qwen-max-latest")
    args = parser.parse_args()

    if args.import_browser_auth and args.transport != "http":
        parser.error("--import-browser-auth requires --transport http")

    client = QwenClient(transport=args.transport, model=args.model)
    if args.import_browser_auth:
        client.import_browser_auth()
        print("QWEN_AUTH_IMPORT_OK (credentials withheld)")

    marker = "QWEN_HTTP_OK" if args.transport == "http" else "QWEN_BROWSER_OK"
    first = client.send_text(
        "Ответь строго без дополнительных слов: " + marker,
    )
    print("FIRST_REPLY:", first.text)
    if marker not in first.text:
        raise RuntimeError("QWEN_FIRST_TURN_MARKER_MISMATCH")
    second = client.send_text("Какой точный маркер ты только что ответил?")
    print("SECOND_REPLY:", second.text)
    if marker not in second.text:
        raise RuntimeError("QWEN_CONTINUATION_MARKER_MISMATCH")
    if first.conversation.conversation_id != second.conversation.conversation_id:
        raise RuntimeError("QWEN_CONTINUATION_CONVERSATION_ID_CHANGED")
    print("QWEN_" + args.transport.upper() + "_LIVE_GATE_OK")


if __name__ == "__main__":
    main()
