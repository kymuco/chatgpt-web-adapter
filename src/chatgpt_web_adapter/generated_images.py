"""Read-only discovery of completed ChatGPT-generated image artifacts.

Image pointers are observation only. An image is returned only when canonical
history and the conversation-scoped file listing agree on its identity.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .exceptions import RequestError
from .generated_artifact_handoff import (
    _authenticated_headers,
    _collection,
    _files_endpoint,
    _json_get,
    _record_filename,
    _safe_file_id,
)
from .status import (
    _current_branch_nodes,
    _message_from_node,
    _message_metadata,
    _message_role,
)
from .types import ChatConversation, ConversationRef


@dataclass(frozen=True)
class GeneratedImageObservation:
    """A ready image correlated to a named, conversation-owned file.

    This is not a download token or authorization to write to disk.
    """

    conversation_id: str
    message_id: str
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int


def _image_parts(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    parts: list[tuple[str, dict[str, Any]]] = []
    for _, node in _current_branch_nodes(payload):
        message = _message_from_node(node)
        if _message_role(message) != "tool":
            continue
        if "image_gen_title" not in _message_metadata(message):
            continue
        assert message is not None
        message_id = message.get("id")
        content = message.get("content")
        if (
            not isinstance(message_id, str)
            or not message_id
            or not isinstance(content, dict)
            or content.get("content_type") != "multimodal_text"
        ):
            continue
        values = content.get("parts")
        if not isinstance(values, list):
            continue
        for part in values:
            if not isinstance(part, dict):
                continue
            if part.get("content_type") != "image_asset_pointer":
                continue
            if not isinstance(part.get("asset_pointer"), str) or not part[
                "asset_pointer"
            ]:
                continue
            mime = part.get("mime_type")
            size = part.get("size_bytes")
            width, height = part.get("width"), part.get("height")
            if (
                mime not in {"image/png", "image/jpeg", "image/webp"}
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value <= 0
                    for value in (size, width, height)
                )
            ):
                continue
            parts.append((message_id, part))
    return parts


def get_generated_images(
    self: Any,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> list[GeneratedImageObservation]:
    """List uniquely correlated ready images on the current conversation branch.

    Performs only canonical conversation and conversation-files GET requests.
    An empty list is not proof that no generation was initiated or is running.
    No Send, download, or local file operation occurs.
    """

    ref = ConversationRef.from_any(conversation)
    history = self._get_full_conversation_payload(ref.conversation_id)
    if not isinstance(history, dict):
        return []
    parts = _image_parts(history)
    if not parts:
        return []

    headers = _authenticated_headers(
        self, conversation_id=ref.conversation_id, accept="application/json"
    )
    status, payload = _json_get(
        self,
        url=_files_endpoint(ref.conversation_id),
        headers=headers,
        stage="discovery",
    )
    if not 200 <= status < 300:
        raise RequestError("generated image discovery failed", status_code=status)
    files = _collection(payload)
    if files is None:
        raise RequestError("generated image discovery shape unsupported")
    records = [item for item in files if isinstance(item, dict)]

    names = Counter(_record_filename(item) for item in records)
    ids = Counter(
        file_id
        for item in records
        if (file_id := _safe_file_id(item.get("file_id"))) is not None
    )
    matches: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for message_id, part in parts:
        eligible = [
            item
            for item in records
            if item.get("origination_message_id") == message_id
            and item.get("mime_type") == part["mime_type"]
            and item.get("file_size_bytes") == part["size_bytes"]
            and item.get("state") == "ready"
            and isinstance(item.get("image_gen_attribution"), dict)
            and bool(item["image_gen_attribution"])
            and _safe_file_id(item.get("file_id")) is not None
            and _record_filename(item) is not None
        ]
        if len(eligible) != 1:
            continue
        record = eligible[0]
        filename = _record_filename(record)
        if (
            filename is None
            or names[filename] != 1
            or ids[_safe_file_id(record.get("file_id"))] != 1
        ):
            continue
        matches.append((message_id, part, record))

    # Do not publish the same file record as separate results when equal-sized
    # image parts collide on one origin, even if the listing is otherwise unique.
    used = Counter(item["file_id"] for _, _, item in matches)
    return [
        GeneratedImageObservation(
            conversation_id=ref.conversation_id,
            message_id=message_id,
            filename=record["file_name"]
            if "file_name" in record
            else _record_filename(record),
            mime_type=part["mime_type"],
            width=part["width"],
            height=part["height"],
            size_bytes=part["size_bytes"],
        )
        for message_id, part, record in matches
        if used[record["file_id"]] == 1
    ]

