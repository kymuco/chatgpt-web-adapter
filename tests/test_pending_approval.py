from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

import chatgpt_web_adapter
from chatgpt_web_adapter import ChatGPTWebClient, PendingApproval


def _message(
    role: str,
    *,
    message_id: str | None = "msg-1",
    recipient: str | None = "all",
    metadata: dict[str, Any] | None = None,
    create_time: float = 1.0,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "author": {"role": role},
        "content": {"content_type": "text", "parts": [""]},
        "create_time": create_time,
        "metadata": metadata or {},
    }
    if message_id is not None:
        message["id"] = message_id
    if recipient is not None:
        message["recipient"] = recipient
    return message


def _node(
    node_id: str,
    message: dict[str, Any] | None,
    *,
    parent: str | None = None,
    children: list[str] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {"id": node_id, "parent": parent}
    if message is not None:
        node["message"] = message
    if children is not None:
        node["children"] = children
    return node


def _confirm_action_metadata(target_message_id: str | None = "target-node") -> dict[str, Any]:
    allow: dict[str, Any] = {}
    if target_message_id is not None:
        allow["target_message_id"] = target_message_id
    return {
        "jit_plugin_data": {
            "from_server": {
                "type": "confirm_action",
                "body": {
                    "actions": [
                        {
                            "type": "allow",
                            "allow": allow,
                        }
                    ]
                },
            }
        }
    }


def _payload(mapping: dict[str, dict[str, Any]], *, current_node: str = "tool-node") -> dict[str, Any]:
    return {
        "conversation_id": "conversation-1",
        "current_node": current_node,
        "mapping": mapping,
    }


def _approval_payload(
    *,
    target_node_id: str = "target-node",
    target_recipient: str | None = "python",
    tool_node_id: str = "tool-node",
    tool_message_id: str | None = "tool-msg",
    tool_children: list[str] | None = [],
    create_time: float = 1.0,
) -> dict[str, Any]:
    return _payload(
        {
            target_node_id: _node(
                target_node_id,
                _message(
                    "assistant",
                    message_id="target-msg",
                    recipient=target_recipient,
                ),
                children=[tool_node_id],
            ),
            tool_node_id: _node(
                tool_node_id,
                _message(
                    "tool",
                    message_id=tool_message_id,
                    recipient="all",
                    metadata=_confirm_action_metadata(target_node_id),
                    create_time=create_time,
                ),
                parent=target_node_id,
                children=tool_children,
            ),
        },
        current_node=tool_node_id,
    )


def _client(payload: Any) -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: payload
    return client


def test_pending_approval_normalizes_required_fields() -> None:
    approval = PendingApproval(
        tool_message_id=" tool-msg ",
        target_message_id=" target-node ",
        recipient=" python ",
    )

    assert approval.tool_message_id == "tool-msg"
    assert approval.target_message_id == "target-node"
    assert approval.recipient == "python"


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        (
            "tool_message_id",
            {"tool_message_id": "", "target_message_id": "target", "recipient": "python"},
        ),
        (
            "target_message_id",
            {"tool_message_id": "tool", "target_message_id": "", "recipient": "python"},
        ),
        (
            "recipient",
            {"tool_message_id": "tool", "target_message_id": "target", "recipient": ""},
        ),
    ],
)
def test_pending_approval_rejects_empty_required_fields(
    field: str,
    kwargs: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match=f"{field} is required"):
        PendingApproval(**kwargs)


def test_pending_approval_is_frozen() -> None:
    approval = PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )

    with pytest.raises(FrozenInstanceError):
        approval.recipient = "browser"


def test_pending_approval_to_dict() -> None:
    approval = PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )

    assert approval.to_dict() == {
        "tool_message_id": "tool-msg",
        "target_message_id": "target-node",
        "recipient": "python",
    }


def test_pending_approval_from_dict_roundtrip() -> None:
    approval = PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )

    assert PendingApproval.from_dict(approval.to_dict()) == approval


def test_pending_approval_from_dict_invalid_returns_none() -> None:
    assert PendingApproval.from_dict(None) is None
    assert PendingApproval.from_dict({}) is None
    assert PendingApproval.from_dict({"tool_message_id": "tool"}) is None


def test_pending_approval_is_exported_from_public_package() -> None:
    assert chatgpt_web_adapter.PendingApproval is PendingApproval
    assert "PendingApproval" in chatgpt_web_adapter.__all__


def test_get_pending_approval_method_is_available() -> None:
    assert hasattr(ChatGPTWebClient, "get_pending_approval")


def test_get_pending_approval_returns_none_without_approval() -> None:
    client = _client(
        _payload(
            {
                "node-1": _node(
                    "node-1",
                    _message("assistant", metadata={"finish_details": {"type": "stop"}}),
                    children=[],
                )
            },
            current_node="node-1",
        )
    )

    assert client.get_pending_approval("conversation-1") is None


def test_get_pending_approval_extracts_confirm_action_descriptor() -> None:
    client = _client(_approval_payload())

    approval = client.get_pending_approval("conversation-1")

    assert approval == PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )


def test_get_pending_approval_chooses_latest_confirm_action_leaf() -> None:
    mapping = {
        "target-old": _node(
            "target-old",
            _message("assistant", message_id="target-old-msg", recipient="python"),
            children=["tool-old"],
        ),
        "tool-old": _node(
            "tool-old",
            _message(
                "tool",
                message_id="tool-old-msg",
                metadata=_confirm_action_metadata("target-old"),
                create_time=1.0,
            ),
            parent="target-old",
            children=[],
        ),
        "target-new": _node(
            "target-new",
            _message("assistant", message_id="target-new-msg", recipient="browser"),
            children=["tool-new"],
        ),
        "tool-new": _node(
            "tool-new",
            _message(
                "tool",
                message_id="tool-new-msg",
                metadata=_confirm_action_metadata("target-new"),
                create_time=2.0,
            ),
            parent="target-new",
            children=[],
        ),
    }
    client = _client(_payload(mapping, current_node="tool-new"))

    approval = client.get_pending_approval("conversation-1")

    assert approval == PendingApproval(
        tool_message_id="tool-new-msg",
        target_message_id="target-new",
        recipient="browser",
    )


