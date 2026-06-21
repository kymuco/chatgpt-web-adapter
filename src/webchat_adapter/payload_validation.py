from __future__ import annotations

from typing import Any

from .exceptions import PayloadValidationError


def _required_non_empty_string(payload: dict[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise PayloadValidationError(f"{field_name} is required")
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PayloadValidationError(f"{field_name} must be a non-empty string")
    return value


def validate_payload(payload: dict[str, Any]) -> None:
    """Lightly validate a raw ChatGPT web backend payload.

    This validates only obvious top-level guardrails for the experimental raw
    payload API. It is not a complete backend schema validator and does not
    validate message content, tool payloads, media payloads, or metadata.
    """

    if not isinstance(payload, dict):
        raise PayloadValidationError("payload must be a dict")

    _required_non_empty_string(payload, "action")
    _required_non_empty_string(payload, "parent_message_id")
    _required_non_empty_string(payload, "model")

    if "messages" not in payload:
        raise PayloadValidationError("messages is required")
    messages = payload.get("messages")
    if isinstance(messages, str) or not isinstance(messages, list):
        raise PayloadValidationError("messages must be a list")
    if not messages:
        raise PayloadValidationError("messages must not be empty")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise PayloadValidationError(f"messages[{index}] must be a dict")

    if "conversation_id" in payload:
        conversation_id = payload.get("conversation_id")
        if conversation_id is not None and (
            not isinstance(conversation_id, str) or not conversation_id.strip()
        ):
            raise PayloadValidationError(
                "conversation_id must be None or a non-empty string when present"
            )
