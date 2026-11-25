"""Revision-aware text parsing for Direct HTTP.

Token callbacks are provisional and append-only. The final response uses the
assembled message state, not the concatenation of already emitted tokens.
"""

from __future__ import annotations

from typing import Any

from .legacy_client_core import ChatGPTWebClient as LegacyClient

_TEXT_PATH = "/message/content/parts/0"


def _publish(state: dict[str, Any], message_id: str | None) -> list[str]:
    parts = state["_browserless_parts"]
    texts = state.setdefault("_browserless_message_text", {})
    text = "".join(parts[message_id])
    texts[message_id] = text
    state["_browserless_final_text"] = "".join(texts.values())
    emitted = state.setdefault("_browserless_emitted_text", {})
    previous = emitted.get(message_id, "")
    # Never emit a replacement as an additional suffix. A caller that needs
    # revision-safe display must consume the final response instead.
    if text.startswith(previous) and text != previous:
        emitted[message_id] = text
        return [text[len(previous) :]]
    return []


def _apply_text_patch(
    state: dict[str, Any], message_id: str | None, patch: dict[str, Any]
) -> list[str]:
    value = patch.get("v")
    operation = patch.get("o")
    parts = state.setdefault("_browserless_parts", {}).setdefault(message_id, [""])
    if not parts:
        parts.append("")
    if operation == "replace" and isinstance(value, str):
        parts[0] = value
    elif operation in (None, "append") and isinstance(value, str):
        parts[0] += value
    else:
        # Unknown text operations are not append operations. Do not fabricate
        # text. A later full snapshot or canonical read can repair this state.
        return []
    return _publish(state, message_id)


def parse_event(payload: Any, state: dict[str, Any]) -> tuple[list[str], str | None]:
    legacy_tokens, title = LegacyClient._parse_event(payload, state)
    if not isinstance(payload, dict):
        return legacy_tokens, title
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
        message_id = message.get("id")
        state["_browserless_message_id"] = message_id
        if not visible:
            return [], title
        parts = state.setdefault("_browserless_parts", {})
        # Some streams emit text before the first identifiable snapshot. Bind
        # that provisional prefix to the first visible message, not a second one.
        if message_id is not None and set(parts) == {None}:
            for key in (
                "_browserless_parts",
                "_browserless_message_text",
                "_browserless_emitted_text",
            ):
                values = state.setdefault(key, {})
                if None in values:
                    values[message_id] = values.pop(None)
        parts[message_id] = [
            part for part in content.get("parts", []) if isinstance(part, str)
        ]
        return _publish(state, message_id), title
    if (
        state.get("_browserless_visible_text") is False
        or state.get("recipient", "all") != "all"
    ):
        return [], title
    message_id = state.get("_browserless_message_id")
    if isinstance(value, str) and payload.get("p") in (None, _TEXT_PATH):
        return _apply_text_patch(state, message_id, payload), title
    if isinstance(value, list):
        tokens = []
        for patch in value:
            if isinstance(patch, dict) and patch.get("p") == _TEXT_PATH:
                tokens.extend(_apply_text_patch(state, message_id, patch))
        return tokens, title
    return legacy_tokens, title
