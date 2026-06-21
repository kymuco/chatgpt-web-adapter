from __future__ import annotations

import argparse
import time
from typing import Any

from webchat_adapter import ChatGPTWebClient, RequestError


DEFAULT_PROMPT = "Reply with one short sentence and nothing else."


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}s"


def _format_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} chars/s"


def _event_line(event: dict[str, Any], *, started_at: float) -> str:
    event_type = event.get("type", "event")
    elapsed = time.perf_counter() - started_at
    parts = [f"[{elapsed:7.3f}s]", str(event_type)]

    if event_type == "requirements_ready":
        parts.append(f"latency={_format_seconds(event.get('latency'))}")
        parts.append(f"token_present={event.get('token_present')}")
    elif event_type == "stream_started":
        parts.append(str(event.get("method") or ""))
        parts.append(str(event.get("url") or ""))
    elif event_type == "first_token":
        parts.append(f"token={event.get('token')!r}")
    elif event_type == "assistant_token":
        parts.append(f"len={len(str(event.get('token') or ''))}")
    elif event_type == "stream_done":
        parts.append(f"text_length={event.get('text_length')}")
    elif event_type == "request_completed":
        parts.append(f"finish_reason={event.get('finish_reason')}")
        parts.append(f"total={_format_seconds(event.get('total'))}")
    elif event_type == "error":
        parts.append(f"stage={event.get('request_stage')}")
        parts.append(f"status={event.get('status_code')}")
        parts.append(f"endpoint={event.get('endpoint')}")

    return " ".join(part for part in parts if part)


def _print_request_error(error: RequestError) -> None:
    print("request failed")
    print("message:", str(error))
    print("status_code:", error.status_code)
    print("endpoint:", error.endpoint)
    print("request_stage:", error.request_stage)
    if error.body_preview:
        print("body_preview:", error.body_preview)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send one prompt and print ChatGPT web latency diagnostics.",
    )
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Do not print assistant tokens live.",
    )
    args = parser.parse_args()

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    started_at = time.perf_counter()
    tokens: list[str] = []

    def on_token(token: str) -> None:
        tokens.append(token)
        if not args.no_stream:
            print(token, end="", flush=True)

    def on_event(event: dict[str, Any]) -> None:
        if event.get("type") == "assistant_token":
            return
        if not args.no_stream:
            print()
        print(_event_line(event, started_at=started_at))

    try:
        response = client.send(
            args.prompt,
            model=args.model,
            on_token=on_token,
            on_event=on_event,
        )
    except RequestError as error:
        if not args.no_stream:
            print()
        _print_request_error(error)
        raise SystemExit(1) from error

    if not args.no_stream:
        print()

    metrics = response.metrics
    print("latency summary")
    print("first_token:", _format_seconds(metrics.first_token))
    print("last_token:", _format_seconds(metrics.last_token))
    print("requirements_latency:", _format_seconds(metrics.requirements_latency))
    print("stream_duration:", _format_seconds(metrics.stream_duration))
    print("total:", _format_seconds(metrics.total))
    print("chars_per_second:", _format_rate(metrics.chars_per_second))
    print("backend_status:", metrics.backend_status)
    print("tokens_seen:", len(tokens))
    print("text_length:", len(response.text))
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)


if __name__ == "__main__":
    main()
