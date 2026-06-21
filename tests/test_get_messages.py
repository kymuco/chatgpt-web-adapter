from __future__ import annotations

import pytest

from webchat_adapter import ChatGPTWebClient, ChatMessage


def _message(
    message_id: str,
    role: str,
    text: str | None,
    *,
    create_time: float = 1.0,
    recipient: str = "all",
    metadata: dict | None = None,
) -> dict:
    content: dict = {}
    if text is not None:
        content["parts"] = [text]
    return {
        "id": message_id,
        "author": {"role": role},
        "content": content,
        "create_time": create_time,
        "recipient": recipient,
        "metadata": metadata or {},
    }


def _node(node_id: str, parent: str | None, message: dict | None) -> dict:
    node = {"id": node_id, "parent": parent}
    if message is not None:
        node["message"] = message
    return node


def _payload(*, current_node: str | None, mapping: dict[str, dict]) -> dict:
    payload = {"conversation_id": "conversation-1", "mapping": mapping}
    if current_node is not None:
        payload["current_node"] = current_node
    return payload


def _client(payload: dict | object) -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: payload
    return client


def test_get_messages_method_is_available() -> None:
    assert hasattr(ChatGPTWebClient, "get_messages")


def test_get_messages_reads_current_branch_not_entire_mapping() -> None:
    payload = _payload(
        current_node="assistant-current",
        mapping={
            "root": _node("root", None, None),
            "user-1": _node(
                "user-1",
                "root",
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            ),
            "assistant-current": _node(
                "assistant-current",
                "user-1",
                _message(
                    "msg-assistant-current",
                    "assistant",
                    "Current answer",
                    create_time=2.0,
                ),
            ),
            "assistant-other-branch": _node(
                "assistant-other-branch",
                "user-1",
                _message(
                    "msg-assistant-other",
                    "assistant",
                    "Other answer",
                    create_time=3.0,
                ),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.node_id for message in messages] == [
        "user-1",
        "assistant-current",
    ]
    assert [message.text for message in messages] == ["Prompt", "Current answer"]


def test_get_messages_returns_oldest_to_newest_order() -> None:
    payload = _payload(
        current_node="assistant-2",
        mapping={
            "user-1": _node(
                "user-1",
                None,
                _message("msg-user-1", "user", "One", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "Two", create_time=2.0),
            ),
            "user-2": _node(
                "user-2",
                "assistant-1",
                _message("msg-user-2", "user", "Three", create_time=3.0),
            ),
            "assistant-2": _node(
                "assistant-2",
                "user-2",
                _message("msg-assistant-2", "assistant", "Four", create_time=4.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.node_id for message in messages] == [
        "user-1",
        "assistant-1",
        "user-2",
        "assistant-2",
    ]


def test_get_messages_limit_returns_last_n_after_filters() -> None:
    payload = _payload(
        current_node="assistant-2",
        mapping={
            "system-1": _node(
                "system-1",
                None,
                _message("msg-system-1", "system", "System", create_time=0.5),
            ),
            "user-1": _node(
                "user-1",
                "system-1",
                _message("msg-user-1", "user", "One", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "Two", create_time=2.0),
            ),
            "user-2": _node(
                "user-2",
                "assistant-1",
                _message("msg-user-2", "user", "Three", create_time=3.0),
            ),
            "assistant-2": _node(
                "assistant-2",
                "user-2",
                _message("msg-assistant-2", "assistant", "Four", create_time=4.0),
            ),
        },
    )

    messages = _client(payload).get_messages(
        "conversation-1",
        roles={"user", "assistant"},
        limit=2,
    )

    assert [message.node_id for message in messages] == ["user-2", "assistant-2"]


def test_get_messages_limit_none_returns_all_filtered_messages() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "system-1": _node(
                "system-1",
                None,
                _message("msg-system-1", "system", "System", create_time=0.5),
            ),
            "user-1": _node(
                "user-1",
                "system-1",
                _message("msg-user-1", "user", "One", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "Two", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages(
        "conversation-1",
        roles={"user", "assistant"},
        limit=None,
    )

    assert [message.node_id for message in messages] == ["user-1", "assistant-1"]


def test_get_messages_limit_zero_returns_empty_list_without_fetching() -> None:
    client = object.__new__(ChatGPTWebClient)

    def fail_fetch(_conversation_id: str) -> dict:
        raise AssertionError("payload should not be fetched")

    client._get_conversation_payload = fail_fetch

    assert client.get_messages("conversation-1", limit=0) == []


def test_get_messages_negative_limit_raises_value_error() -> None:
    with pytest.raises(ValueError, match="limit must be greater than or equal to 0"):
        _client({}).get_messages("conversation-1", limit=-1)


def test_get_messages_non_int_limit_raises_type_error() -> None:
    with pytest.raises(TypeError, match="limit must be an int or None"):
        _client({}).get_messages("conversation-1", limit=1.5)


def test_get_messages_bool_limit_raises_type_error() -> None:
    with pytest.raises(TypeError, match="limit must be an int or None"):
        _client({}).get_messages("conversation-1", limit=True)


def test_get_messages_filters_by_roles() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "user-1": _node(
                "user-1",
                None,
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "Answer", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1", roles={"user"})

    assert [message.role for message in messages] == ["user"]
    assert [message.text for message in messages] == ["Prompt"]


def test_get_messages_roles_none_returns_all_roles() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "system-1": _node(
                "system-1",
                None,
                _message("msg-system-1", "system", "System", create_time=0.5),
            ),
            "user-1": _node(
                "user-1",
                "system-1",
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "Answer", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.role for message in messages] == ["system", "user", "assistant"]


def test_get_messages_empty_roles_returns_empty_list_without_fetching() -> None:
    client = object.__new__(ChatGPTWebClient)

    def fail_fetch(_conversation_id: str) -> dict:
        raise AssertionError("payload should not be fetched")

    client._get_conversation_payload = fail_fetch

    assert client.get_messages("conversation-1", roles=set()) == []


def test_get_messages_roles_string_raises_type_error() -> None:
    with pytest.raises(TypeError, match="roles must be an iterable of strings"):
        _client({}).get_messages("conversation-1", roles="assistant")


def test_get_messages_non_string_role_raises_type_error() -> None:
    with pytest.raises(TypeError, match="roles must contain only strings"):
        _client({}).get_messages("conversation-1", roles={"assistant", 1})


def test_get_messages_include_empty_false_filters_empty_messages() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "user-1": _node(
                "user-1",
                None,
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.node_id for message in messages] == ["user-1"]


def test_get_messages_include_empty_true_keeps_empty_messages() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "user-1": _node(
                "user-1",
                None,
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            ),
            "assistant-1": _node(
                "assistant-1",
                "user-1",
                _message("msg-assistant-1", "assistant", "", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1", include_empty=True)

    assert [message.node_id for message in messages] == ["user-1", "assistant-1"]
    assert messages[-1].text == ""


def test_get_messages_skips_malformed_node_without_message() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "malformed": _node("malformed", None, None),
            "assistant-1": _node(
                "assistant-1",
                "malformed",
                _message("msg-assistant-1", "assistant", "Answer", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.node_id for message in messages] == ["assistant-1"]


def test_get_messages_missing_current_node_returns_empty_list() -> None:
    payload = _payload(
        current_node=None,
        mapping={
            "user-1": _node(
                "user-1",
                None,
                _message("msg-user-1", "user", "Prompt", create_time=1.0),
            )
        },
    )

    assert _client(payload).get_messages("conversation-1") == []


def test_get_messages_current_node_missing_in_mapping_returns_empty_list() -> None:
    payload = _payload(current_node="missing", mapping={})

    assert _client(payload).get_messages("conversation-1") == []


def test_get_messages_parent_cycle_does_not_hang() -> None:
    payload = _payload(
        current_node="node-a",
        mapping={
            "node-a": _node(
                "node-a",
                "node-b",
                _message("msg-a", "assistant", "A", create_time=1.0),
            ),
            "node-b": _node(
                "node-b",
                "node-a",
                _message("msg-b", "user", "B", create_time=2.0),
            ),
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.node_id for message in messages] == ["node-b", "node-a"]


def test_get_messages_builds_chat_message_fields() -> None:
    metadata = {
        "content_type": "text",
        "finish_details": {"type": "stop"},
        "is_complete": True,
        "model_slug": "gpt-5-5-thinking",
        "ignored": "not copied",
    }
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "assistant-1": _node(
                "assistant-1",
                None,
                _message(
                    "msg-assistant-1",
                    "assistant",
                    "Answer",
                    create_time=123.5,
                    recipient="all",
                    metadata=metadata,
                ),
            )
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert messages == [
        ChatMessage(
            node_id="assistant-1",
            message_id="msg-assistant-1",
            role="assistant",
            text="Answer",
            create_time=123.5,
            recipient="all",
            model="gpt-5-5-thinking",
            finish_reason="stop",
            metadata_preview={
                "content_type": "text",
                "finish_details": {"type": "stop"},
                "is_complete": True,
                "model_slug": "gpt-5-5-thinking",
            },
        )
    ]


def test_get_messages_reads_content_text_when_available() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "assistant-1": _node(
                "assistant-1",
                None,
                {
                    "id": "msg-assistant-1",
                    "author": {"role": "assistant"},
                    "content": {"text": "Text field"},
                    "create_time": 1.0,
                    "recipient": "all",
                    "metadata": {},
                },
            )
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.text for message in messages] == ["Text field"]


def test_get_messages_joins_string_parts_and_ignores_structured_parts_for_now() -> None:
    payload = _payload(
        current_node="assistant-1",
        mapping={
            "assistant-1": _node(
                "assistant-1",
                None,
                {
                    "id": "msg-assistant-1",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["One", {"type": "image"}, "Two"]},
                    "create_time": 1.0,
                    "recipient": "all",
                    "metadata": {},
                },
            )
        },
    )

    messages = _client(payload).get_messages("conversation-1")

    assert [message.text for message in messages] == ["One\nTwo"]


def test_get_messages_non_dict_payload_returns_empty_list() -> None:
    assert _client([]).get_messages("conversation-1") == []
