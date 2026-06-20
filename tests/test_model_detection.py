from __future__ import annotations

from typing import Any

from webchat_adapter.model_detection import detect_model_from_conversation_payload


def _message_node(
    message_id: str,
    *,
    role: str = "assistant",
    create_time: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "message": {
            "id": message_id,
            "author": {"role": role},
            "create_time": create_time,
            "content": {"content_type": "text", "parts": ["message"]},
            "metadata": dict(metadata or {}),
        }
    }


def test_detect_model_prefers_current_node_metadata() -> None:
    payload = {
        "conversation_id": "conv-123",
        "current_node": "assistant-current",
        "mapping": {
            "assistant-old": _message_node(
                "assistant-old",
                create_time=1.0,
                metadata={"model_slug": "gpt-old"},
            ),
            "assistant-current": _message_node(
                "assistant-current",
                create_time=2.0,
                metadata={"model_slug": "gpt-current"},
            ),
        },
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-current"


def test_detect_model_falls_back_to_latest_assistant_metadata() -> None:
    payload = {
        "conversation_id": "conv-123",
        "current_node": "user-latest",
        "mapping": {
            "assistant-latest": _message_node(
                "assistant-latest",
                create_time=2.0,
                metadata={"model_slug": "gpt-assistant"},
            ),
            "user-latest": _message_node(
                "user-latest",
                role="user",
                create_time=3.0,
            ),
        },
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-assistant"


def test_detect_model_falls_back_to_latest_any_message_metadata() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {
            "user-old": _message_node(
                "user-old",
                role="user",
                create_time=1.0,
                metadata={"model_slug": "gpt-old"},
            ),
            "user-new": _message_node(
                "user-new",
                role="user",
                create_time=2.0,
                metadata={"model_slug": "gpt-user"},
            ),
        },
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-user"


def test_detect_model_falls_back_to_payload_metadata() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {},
        "metadata": {"default_model_slug": "gpt-meta"},
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-meta"


def test_detect_model_falls_back_to_top_level_fields() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {},
        "model_slug": "gpt-top",
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-top"


def test_detect_model_reads_nested_model_object() -> None:
    payload = {
        "conversation_id": "conv-123",
        "current_node": "assistant-current",
        "mapping": {
            "assistant-current": _message_node(
                "assistant-current",
                metadata={"model": {"slug": "gpt-nested"}},
            ),
        },
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-nested"


def test_detect_model_reads_nested_selected_model_object() -> None:
    payload = {
        "conversation_id": "conv-123",
        "metadata": {"selected_model": {"slug": "gpt-selected"}},
    }

    assert detect_model_from_conversation_payload(payload) == "gpt-selected"


def test_detect_model_ignores_empty_strings() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {},
        "metadata": {"model_slug": "   ", "model": ""},
    }

    assert detect_model_from_conversation_payload(payload) is None


def test_detect_model_ignores_non_string_scalar_values() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {},
        "metadata": {"model_slug": 123, "model": {"bad": "shape"}},
    }

    assert detect_model_from_conversation_payload(payload) is None


def test_detect_model_returns_none_for_unknown_payload() -> None:
    payload = {"conversation_id": "conv-123", "mapping": {}}

    assert detect_model_from_conversation_payload(payload) is None


def test_detect_model_returns_none_for_non_dict_payload() -> None:
    assert detect_model_from_conversation_payload(None) is None


def test_detect_model_does_not_recursively_guess_unrelated_slug() -> None:
    payload = {
        "conversation_id": "conv-123",
        "mapping": {},
        "metadata": {
            "tool": {"slug": "not-a-model"},
            "attachment": {"name": "also-not-a-model"},
        },
    }

    assert detect_model_from_conversation_payload(payload) is None
