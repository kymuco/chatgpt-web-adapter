from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import ChatConversation, ChatMessage, ConversationRef

_CONTEXT_SEPARATOR = "\n\n---\n\n"
_SAFE_NAME_FORBIDDEN = frozenset('<>:"/\\|?*')


@dataclass(frozen=True)
class ConversationSnapshot:
    conversation_id: str
    index: int
    context_path: Path
    raw_payload_path: Path | None
    message_count: int


def _normalize_snapshot_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("snapshot name must be a string")
    normalized = name.strip()
    if not normalized:
        raise ValueError("snapshot name is required")
    if normalized in {".", ".."}:
        raise ValueError("snapshot name must be a file-name component")
    if any(character in _SAFE_NAME_FORBIDDEN or ord(character) < 32 for character in normalized):
        raise ValueError("snapshot name contains characters that are invalid in file names")
    return normalized


def _normalize_snapshot_index(index: int | None) -> int | None:
    if index is None:
        return None
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("snapshot index must be an int or None")
    if index <= 0:
        raise ValueError("snapshot index must be greater than zero")
    return index


def _next_snapshot_index(output_dir: Path, name: str) -> int:
    pattern = re.compile(rf"^{re.escape(name)}_chat_context_(\d+)\.md$")
    latest = 0
    if output_dir.exists():
        for path in output_dir.iterdir():
            if not path.is_file():
                continue
            match = pattern.match(path.name)
            if match is not None:
                latest = max(latest, int(match.group(1)))
    return latest + 1


def _context_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    selected: list[ChatMessage] = []
    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue
        if message.role == "assistant" and message.recipient not in (None, "all"):
            continue
        text = message.text.strip()
        if not text:
            continue
        selected.append(
            ChatMessage(
                node_id=message.node_id,
                message_id=message.message_id,
                role=message.role,
                text=text,
                create_time=message.create_time,
                recipient=message.recipient,
                model=message.model,
                finish_reason=message.finish_reason,
                metadata_preview=message.metadata_preview,
            )
        )
    return selected


def render_snapshot_context(messages: list[ChatMessage]) -> str:
    blocks = [f"## {(message.role or 'message').upper()}\n\n{message.text}" for message in messages]
    if not blocks:
        return ""
    return _CONTEXT_SEPARATOR.join(blocks) + "\n"


def snapshot_conversation(
    client: Any,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
    *,
    output_dir: str | Path = ".",
    name: str = "conversation",
    index: int | None = None,
    include_raw_payload: bool = True,
) -> ConversationSnapshot:
    """Write a deterministic user/assistant context snapshot of one conversation.

    The context contains only current-branch user messages and assistant messages
    addressed to the user (recipient absent or ``all``). Internal assistant-to-tool
    traffic is deliberately excluded. A raw conversation payload can be written as
    a forensic backup alongside the clean context.
    """

    normalized_name = _normalize_snapshot_name(name)
    normalized_index = _normalize_snapshot_index(index)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    if normalized_index is None:
        normalized_index = _next_snapshot_index(directory, normalized_name)

    context_path = directory / f"{normalized_name}_chat_context_{normalized_index}.md"
    raw_payload_path = (
        directory / f"{normalized_name}_chat_payload_{normalized_index}.json"
        if include_raw_payload
        else None
    )

    if context_path.exists():
        raise FileExistsError(f"snapshot context already exists: {context_path}")
    if raw_payload_path is not None and raw_payload_path.exists():
        raise FileExistsError(f"snapshot raw payload already exists: {raw_payload_path}")

    messages = client.get_messages(
        conversation,
        limit=None,
        roles=("user", "assistant"),
        include_empty=False,
    )
    selected = _context_messages(list(messages))
    context_text = render_snapshot_context(selected)

    raw_payload: Any | None = None
    if raw_payload_path is not None:
        ref = ConversationRef.from_any(conversation)
        raw_payload = client._get_conversation_payload(ref.conversation_id)
        raw_text = json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n"
    else:
        raw_text = None

    context_path.write_text(context_text, encoding="utf-8")
    if raw_payload_path is not None and raw_text is not None:
        raw_payload_path.write_text(raw_text, encoding="utf-8")

    ref = ConversationRef.from_any(conversation)
    return ConversationSnapshot(
        conversation_id=ref.conversation_id,
        index=normalized_index,
        context_path=context_path,
        raw_payload_path=raw_payload_path,
        message_count=len(selected),
    )
