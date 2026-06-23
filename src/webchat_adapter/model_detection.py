from __future__ import annotations

from typing import Any

MODEL_KEYS = (
    "model_slug",
    "model",
    "default_model_slug",
    "selected_model",
)
MODEL_CONTAINER_KEYS = (
    "model",
    "selected_model",
    "default_model",
)
NESTED_MODEL_KEYS = (
    "slug",
    "name",
    "id",
)


def _clean_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _model_from_mapping(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    for key in MODEL_KEYS:
        model = _clean_model(value.get(key))
        if model:
            return model

    for key in MODEL_CONTAINER_KEYS:
        container = value.get(key)
        if not isinstance(container, dict):
            continue
        for nested_key in NESTED_MODEL_KEYS:
            model = _clean_model(container.get(nested_key))
            if model:
                return model

    return None


def _conversation_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload.get("mapping")
    return mapping if isinstance(mapping, dict) else {}


def _message_from_node(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    message = node.get("message")
    return message if isinstance(message, dict) else None


def _current_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    current_node = payload.get("current_node")
    if not isinstance(current_node, str) or not current_node.strip():
        return None
    return _message_from_node(_conversation_mapping(payload).get(current_node))


def _current_branch_messages(
    payload: dict[str, Any],
    *,
    role: str | None = None,
) -> list[dict[str, Any]]:
    mapping = _conversation_mapping(payload)
    current_node = payload.get("current_node")
    if not isinstance(current_node, str) or not current_node.strip():
        return []

    messages: list[dict[str, Any]] = []
    seen: set[str] = set()
    node_id = current_node
    while isinstance(node_id, str) and node_id.strip():
        if node_id in seen:
            break
        seen.add(node_id)

        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break

        message = _message_from_node(node)
        if isinstance(message, dict):
            if role is None:
                messages.append(message)
            else:
                author = message.get("author")
                if isinstance(author, dict) and author.get("role") == role:
                    messages.append(message)

        parent = node.get("parent")
        node_id = parent if isinstance(parent, str) else ""

    messages.reverse()
    return messages


def _latest_message(
    messages: list[dict[str, Any]],
    *,
    role: str | None = None,
) -> dict[str, Any] | None:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for message in messages:
        if role is not None:
            author = message.get("author")
            if not isinstance(author, dict) or author.get("role") != role:
                continue

        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id.strip():
            continue

        create_time = message.get("create_time")
        try:
            score = float(create_time or 0)
        except (TypeError, ValueError):
            score = 0.0
        candidates.append((score, message))

    if not candidates:
        return None
    _score, message = max(candidates, key=lambda item: item[0])
    return message


def _all_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for node in _conversation_mapping(payload).values():
        message = _message_from_node(node)
        if isinstance(message, dict):
            messages.append(message)
    return messages


def _model_from_message(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None
    return _model_from_mapping(message.get("metadata"))


def detect_model_from_conversation_payload(payload: Any) -> str | None:
    """Best-effort model extraction from a chatgpt.com conversation payload.

    The ChatGPT web conversation payload is not a stable public schema. This
    helper intentionally detects only known model-like fields from known payload
    locations and returns None instead of guessing when the model cannot be
    found.
    """

    if not isinstance(payload, dict):
        return None

    branch_messages = _current_branch_messages(payload)
    for message in (
        _current_message(payload),
        _latest_message(branch_messages, role="assistant"),
        _latest_message(branch_messages),
        _latest_message(_all_messages(payload), role="assistant"),
        _latest_message(_all_messages(payload)),
    ):
        model = _model_from_message(message)
        if model:
            return model

    model = _model_from_mapping(payload.get("metadata"))
    if model:
        return model

    return _model_from_mapping(payload)
