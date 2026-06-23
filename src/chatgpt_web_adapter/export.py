from __future__ import annotations

import json
from typing import Any

from .types import ChatConversation, ChatMessage, ConversationRef

EXPORT_FORMAT_ALIASES = {
    "markdown": "markdown",
    "md": "markdown",
    "jsonl": "jsonl",
    "txt": "txt",
    "text": "txt",
}
EMPTY_TEXT = "[empty]"


def _normalize_export_format(format: str) -> str:
    if not isinstance(format, str):
        raise TypeError("format must be a string")

    normalized = format.strip().lower()
    export_format = EXPORT_FORMAT_ALIASES.get(normalized)
    if export_format is None:
        supported = ", ".join(sorted(set(EXPORT_FORMAT_ALIASES.values())))
        raise ValueError(f"unsupported export format: {format!r}; supported: {supported}")
    return export_format


def _role_label(role: str | None) -> str:
    if not isinstance(role, str):
        return "Message"

    cleaned = " ".join(role.replace("_", " ").split())
    if not cleaned:
        return "Message"
    return cleaned.title()


def _display_text(message: ChatMessage) -> str:
    return message.text if message.text else EMPTY_TEXT


def _format_markdown(messages: list[ChatMessage]) -> str:
    blocks: list[str] = []
    for message in messages:
        blocks.append(f"## {_role_label(message.role)}\n\n{_display_text(message)}")
    return "\n\n".join(blocks)


def _format_txt(messages: list[ChatMessage]) -> str:
    blocks: list[str] = []
    for message in messages:
        blocks.append(f"{_role_label(message.role)}:\n{_display_text(message)}")
    return "\n\n".join(blocks)


def _format_jsonl(messages: list[ChatMessage]) -> str:
    return "\n".join(
        json.dumps(message.to_dict(), ensure_ascii=False, sort_keys=True)
        for message in messages
    )


def export_conversation(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
    *,
    format: str = "markdown",
) -> str:
    """Export the current branch of a conversation in a stable text format."""

    export_format = _normalize_export_format(format)
    messages = self.get_messages(url_or_id, limit=None, include_empty=True)

    if export_format == "markdown":
        return _format_markdown(messages)
    if export_format == "jsonl":
        return _format_jsonl(messages)
    if export_format == "txt":
        return _format_txt(messages)

    raise AssertionError("unreachable export format")
