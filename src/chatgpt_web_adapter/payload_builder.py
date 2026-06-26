from __future__ import annotations

import copy
import time
import uuid
from typing import Any

from .client import DEFAULT_MODEL, DEFAULT_THINKING_MODEL, MODEL_ALIASES
from .types import ChatConversation


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def _normalize_model(model: str | None, reasoning_effort: str | None) -> str:
    if isinstance(model, str):
        model_name = _required_str(model, "model")
        return MODEL_ALIASES.get(model_name.lower(), MODEL_ALIASES.get(model_name, model_name))
    normalized_effort = reasoning_effort.strip().lower() if isinstance(reasoning_effort, str) else None
    if normalized_effort in {"medium", "high", "standard", "extended"}:
        return DEFAULT_THINKING_MODEL
    return DEFAULT_MODEL


def _normalize_reasoning_effort(reasoning_effort: str | None) -> str | None:
    normalized = reasoning_effort.strip().lower() if isinstance(reasoning_effort, str) else None
    if normalized == "medium":
        normalized = "standard"
    elif normalized == "high":
        normalized = "extended"
    elif normalized in {"", "off", "none", "-", "instant"}:
        normalized = None
    if normalized not in {None, "standard", "extended"}:
        raise ValueError(
            "reasoning_effort must be one of: instant, medium, high, standard, extended, off/none/-"
        )
    return normalized


def _message_metadata(metadata: dict[str, Any] | None, *, system_hints: list[str] | None = None) -> dict[str, Any]:
    if metadata is not None and not isinstance(metadata, dict):
        raise TypeError("metadata must be a dict or None")

    result: dict[str, Any] = {
        "serialization_metadata": {"custom_symbol_offsets": []},
    }
    if metadata:
        copied = copy.deepcopy(metadata)
        serialization_metadata = copied.pop("serialization_metadata", None)
        result.update(copied)
        if serialization_metadata is not None:
            if not isinstance(serialization_metadata, dict):
                raise TypeError("metadata.serialization_metadata must be a dict")
            result["serialization_metadata"].update(copy.deepcopy(serialization_metadata))
    if system_hints:
        result["system_hints"] = list(system_hints)
    return result


def _conversation_to_dict(
    conversation: ChatConversation | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(conversation, ChatConversation):
        return conversation.to_dict()
    if isinstance(conversation, dict):
        return copy.deepcopy(conversation)
    return None


def _base_payload(
    *,
    prompt: str,
    model: str | None,
    parent_message_id: str,
    system: str | None = None,
    web_search: bool = False,
    temporary: bool = False,
    reasoning_effort: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    normalized_effort = _normalize_reasoning_effort(reasoning_effort)
    system_hints = ["search"] if web_search else None
    messages: list[dict[str, Any]] = []
    if system is not None and system.strip():
        messages.append(PayloadBuilder.text_message(system.strip(), role="system"))
    messages.append(
        PayloadBuilder.text_message(
            prompt,
            role="user",
            metadata={"system_hints": system_hints} if system_hints else None,
        )
    )

    payload: dict[str, Any] = {
        "action": "next",
        "parent_message_id": parent_message_id,
        "model": _normalize_model(model, reasoning_effort),
        "conversation_mode": {"kind": "primary_assistant"},
        "enable_message_followups": False,
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "messages": messages,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if temporary:
        payload["history_and_training_disabled"] = True
    if system_hints:
        payload["system_hints"] = system_hints
    if normalized_effort is not None:
        payload["thinking_effort"] = normalized_effort
    return payload


class PayloadBuilder:
    """Experimental helpers for constructing ChatGPT web backend payload dicts."""

    @staticmethod
    def text_message(
        text: Any,
        *,
        role: str = "user",
        message_id: str | None = None,
        create_time: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role_name = _required_str(role, "role")
        message_id_value = _optional_str(message_id) or str(uuid.uuid4())
        create_time_value = float(time.time() if create_time is None else create_time)
        return {
            "id": message_id_value,
            "author": {"role": role_name},
            "content": {
                "content_type": "text",
                "parts": ["" if text is None else str(text)],
            },
            "metadata": _message_metadata(metadata),
            "create_time": create_time_value,
        }

    @staticmethod
    def new_chat(
        prompt: Any,
        *,
        model: str | None = None,
        system: str | None = None,
        web_search: bool = False,
        temporary: bool = False,
        reasoning_effort: str | None = None,
        parent_message_id: str | None = None,
    ) -> dict[str, Any]:
        parent = _optional_str(parent_message_id) or str(uuid.uuid4())
        return _base_payload(
            prompt="" if prompt is None else str(prompt),
            model=model,
            parent_message_id=parent,
            system=system,
            web_search=web_search,
            temporary=temporary,
            reasoning_effort=reasoning_effort,
        )

    @staticmethod
    def continue_chat(
        prompt: Any,
        *,
        conversation: ChatConversation | dict[str, Any] | None = None,
        conversation_id: str | None = None,
        parent_message_id: str | None = None,
        model: str | None = None,
        web_search: bool = False,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        conversation_dict = _conversation_to_dict(conversation)
        resolved_conversation_id = _optional_str(conversation_id)
        resolved_parent_message_id = _optional_str(parent_message_id)
        if isinstance(conversation_dict, dict):
            resolved_conversation_id = resolved_conversation_id or _optional_str(
                conversation_dict.get("conversation_id")
            )
            resolved_parent_message_id = (
                resolved_parent_message_id
                or _optional_str(conversation_dict.get("parent_message_id"))
                or _optional_str(conversation_dict.get("message_id"))
            )

        if not resolved_conversation_id:
            raise ValueError("conversation_id is required")
        if not resolved_parent_message_id:
            raise ValueError("parent_message_id is required")

        return _base_payload(
            prompt="" if prompt is None else str(prompt),
            model=model,
            parent_message_id=resolved_parent_message_id,
            web_search=web_search,
            reasoning_effort=reasoning_effort,
            conversation_id=resolved_conversation_id,
        )
