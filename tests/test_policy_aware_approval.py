from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import webchat_adapter
from webchat_adapter import (
    ApprovalDeniedError,
    ApprovalPolicy,
    ChatConversation,
    ChatGPTWebClient,
    ChatMetrics,
    ChatResponse,
)
from webchat_adapter.approval_types import APPROVAL_EVENT_TYPES


def _confirm_action_payload(*, recipient: str = "python") -> dict[str, Any]:
    return {
        "conversation_id": "conversation-1",
        "mapping": {
            "target-node": {
                "message": {
                    "id": "target-msg",
                    "author": {"role": "assistant"},
                    "recipient": recipient,
                },
                "children": ["tool-node"],
            },
            "tool-node": {
                "message": {
                    "id": "tool-msg",
                    "author": {"role": "tool"},
                    "create_time": 1.0,
                    "metadata": {
                        "jit_plugin_data": {
                            "from_server": {
                                "type": "confirm_action",
                                "body": {
                                    "actions": [
                                        {
                                            "type": "allow",
                                            "allow": {
                                                "target_message_id": "target-node",
                                            },
                                        }
                                    ]
                                },
                            }
                        }
                    },
                },
                "children": [],
            },
        },
    }


def _idle_payload() -> dict[str, Any]:
    return {
        "conversation_id": "conversation-1",
        "current_node": "assistant-node",
        "mapping": {
            "assistant-node": {
                "message": {
                    "id": "assistant-msg",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"parts": ["Done"]},
                    "metadata": {"finish_details": {"type": "stop"}},
                },
                "children": [],
            }
        },
    }


def _client_with_pending_payload(payload: dict[str, Any]) -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client.auth = SimpleNamespace(turnstile_token=None)
    client._get_conversation_payload = lambda _conversation_id: payload
    client._build_headers = lambda extra=None: dict(extra or {})
    client._get_ready_requirements = lambda: ({"token": "requirements-token"}, "proof-token")
    return client


def _canonical_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("type") in APPROVAL_EVENT_TYPES]


def test_approval_denied_error_is_exported() -> None:
    assert webchat_adapter.ApprovalDeniedError is ApprovalDeniedError
    assert "ApprovalDeniedError" in webchat_adapter.__all__


def test_wait_and_approve_pending_actions_default_policy_blocks_before_prepare_or_stream() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))
    events: list[dict[str, Any]] = []
    calls: list[str] = []
    client._json_request = lambda *_args, **_kwargs: calls.append("prepare")
    client._stream_backend_payload = lambda *_args, **_kwargs: calls.append("stream")

    with pytest.raises(ApprovalDeniedError) as exc_info:
        client.wait_and_approve_pending_actions(
            ChatConversation(conversation_id="conversation-1"),
            max_rounds=1,
            settle_delay=0,
            on_event=events.append,
        )

    assert calls == []
    assert exc_info.value.approval.recipient == "python"
    assert exc_info.value.decision.allowed is False
    assert exc_info.value.decision.reason == "manual_required_for_unknown_recipient"
    assert [event["type"] for event in events] == [
        "approval_round_started",
        "approval_detected",
        "approval_denied",
    ]
    denied_event = events[-1]
    assert denied_event["recipient"] == "python"
    assert denied_event["allowed"] is False
    assert denied_event["reason"] == "manual_required_for_unknown_recipient"


def test_approve_pending_action_allowed_policy_reaches_existing_send_flow() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))
    events: list[dict[str, Any]] = []
    calls: list[str] = []

    def fake_json_request(*_args: Any, **_kwargs: Any) -> tuple[int, dict[str, str]]:
        calls.append("prepare")
        return 200, {"status": "ok", "conduit_token": "conduit-token"}

    def fake_stream(*_args: Any, **_kwargs: Any) -> tuple[str, str, str]:
        calls.append("stream")
        return "conversation-1", "message-1", "Approved"

    client._json_request = fake_json_request
    client._stream_backend_payload = fake_stream

    response = client.approve_pending_action(
        ChatConversation(conversation_id="conversation-1"),
        poll=False,
        policy=ApprovalPolicy(allowed_recipients={"python"}),
        on_event=events.append,
    )

    assert calls == ["prepare", "stream"]
    assert response.text == "Approved"
    canonical_types = [event["type"] for event in _canonical_events(events)]
    assert canonical_types == [
        "approval_detected",
        "approval_allowed",
        "approval_sent",
        "approval_completed",
    ]
    assert "approval_policy_allowed" not in [event["type"] for event in events]
    assert "pending_approval_detected" not in [event["type"] for event in events]
    allowed_event = _canonical_events(events)[1]
    assert allowed_event["allowed"] is True
    assert allowed_event["reason"] == "recipient_allowed"


def test_approve_pending_action_denied_policy_blocks_before_prepare_or_stream() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="browser"))
    events: list[dict[str, Any]] = []
    client._json_request = lambda *_args, **_kwargs: pytest.fail("prepare must not run")
    client._stream_backend_payload = lambda *_args, **_kwargs: pytest.fail("stream must not run")

    with pytest.raises(ApprovalDeniedError) as exc_info:
        client.approve_pending_action(
            ChatConversation(conversation_id="conversation-1"),
            policy=ApprovalPolicy(denied_recipients={"browser"}),
            on_event=events.append,
        )

    assert exc_info.value.decision.reason == "recipient_denied"
    assert exc_info.value.decision.manual_required is False
    assert [event["type"] for event in events] == ["approval_detected", "approval_denied"]


