from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_manifest import (
    EXPORT_ARTIFACT_KIND,
    EXPORT_CONTRACT,
    artifact_file_entry,
    build_artifact_manifest,
    write_artifact_manifest,
)
from .types import ChatConversation, ChatMessage, ConversationRef

EXPORT_FORMAT_ALIASES = {
    "markdown": "markdown",
    "md": "markdown",
    "jsonl": "jsonl",
    "txt": "txt",
    "text": "txt",
}
EXPORT_EXTENSIONS = {
    "markdown": "md",
    "jsonl": "jsonl",
    "txt": "txt",
}
EXPORT_MEDIA_TYPES = {
    "markdown": "text/markdown; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
}
EMPTY_TEXT = "[empty]"
_SAFE_NAME_FORBIDDEN = frozenset('<>:"/\\|?*')


@dataclass(frozen=True)
class ConversationExportArtifact:
    conversation_id: str
    index: int
    format: str
    export_path: Path
    manifest_path: Path
    message_count: int


def _normalize_export_format(format: str) -> str:
    if not isinstance(format, str):
        raise TypeError("format must be a string")

    normalized = format.strip().lower()
    export_format = EXPORT_FORMAT_ALIASES.get(normalized)
    if export_format is None:
        supported = ", ".join(sorted(set(EXPORT_FORMAT_ALIASES.values())))
        raise ValueError(f"unsupported export format: {format!r}; supported: {supported}")
    return export_format


def _normalize_export_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("export name must be a string")
    normalized = name.strip()
    if not normalized:
        raise ValueError("export name is required")
    if normalized in {".", ".."}:
        raise ValueError("export name must be a file-name component")
    if any(character in _SAFE_NAME_FORBIDDEN or ord(character) < 32 for character in normalized):
        raise ValueError("export name contains characters that are invalid in file names")
    return normalized


def _normalize_export_index(index: int | None) -> int | None:
    if index is None:
        return None
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("export index must be an int or None")
    if index <= 0:
        raise ValueError("export index must be greater than zero")
    return index


def _next_export_index(output_dir: Path, name: str) -> int:
    pattern = re.compile(rf"^{re.escape(name)}_chat_export_(\d+)\.manifest\.json$")
    latest = 0
    if output_dir.exists():
        for path in output_dir.iterdir():
            if not path.is_file():
                continue
            match = pattern.match(path.name)
            if match is not None:
                latest = max(latest, int(match.group(1)))
    return latest + 1


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


def render_conversation_export(messages: list[ChatMessage], *, format: str = "markdown") -> str:
    export_format = _normalize_export_format(format)
    if export_format == "markdown":
        return _format_markdown(messages)
    if export_format == "jsonl":
        return _format_jsonl(messages)
    if export_format == "txt":
        return _format_txt(messages)
    raise AssertionError("unreachable export format")


def export_conversation(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
    *,
    format: str = "markdown",
) -> str:
    """Serialize the normalized current conversation branch without writing files."""

    messages = self.get_messages(url_or_id, limit=None, include_empty=True)
    return render_conversation_export(list(messages), format=format)


def write_conversation_export(
    client: Any,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
    *,
    output_dir: str | Path = ".",
    name: str = "conversation",
    index: int | None = None,
    format: str = "markdown",
) -> ConversationExportArtifact:
    """Write one normalized current-branch export plus its stable manifest."""

    normalized_name = _normalize_export_name(name)
    normalized_index = _normalize_export_index(index)
    export_format = _normalize_export_format(format)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    if normalized_index is None:
        normalized_index = _next_export_index(directory, normalized_name)

    extension = EXPORT_EXTENSIONS[export_format]
    export_path = directory / f"{normalized_name}_chat_export_{normalized_index}.{extension}"
    manifest_path = directory / f"{normalized_name}_chat_export_{normalized_index}.manifest.json"

    if export_path.exists():
        raise FileExistsError(f"conversation export already exists: {export_path}")
    if manifest_path.exists():
        raise FileExistsError(f"conversation export manifest already exists: {manifest_path}")

    ref = ConversationRef.from_any(conversation)
    messages = list(client.get_messages(ref, limit=None, include_empty=True))
    export_text = render_conversation_export(messages, format=export_format)
    export_path.write_text(export_text, encoding="utf-8", newline="\n")

    manifest = build_artifact_manifest(
        artifact_kind=EXPORT_ARTIFACT_KIND,
        contract=EXPORT_CONTRACT,
        conversation_id=ref.conversation_id,
        index=normalized_index,
        format=export_format,
        files=(
            artifact_file_entry(
                export_path,
                role="export",
                media_type=EXPORT_MEDIA_TYPES[export_format],
            ),
        ),
    )
    write_artifact_manifest(manifest_path, manifest)

    return ConversationExportArtifact(
        conversation_id=ref.conversation_id,
        index=normalized_index,
        format=export_format,
        export_path=export_path,
        manifest_path=manifest_path,
        message_count=len(messages),
    )
