"""Snapshot-aware text parsing for the opt-in browserless HTTP client."""

from __future__ import annotations

from typing import Any

from .legacy_client_core import ChatGPTWebClient as LegacyClient


def parse_event(payload: Any, state: dict[str, Any]) -> tuple[list[str], str | None]:
    tokens, title = LegacyClient._parse_event(payload, state)
    if not isinstance(payload, dict):
        return tokens, title
    value = payload.get("v")
    message = value.get("message") if isinstance(value, dict) else None
    if isinstance(message, dict):
        content = message.get("content") or {}
        visible = (
            message.get("author", {}).get("role") == "assistant"
            and message.get("recipient", "all") == "all"
            and message.get("channel") in (None, "final")
            and content.get("content_type") == "text"
        )
        state["_browserless_visible_text"] = visible
        state["_browserless_message_id"] = message.get("id")
        if not visible:
            return [], title
        text = "".join(
            part for part in content.get("parts", []) if isinstance(part, str)
        )
        previous = state.setdefault("_browserless_message_text", {}).get(
            message.get("id"), ""
        )
        state["_browserless_message_text"][message.get("id")] = text
        # A callback cannot retract previously delivered text. Canonical readback
        # remains responsible for non-prefix revisions, as in the existing API.
        return (
            [text[len(previous) :]]
            if text.startswith(previous) and text != previous
            else []
        ), title
    if state.get("_browserless_visible_text") is False:
        return [], title
    message_id = state.get("_browserless_message_id")
    if message_id and tokens:
        texts = state.setdefault("_browserless_message_text", {})
        texts[message_id] = texts.get(message_id, "") + "".join(tokens)
    return tokens, title