def test_approve_pending_action_unknown_manual_disabled_still_blocks_when_policy_is_explicit() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))
    client._json_request = lambda *_args, **_kwargs: pytest.fail("prepare must not run")
    client._stream_backend_payload = lambda *_args, **_kwargs: pytest.fail("stream must not run")

    with pytest.raises(ApprovalDeniedError) as exc_info:
        client.approve_pending_action(
            ChatConversation(conversation_id="conversation-1"),
            policy=ApprovalPolicy(require_manual_for_unknown=False),
        )

    assert exc_info.value.decision.reason == "unknown_recipient_denied"
    assert exc_info.value.decision.manual_required is False


def test_approve_pending_action_rejects_invalid_policy_before_fetching() -> None:
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: pytest.fail("should not fetch")

    with pytest.raises(TypeError, match="policy must be an ApprovalPolicy or None"):
        client.approve_pending_action(
            ChatConversation(conversation_id="conversation-1"),
            policy={"allowed_recipients": ["python"]},
        )


def test_wait_and_approve_pending_actions_passes_policy_to_approve_helper() -> None:
    policy = ApprovalPolicy(allowed_recipients={"python"})
    client = object.__new__(ChatGPTWebClient)
    client._conversation_to_dict = ChatGPTWebClient._conversation_to_dict
    client._get_conversation_payload = lambda _conversation_id: _confirm_action_payload()
    client._latest_confirm_action_leaf = ChatGPTWebClient._latest_confirm_action_leaf
    captured: list[ApprovalPolicy | None] = []

    def fake_approve(
        _conversation: ChatConversation,
        *,
        policy: ApprovalPolicy | None = None,
        **_kwargs: Any,
    ) -> ChatResponse:
        captured.append(policy)
        return ChatResponse(
            text="Done",
            conversation=ChatConversation(conversation_id="conversation-1", message_id="m1"),
            metrics=ChatMetrics(),
        )

    client.approve_pending_action = fake_approve

    response = client.wait_and_approve_pending_actions(
        ChatConversation(conversation_id="conversation-1"),
        policy=policy,
        max_rounds=1,
        settle_delay=0,
    )

    assert captured == [policy]
    assert response.text == "Done"


def test_wait_and_approve_pending_actions_propagates_policy_denial() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))

    with pytest.raises(ApprovalDeniedError):
        client.wait_and_approve_pending_actions(
            ChatConversation(conversation_id="conversation-1"),
            max_rounds=1,
            settle_delay=0,
        )


def test_send_and_auto_approve_passes_policy_to_wait_helper() -> None:
    policy = ApprovalPolicy(allowed_recipients={"python"})
    client = object.__new__(ChatGPTWebClient)
    captured: list[ApprovalPolicy | None] = []

    def fake_send(*_args: Any, **_kwargs: Any) -> ChatResponse:
        return ChatResponse(
            text="sent",
            conversation=ChatConversation(conversation_id="conversation-1", message_id="m0"),
            metrics=ChatMetrics(),
        )

    def fake_wait(
        _conversation: ChatConversation,
        *,
        policy: ApprovalPolicy | None = None,
        **_kwargs: Any,
    ) -> ChatResponse:
        captured.append(policy)
        return ChatResponse(
            text="waited",
            conversation=ChatConversation(conversation_id="conversation-1", message_id="m1"),
            metrics=ChatMetrics(),
        )

    client.send = fake_send
    client.wait_and_approve_pending_actions = fake_wait

    response = client.send_and_auto_approve(
        "prompt",
        conversation=ChatConversation(conversation_id="conversation-1"),
        policy=policy,
    )

    assert captured == [policy]
    assert response.text == "waited"


def test_policy_aware_approval_failed_event_on_prepare_failure() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))
    events: list[dict[str, Any]] = []
    client._json_request = lambda *_args, **_kwargs: (500, {"error": "prepare failed"})
    client._stream_backend_payload = lambda *_args, **_kwargs: pytest.fail("stream must not run")

    with pytest.raises(Exception):
        client.approve_pending_action(
            ChatConversation(conversation_id="conversation-1"),
            policy=ApprovalPolicy(allowed_recipients={"python"}),
            on_event=events.append,
        )

    canonical_types = [event["type"] for event in _canonical_events(events)]
    assert canonical_types == [
        "approval_detected",
        "approval_allowed",
        "approval_failed",
    ]
    failed_event = _canonical_events(events)[-1]
    assert failed_event["allowed"] is None
    assert "prepare" in failed_event["reason"]


def test_canonical_approval_events_have_stable_shape() -> None:
    client = _client_with_pending_payload(_confirm_action_payload(recipient="python"))
    events: list[dict[str, Any]] = []

    def fake_json_request(*_args: Any, **_kwargs: Any) -> tuple[int, dict[str, str]]:
        return 200, {"status": "ok", "conduit_token": "conduit-token"}

    def fake_stream(*_args: Any, **_kwargs: Any) -> tuple[str, str, str]:
        return "conversation-1", "message-1", "Approved"

    client._json_request = fake_json_request
    client._stream_backend_payload = fake_stream

    client.approve_pending_action(
        ChatConversation(conversation_id="conversation-1"),
        poll=False,
        policy=ApprovalPolicy(allowed_recipients={"python"}),
        on_event=events.append,
    )

    expected_keys = {
        "type",
        "conversation_id",
        "round_index",
        "tool_message_id",
        "target_message_id",
        "recipient",
        "allowed",
        "reason",
        "metadata_preview",
    }
    for event in _canonical_events(events):
        assert set(event) == expected_keys
        assert event["conversation_id"] == "conversation-1"
        assert event["tool_message_id"] == "tool-msg"
        assert event["target_message_id"] == "target-node"
        assert event["recipient"] == "python"