def test_get_pending_approval_ignores_leaf_from_non_current_branch() -> None:
    mapping = {
        "root": _node("root", None, children=["branch-live", "branch-stale"]),
        "branch-live": _node(
            "branch-live",
            _message("assistant", message_id="live-target-msg", recipient="python"),
            parent="root",
            children=["tool-live"],
        ),
        "tool-live": _node(
            "tool-live",
            _message(
                "tool",
                message_id="tool-live-msg",
                metadata=_confirm_action_metadata("branch-live"),
                create_time=1.0,
            ),
            parent="branch-live",
            children=[],
        ),
        "branch-stale": _node(
            "branch-stale",
            _message("assistant", message_id="stale-target-msg", recipient="browser"),
            parent="root",
            children=["tool-stale"],
        ),
        "tool-stale": _node(
            "tool-stale",
            _message(
                "tool",
                message_id="tool-stale-msg",
                metadata=_confirm_action_metadata("branch-stale"),
                create_time=2.0,
            ),
            parent="branch-stale",
            children=[],
        ),
    }
    client = _client(_payload(mapping, current_node="tool-live"))

    approval = client.get_pending_approval("conversation-1")

    assert approval == PendingApproval(
        tool_message_id="tool-live-msg",
        target_message_id="branch-live",
        recipient="python",
    )


def test_get_pending_approval_ignores_non_leaf_confirm_action() -> None:
    client = _client(_approval_payload(tool_children=["allow-node"]))

    assert client.get_pending_approval("conversation-1") is None


@pytest.mark.parametrize(
    "payload",
    [
        _approval_payload(tool_message_id=None),
        _approval_payload(target_recipient=None),
        _payload(
            {
                "target-node": _node(
                    "target-node",
                    _message("assistant", recipient="python"),
                    children=["tool-node"],
                ),
                "tool-node": _node(
                    "tool-node",
                    _message(
                        "tool",
                        message_id="tool-msg",
                        metadata=_confirm_action_metadata(None),
                    ),
                    children=[],
                ),
            }
        ),
        _payload(
            {
                "tool-node": _node(
                    "tool-node",
                    _message(
                        "tool",
                        message_id="tool-msg",
                        metadata=_confirm_action_metadata("missing-target"),
                    ),
                    children=[],
                )
            }
        ),
        _payload(
            {
                "target-node": _node(
                    "target-node",
                    _message("assistant", recipient="python"),
                    children=["tool-node"],
                ),
                "tool-node": _node(
                    "tool-node",
                    _message(
                        "tool",
                        message_id="tool-msg",
                        metadata={
                            "jit_plugin_data": {
                                "from_server": {
                                    "type": "confirm_action",
                                    "body": {"actions": [{"type": "deny"}]},
                                }
                            }
                        },
                    ),
                    children=[],
                ),
            }
        ),
    ],
)
def test_get_pending_approval_ignores_malformed_confirm_action_payloads(
    payload: dict[str, Any],
) -> None:
    client = _client(payload)

    assert client.get_pending_approval("conversation-1") is None


def test_get_status_still_detects_confirm_action_as_pending_approval() -> None:
    client = _client(_approval_payload())

    status = client.get_status("conversation-1")

    assert status.status == "awaiting_tool_approval"
    assert status.pending_approval is True


def test_get_status_ignores_pending_approval_from_non_current_branch() -> None:
    mapping = {
        "root": _node("root", None, children=["assistant-live", "assistant-stale"]),
        "assistant-live": _node(
            "assistant-live",
            _message(
                "assistant",
                message_id="live-msg",
                recipient="all",
                metadata={"finish_details": {"type": "stop"}},
            ),
            parent="root",
            children=[],
        ),
        "assistant-stale": _node(
            "assistant-stale",
            _message("assistant", message_id="stale-msg", recipient="browser"),
            parent="root",
            children=["tool-stale"],
        ),
        "tool-stale": _node(
            "tool-stale",
            _message(
                "tool",
                message_id="tool-stale-msg",
                metadata=_confirm_action_metadata("assistant-stale"),
                create_time=2.0,
            ),
            parent="assistant-stale",
            children=[],
        ),
    }
    client = _client(_payload(mapping, current_node="assistant-live"))

    status = client.get_status("conversation-1")

    assert status.status == "completed"
    assert status.pending_approval is False


def test_generic_pending_status_does_not_create_pending_approval_descriptor() -> None:
    client = _client(
        _payload(
            {
                "node-1": _node(
                    "node-1",
                    _message(
                        "assistant",
                        recipient="python",
                        metadata={"pending_approval": True},
                    ),
                    children=[],
                )
            },
            current_node="node-1",
        )
    )

    status = client.get_status("conversation-1")
    approval = client.get_pending_approval("conversation-1")

    assert status.status == "awaiting_tool_approval"
    assert status.pending_approval is True
    assert approval is None


def test_get_pending_approval_returns_none_for_non_dict_payload() -> None:
    client = _client([])

    assert client.get_pending_approval("conversation-1") is None


def test_get_pending_approval_validates_conversation_reference_before_fetching() -> None:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: pytest.fail(
        "payload should not be fetched for invalid references"
    )

    with pytest.raises(ValueError, match="conversation_id is required"):
        client.get_pending_approval("")
