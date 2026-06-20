from __future__ import annotations

from typing import Any

from .types import AttachedConversation, ChatConversation, ConversationRef


def _metadata_model(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("model_slug", "model", "default_model_slug", "selected_model"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _message_id(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None
    value = message.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _finish_reason(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return None
    finish_details = metadata.get("finish_details")
    if not isinstance(finish_details, dict):
        return None
    reason = finish_details.get("type")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def _attached_conversation_message(client: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    current_message = client._current_message_from_conversation(payload)
    if isinstance(current_message, dict):
        return current_message

    assistant_message, _text = client._latest_assistant_from_conversation(payload)
    if isinstance(assistant_message, dict):
        return assistant_message

    message, _text = client._latest_message_any_from_conversation(payload)
    return message if isinstance(message, dict) else None


def _detect_model_from_conversation_payload(client: Any, payload: dict[str, Any]) -> str | None:
    current_message = client._current_message_from_conversation(payload)
    if isinstance(current_message, dict):
        model = _metadata_model(current_message.get("metadata"))
        if model:
            return model

    assistant_message, _text = client._latest_assistant_from_conversation(payload)
    if isinstance(assistant_message, dict):
        model = _metadata_model(assistant_message.get("metadata"))
        if model:
            return model

    model = _metadata_model(payload.get("metadata"))
    if model:
        return model

    for key in ("model_slug", "model", "default_model_slug", "selected_model"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def attach_conversation(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> AttachedConversation:
    """Attach to an existing chatgpt.com conversation by URL or id."""

    ref = ConversationRef.from_any(url_or_id)
    payload = self._get_conversation_payload(ref.conversation_id)
    selected_message = _attached_conversation_message(self, payload)
    message_id = _message_id(selected_message)

    conversation = ChatConversation(
        conversation_id=ref.conversation_id,
        message_id=message_id,
        parent_message_id=message_id,
        finish_reason=_finish_reason(selected_message),
        is_thinking=False,
    )
    return AttachedConversation.from_payload(
        payload,
        conversation=conversation,
        detected_model=_detect_model_from_conversation_payload(self, payload),
    )
