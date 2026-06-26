from __future__ import annotations

"""Watch ChatGPT web request events with optional colorized terminal output.

Purpose: inspect raw SSE, websocket handoff, polling, approvals, and assistant tokens live.
Surface: stable example built on top of the SDK event callback.
Prerequisites: valid ``auth_data.json`` from an active ChatGPT web session.
"""

import argparse
import json
import os
import sys
import time
from typing import Any

from chatgpt_web_adapter import ChatGPTWebClient


ANSI_RESET = "\x1b[0m"
ANSI = {
    "dim": "\x1b[2m",
    "bold": "\x1b[1m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "magenta": "\x1b[35m",
    "cyan": "\x1b[36m",
    "gray": "\x1b[90m",
}

APPROVAL_EVENT_TYPES = {
    "approval_detected",
    "approval_allowed",
    "approval_denied",
    "approval_sent",
    "approval_completed",
    "approval_failed",
    "pending_approval_detected",
    "approval_prepare_succeeded",
    "approval_round_started",
    "approval_round_finished",
    "waiting_for_pending_approval",
}
POLL_EVENT_TYPES = {
    "conversation_poll_started",
    "conversation_poll_attempt",
    "conversation_poll_completed",
    "conversation_poll_timeout",
    "conversation_poll_error",
    "conversation_recovery_fetch_error",
}
STREAM_EVENT_TYPES = {
    "stream_started",
    "stream_completed",
    "stream_done",
    "raw_sse_event",
    "raw_sse_done",
    "raw_ws_event",
    "raw_ws_done",
    "stream_handoff",
    "stream_handoff_transport_probe",
    "stream_handoff_ws_connected",
    "stream_handoff_ws_subscribed",
    "stream_handoff_ws_failed",
    "stream_handoff_recovery_mode",
}
REQUEST_EVENT_TYPES = {
    "request_started",
    "request_payload_prepared",
    "requirements_ready",
    "request_completed",
}


def _color_enabled(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _paint(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    code = ANSI.get(color)
    if not code:
        return text
    return f"{code}{text}{ANSI_RESET}"


def _event_color(event_type: str) -> str:
    if event_type == "assistant_token":
        return "green"
    if event_type == "error":
        return "red"
    if event_type in APPROVAL_EVENT_TYPES:
        return "blue"
    if event_type in POLL_EVENT_TYPES:
        return "yellow"
    if event_type in {
        "stream_handoff",
        "stream_handoff_transport_probe",
        "stream_handoff_ws_connected",
        "stream_handoff_ws_subscribed",
        "stream_handoff_ws_failed",
        "stream_handoff_recovery_mode",
    }:
        return "magenta"
    if event_type in STREAM_EVENT_TYPES:
        return "cyan"
    if event_type in REQUEST_EVENT_TYPES:
        return "gray"
    if event_type == "first_token":
        return "green"
    return "gray"


def _format_elapsed(started_at: float) -> str:
    return f"{time.perf_counter() - started_at:8.3f}s"


def _compact_payload(event_type: str, payload: dict[str, Any]) -> Any:
    if event_type in {"raw_sse_event", "raw_ws_event"}:
        parsed = payload.get("parsed")
        if parsed is not None:
            return parsed
        return {"raw": payload.get("raw")}
    if event_type == "raw_ws_frame":
        return {"raw": payload.get("raw")}
    if event_type == "request_payload_prepared":
        return payload.get("payload")
    return payload


def _print_json_block(label: str, payload: Any, *, color: str, color_enabled: bool) -> None:
    print(_paint(label, color, enabled=color_enabled))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_summary(response: Any, *, elapsed: float, color_enabled: bool) -> None:
    print()
    _print_json_block(
        "conversation:",
        response.conversation.to_dict(),
        color="gray",
        color_enabled=color_enabled,
    )
    print()
    _print_json_block(
        "request:",
        response.request.to_dict(),
        color="gray",
        color_enabled=color_enabled,
    )
    print()
    _print_json_block(
        "metrics:",
        response.metrics.to_dict(),
        color="gray",
        color_enabled=color_enabled,
    )
    print()
    print(_paint("response_text:", "green", enabled=color_enabled))
    print(response.text)
    print()
    print(f"wall_time_seconds: {elapsed:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch raw ChatGPT web events while sending a prompt.",
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to send.")
    parser.add_argument("--conversation", help="Existing conversation URL or raw id.")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-5-5-thinking")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="ANSI color mode for terminal output.",
    )
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Print assistant token text inline as it streams.",
    )
    parser.add_argument(
        "--show-raw-frames",
        action="store_true",
        help="Print raw websocket frame blobs. Disabled by default because they are noisy.",
    )
    parser.add_argument(
        "--preserve-model",
        action="store_true",
        help="When continuing a conversation, preserve the detected model instead of forcing --model.",
    )
    args = parser.parse_args()

    if not args.prompt:
        raise SystemExit("prompt is required")

    color_enabled = _color_enabled(args.color)
    started_at = time.perf_counter()
    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)

    def on_token(token: str) -> None:
        if not args.show_tokens:
            return
        print(_paint(token, "green", enabled=color_enabled), end="", flush=True)

    def on_event(event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "event")
        if event_type == "assistant_token":
            return
        if event_type == "raw_ws_frame" and not args.show_raw_frames:
            return
        payload = {key: value for key, value in event.items() if key != "type"}
        color = _event_color(event_type)
        label = _paint(f"[{_format_elapsed(started_at)}] {event_type}", color, enabled=color_enabled)
        compact = _compact_payload(event_type, payload)
        if event_type in {"raw_sse_event", "raw_ws_event", "request_payload_prepared", "raw_ws_frame"}:
            print()
            _print_json_block(label, compact, color=color, color_enabled=color_enabled)
            return
        print()
        print(label, json.dumps(compact, ensure_ascii=False))

    if args.conversation:
        response = client.send_to_conversation(
            args.conversation,
            args.prompt,
            model=None if args.preserve_model else args.model,
            reasoning_effort=None if args.preserve_model else args.reasoning_effort,
            preserve_model=args.preserve_model,
            on_token=on_token,
            on_event=on_event,
        )
    else:
        response = client.send(
            args.prompt,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            on_token=on_token,
            on_event=on_event,
        )

    if args.show_tokens:
        print()
    _print_summary(
        response,
        elapsed=time.perf_counter() - started_at,
        color_enabled=color_enabled,
    )


if __name__ == "__main__":
    main()
