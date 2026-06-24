from __future__ import annotations

from typing import Any

import chatgpt_web_adapter as adapter


def _oauth_required_payload() -> dict[str, Any]:
    return {
        "conversation_id": "conv-123",
        "current_node": "tool-oauth",
        "mapping": {
            "user-1": {
                "parent": None,
                "children": ["assistant-tool-call"],
                "message": {
                    "id": "user-1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["check my latest email"]},
                },
            },
            "assistant-tool-call": {
                "parent": "user-1",
                "children": ["tool-oauth"],
                "message": {
                    "id": "assistant-tool-call",
                    "author": {"role": "assistant"},
                    "recipient": "api_tool.call_tool",
                    "content": {"content_type": "code", "text": "{}"},
                },
            },
            "tool-oauth": {
                "parent": "assistant-tool-call",
                "children": [],
                "message": {
                    "id": "tool-oauth",
                    "author": {"role": "tool", "name": "api_tool.call_tool"},
                    "recipient": "assistant",
                    "create_time": 1782289694.5,
                    "content": {
                        "content_type": "text",
                        "parts": [
                            "The user has not logged into this tool. Eliciting user login."
                        ],
                    },
                    "metadata": {
                        "jit_plugin_data": {
                            "from_server": {
                                "type": "oauth_required",
                                "body": {
                                    "actions": [
                                        {
                                            "type": "oauth_redirect",
                                            "oauth_redirect": {
                                                "connector_id": "connector-gmail",
                                                "domain": "call_tool",
                                                "gizmo_action_id": "call_tool",
                                                "gizmo_id": "FAKE_CONNECTOR_GIZMO",
                                                "target_message_id": "assistant-tool-call",
                                            },
                                        },
                                        {
                                            "type": "deny",
                                            "name": "deny",
                                            "style": "secondary",
                                            "deny": {
                                                "target_message_id": "assistant-tool-call"
                                            },
                                        },
                                    ],
                                    "auth_reason": "missing_link",
                                    "connector_id": "connector-gmail",
                                    "domain": "call_tool",
                                    "is_consequential": True,
                                    "is_read_only": None,
                                    "params": {
                                        "args": {"max_results": 1, "query": ""},
                                        "path": "/connector-gmail/search_emails",
                                    },
                                },
                            }
                        }
                    },
                },
            },
        },
    }


def test_find_required_action_detects_oauth_required_connector_card() -> None:
    action = adapter.find_required_action(_oauth_required_payload())

    assert action is not None
    assert action.type == "oauth_required"
    assert action.tool_message_id == "tool-oauth"
    assert action.reason == "missing_link"
    assert action.connector_id == "connector-gmail"
    assert action.domain == "call_tool"
    assert action.path == "/connector-gmail/search_emails"
    assert action.target_message_id == "assistant-tool-call"
    assert action.actions == ("oauth_redirect", "deny")
    assert action.is_consequential is True
    assert action.is_read_only is None


def test_required_action_roundtrips_dict() -> None:
    action = adapter.find_required_action(_oauth_required_payload())
    assert action is not None

    restored = adapter.RequiredAction.from_dict(action.to_dict())

    assert restored == action


def test_find_required_action_ignores_confirm_action_approvals() -> None:
    payload = _oauth_required_payload()
    tool_message = payload["mapping"]["tool-oauth"]["message"]
    tool_message["metadata"]["jit_plugin_data"]["from_server"] = {
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

    assert adapter.find_required_action(payload) is None


def test_client_get_required_action_fetches_conversation_payload(monkeypatch) -> None:
    client = object.__new__(adapter.ChatGPTWebClient)
    seen: list[str] = []

    def fake_get_conversation_payload(conversation_id: str) -> dict[str, Any]:
        seen.append(conversation_id)
        return _oauth_required_payload()

    monkeypatch.setattr(client, "_get_conversation_payload", fake_get_conversation_payload)

    action = client.get_required_action("https://chatgpt.com/c/conv-123")

    assert seen == ["conv-123"]
    assert action is not None
    assert action.type == "oauth_required"
