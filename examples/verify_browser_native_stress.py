from __future__ import annotations

"""Verify PR8.0 browser-native 20-turn repeatability against canonical chat history.

Purpose: confirm that the extension stress harness produced exactly one user turn and
one final assistant marker for SDK_BRIDGE_STRESS_01..20, in order, with no missing
or duplicate markers.
Surface: research-only PR8.0 feasibility verifier.
Prerequisites: valid auth_data.json and the conversation id used by the stress run.
"""

import argparse
import json
import re
from collections import Counter
from typing import Any


STRESS_TURN_COUNT = 20
USER_PATTERN = re.compile(r"^Reply with exactly: SDK_BRIDGE_STRESS_(\d{2})$")
ASSISTANT_PATTERN = re.compile(r"^SDK_BRIDGE_STRESS_(\d{2})$")


def _marker_number(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.fullmatch(text.strip())
    if match is None:
        return None
    return int(match.group(1))


def analyze_stress_messages(messages: list[Any], *, count: int = STRESS_TURN_COUNT) -> dict[str, Any]:
    expected = list(range(1, count + 1))
    user_counts: Counter[int] = Counter()
    assistant_counts: Counter[int] = Counter()
    marker_events: list[tuple[str, int]] = []

    for message in messages:
        role = getattr(message, "role", None)
        text = getattr(message, "text", "")
        if not isinstance(text, str):
            continue
        if role == "user":
            marker = _marker_number(USER_PATTERN, text)
            if marker is not None:
                user_counts[marker] += 1
                marker_events.append(("user", marker))
        elif role == "assistant":
            marker = _marker_number(ASSISTANT_PATTERN, text)
            if marker is not None:
                assistant_counts[marker] += 1
                marker_events.append(("assistant", marker))

    expected_events = [
        event
        for marker in expected
        for event in (("user", marker), ("assistant", marker))
    ]
    missing_user = [marker for marker in expected if user_counts[marker] == 0]
    missing_assistant = [marker for marker in expected if assistant_counts[marker] == 0]
    duplicate_user = [marker for marker in expected if user_counts[marker] > 1]
    duplicate_assistant = [marker for marker in expected if assistant_counts[marker] > 1]
    unexpected_user = sorted(marker for marker in user_counts if marker not in expected)
    unexpected_assistant = sorted(marker for marker in assistant_counts if marker not in expected)
    order_ok = marker_events == expected_events

    passed = not any(
        (
            missing_user,
            missing_assistant,
            duplicate_user,
            duplicate_assistant,
            unexpected_user,
            unexpected_assistant,
        )
    ) and order_ok

    return {
        "ok": passed,
        "expected_turns": count,
        "observed_user_markers": sum(user_counts.values()),
        "observed_assistant_markers": sum(assistant_counts.values()),
        "missing_user": missing_user,
        "missing_assistant": missing_assistant,
        "duplicate_user": duplicate_user,
        "duplicate_assistant": duplicate_assistant,
        "unexpected_user": unexpected_user,
        "unexpected_assistant": unexpected_assistant,
        "order_ok": order_ok,
        "marker_event_count": len(marker_events),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the PR8.0 20-turn browser-native stress run from canonical ChatGPT history."
    )
    parser.add_argument("conversation", help="ChatGPT conversation URL or raw conversation id")
    parser.add_argument("--auth-file", default="auth_data.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    from chatgpt_web_adapter import ChatGPTWebClient

    client = ChatGPTWebClient(auth_file=args.auth_file, timeout=args.timeout)
    messages = client.get_messages(args.conversation, limit=args.limit, include_empty=False)
    report = analyze_stress_messages(messages)
    report["conversation"] = args.conversation
    report["message_count"] = len(messages)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
