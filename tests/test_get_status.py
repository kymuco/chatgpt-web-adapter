from __future__ import annotations

from typing import Any

import pytest

from webchat_adapter import ChatGPTWebClient, ConversationStatus


def _message(
    role: str,
    *,
    message_id: str = "msg-1",
    recipient: str | None = "all",
    metadata: dict[str, Any] | None = None,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "id": message_id,
        "author": {"role": role},
        "content": {"content_type": "text", "parts": [""]},
        "create_time": 1.0,
        "metadata": metadata or {},
    }
    if recipient is not None:
        message["recipient"] = recipient
    if finish_reason is not None:
        message["finish_reason"] = finish_reason
    return message


def _node(
    node_id: str,
    message: dict[str, Any] | None,
    *,
    parent: str | None = None,
    children: list[str] | None = None,
    async_status: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {"id": node_id, "parent": parent}
    if message is not None:
        node["message"] = message
    if children is not None:
        node["children"] = children
    if async_status is not None:
        node["async_status"] = async_status
    if status is not None:
        node["status"] = status
    return node


def _payload(
    message: dict[str, Any] | None,
    *,
    current_node: str | None = "node-1",
    async_status: str | None = None,
    status: str | None = None,
    mapping: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "conversation_id": "conversation-1",
        "mapping": mapping if mapping is not None else {"node-1": _node("node-1", message)},
    }
    if current_node is not None:
        payload["current_node"] = current_node
    if async_status is not None:
        payload["async_status"] = async_status
    if status is not None:
        payload["status"] = status
    return payload


def _client(payload: Any) -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: payload
    return client


def test_get_status_method_is_available() -> None:
    assert hasattr(ChatGPTWebClient, "get_status")


def test_get_status_completed_assistant_from_finish_details() -> None:
    client = _client(
        _payload(
            _message(
                "assistant",
                metadata={"finish_details": {"type": "stop"}},
            )
        )
    )

    status = client.get_status("conversation-1")

    assert isinstance(status, ConversationStatus)
    assert status.status == "completed"
    assert status.finish_reason == "stop"
    assert status.role == "assistant"
    assert status.recipient == "all"


def test_get_status_running_assistant_without_finish_details() -> None:
    client = _client(_payload(_message("assistant")))

    status = client.get_status("conversation-1")

    assert status.status == "running"


def test_get_status_running_from_payload_async_status() -> None:
    client = _client(_payload(_message("assistant"), async_status="in_progress"))

    status = client.get_status("conversation-1")

    assert status.status == "running"
    assert status.async_status == "in_progress"


def test_get_status_completed_from_payload_async_status() -> None:
    client = _client(_payload(_message("assistant"), async_status="completed"))

    status = client.get_status("conversation-1")

    assert status.status == "completed"
    assert status.async_status == "completed"


def test_get_status_user_last_message() -> None:
    client = _client(_payload(_message("user", recipient=None)))

    status = client.get_status("conversation-1")

    assert status.status == "user_last_message"
    assert status.role == "user"


def test_get_status_active_async_overrides_user_last_message() -> None:
    client = _client(_payload(_message("user", recipient=None), async_status="running"))

    status = client.get_status("conversation-1")

    assert status.status == "running"
    assert status.role == "user"


def test_get_status_tool_calling_from_assistant_recipient() -> None:
    client = _client(_payload(_message("assistant", recipient="python")))

    status = client.get_status("conversation-1")

    assert status.status == "tool_calling"
    assert status.recipient == "python"


def test_get_status_tool_running_from_tool_role() -> None:
    client = _client(_payload(_message("tool", recipient="all")))

    status = client.get_status("conversation-1")

    assert status.status == "tool_running"
    assert status.role == "tool"


def test_get_status_awaiting_tool_approval_from_metadata_signal() -> None:
    client = _client(
        _payload(
            _message(
                "assistant",
                recipient="python",
                metadata={"pending_approval": True},
            )
        )
    )

    status = client.get_status("conversation-1")

    assert status.status == "awaiting_tool_approval"
    assert status.pending_approval is True
    assert status.recipient == "python"


def test_get_status_awaiting_tool_approval_from_confirm_action_leaf() -> None:
    mapping = {
        "assistant-tool-call": _node(
            "assistant-tool-call",
            _message("assistant", message_id="target-msg", recipient="python"),
            children=["tool-approval"],
        ),
        "tool-approval": _node(
            "tool-approval",
            _message(
                "tool",
                message_id="approval-msg",
                recipient="all",
                metadata={
                    "jit_plugin_data": {
                        "from_server": {
                            "type": "confirm_action",
                            "body": {
                                "actions": [
                                    {
                                        "type": "allow",
                                        "allow": {"target_message_id": "assistant-tool-call"},
                                    }
                                ]
                            },
                        }
                    }
                },
            ),
            parent="assistant-tool-call",
            children=[],
        ),
    }
    client = _client(_payload(None, current_node="tool-approval", mapping=mapping))

    status = client.get_status("conversation-1")

    assert status.status == "awaiting_tool_approval"
    assert status.pending_approval is True
    assert status.node_id == "tool-approval"
    assert status.message_id == "approval-msg"
    assert status.role == "tool"


def test_get_status_missing_current_node_returns_unknown() -> None:
    client = _client(_payload(_message("assistant"), current_node=None))

    status = client.get_status("conversation-1")

    assert status.status == "unknown"


def test_get_status_current_node_not_in_mapping_returns_unknown() -> None:
    client = _client(_payload(_message("assistant"), current_node="missing"))

    status = client.get_status("conversation-1")

    assert status.status == "unknown"


def test_get_status_malformed_current_node_returns_unknown() -> None:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "node-1",
        "mapping": {"node-1": "not-a-node"},
    }
    client = _client(payload)

    status = client.get_status("conversation-1")

    assert status.status == "unknown"


