from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .types import ChatConversation, ChatMessage, ConversationRef

METADATA_PREVIEW_KEYS = (
    "content_type",
    "finish_details",
    "is_complete",
    "model_slug",
    "model",
    "default_model_slug",
    "selected_model",
)
MODEL_KEYS = (
    "model_slug",
    "model",
    "default_model_slug",
    "selected_model",
)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _conversation_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload.get("mapping")
    return mapping if isinstance(mapping, dict) else {}


def _current_branch_nodes(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    mapping = _conversation_mapping(payload)
    node_id = _optional_str(payload.get("current_node"))
    branch: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    while node_id:
        if node_id in seen:
            break
        seen.add(node_id)

        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break

        branch.append((node_id, node))
        node_id = _optional_str(node.get("parent"))

    branch.reverse()
    return branch


def _message_from_node(node: dict[str, Any]) -> dict[str, Any] | None:
    message = node.get("message")
    return message if isinstance(message, dict) else None


def _message_role(message: dict[str, Any]) -> str | None:
    author = message.get("author")
    if not isinstance(author, dict):
        return None
    return _optional_str(author.get("role"))


def _message_metadata(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _message_model(message: dict[str, Any]) -> str | None:
    metadata = _message_metadata(message)
    for key in MODEL_KEYS:
        value = _optional_str(metadata.get(key))
        if value:
            return value
    return None


def _message_finish_reason(message: dict[str, Any]) -> str | None:
    metadata = _message_metadata(message)
    finish_details = metadata.get("finish_details")
    if not isinstance(finish_details, dict):
        return None
    return _optional_str(finish_details.get("type"))


def _message_metadata_preview(message: dict[str, Any]) -> dict[str, Any]:
    metadata = _message_metadata(message)
    return {key: metadata[key] for key in METADATA_PREVIEW_KEYS if key in metadata}


def _basic_message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return ""

    text = content.get("text")
    if isinstance(text, str):
        return text

    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""

    return "\n".join(part for part in parts if isinstance(part, str) and part)


def _chat_message_from_node(node_id: str, node: dict[str, Any]) -> ChatMessage | None:
    message = _message_from_node(node)
    if message is None:
        return None

    return ChatMessage(
        node_id=node_id,
        message_id=message.get("id"),
        role=_message_role(message),
        text=_basic_message_text(message),
        create_time=message.get("create_time"),
        recipient=message.get("recipient"),
        model=_message_model(message),
        finish_reason=_message_finish_reason(message),
        metadata_preview=_message_metadata_preview(message),
    )


def _normalize_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an int or None")
    if limit < 0:
        raise ValueError("limit must be greater than or equal to 0")
    return limit


def _normalize_roles(roles: Iterable[str] | None) -> set[str] | None:
    if roles is None:
        return None
    if isinstance(roles, str):
        raise TypeError("roles must be an iterable of strings, not a string")

    normalized: set[str] = set()
    for role in roles:
        if not isinstance(role, str):
            raise TypeError("roles must contain only strings")
        value = role.strip()
        if value:
            normalized.add(value)
    return normalized


def _message_matches_roles(message: ChatMessage, roles: set[str] | None) -> bool:
    return roles is None or message.role in roles


def get_messages(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
    *,
    limit: int | None = None,
    roles: Iterable[str] | None = None,
    include_empty: bool = False,
) -> list[ChatMessage]:
    """Read messages from the current branch of an existing conversation."""

    normalized_limit = _normalize_limit(limit)
    normalized_roles = _normalize_roles(roles)
    ref = ConversationRef.from_any(url_or_id)

    if normalized_limit == 0 or normalized_roles == set():
        return []

    payload = self._get_conversation_payload(ref.conversation_id)
    if not isinstance(payload, dict):
        return []

    messages: list[ChatMessage] = []
    for node_id, node in _current_branch_nodes(payload):
        message = _chat_message_from_node(node_id, node)
        if message is None:
            continue
        if not _message_matches_roles(message, normalized_roles):
            continue
        if not include_empty and not message.text:
            continue
        messages.append(message)

    if normalized_limit is not None:
        return messages[-normalized_limit:]
    return messages