def test_get_status_node_without_message_returns_unknown() -> None:
    client = _client(_payload(None))

    status = client.get_status("conversation-1")

    assert status.status == "unknown"


def test_get_status_non_dict_payload_returns_unknown() -> None:
    client = _client([])

    status = client.get_status("conversation-1")

    assert status.status == "unknown"


def test_get_status_fills_current_message_fields() -> None:
    client = _client(
        _payload(
            _message(
                "assistant",
                message_id="msg-1",
                recipient="all",
                metadata={"finish_details": {"type": "stop"}},
            )
        )
    )

    status = client.get_status("conversation-1")

    assert status.node_id == "node-1"
    assert status.message_id == "msg-1"
    assert status.role == "assistant"
    assert status.recipient == "all"
    assert status.finish_reason == "stop"


def test_get_status_metadata_preview_uses_selected_keys_only() -> None:
    client = _client(
        _payload(
            _message(
                "assistant",
                metadata={
                    "finish_details": {"type": "stop"},
                    "async_status": "completed",
                    "huge_payload": {"ignore": True},
                },
            )
        )
    )

    status = client.get_status("conversation-1")

    assert status.metadata_preview == {
        "async_status": "completed",
        "finish_details": {"type": "stop"},
    }


def test_get_status_reads_async_status_from_node_and_metadata() -> None:
    node_async_client = _client(
        _payload(
            _message("assistant"),
            mapping={"node-1": _node("node-1", _message("assistant"), async_status="queued")},
        )
    )
    metadata_async_client = _client(
        _payload(_message("assistant", metadata={"async_status": "streaming"}))
    )

    assert node_async_client.get_status("conversation-1").async_status == "queued"
    assert metadata_async_client.get_status("conversation-1").async_status == "streaming"


def test_get_status_reads_finish_reason_from_fallback_fields() -> None:
    metadata_client = _client(
        _payload(_message("assistant", metadata={"finish_reason": "stop"}))
    )
    message_client = _client(_payload(_message("assistant", finish_reason="stop")))

    assert metadata_client.get_status("conversation-1").finish_reason == "stop"
    assert message_client.get_status("conversation-1").finish_reason == "stop"


def test_get_status_validates_conversation_reference_before_fetching() -> None:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: pytest.fail(
        "payload should not be fetched for invalid references"
    )

    with pytest.raises(ValueError, match="conversation_id is required"):
        client.get_status("")
