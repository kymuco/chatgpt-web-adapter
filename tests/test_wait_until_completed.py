from __future__ import annotations

from typing import Any

import pytest

import webchat_adapter
import webchat_adapter.wait as wait_module
from webchat_adapter import (
    ChatGPTWebClient,
    ChatMessage,
    ConversationRef,
    ConversationStatus,
    ConversationTimeoutError,
    PendingApproval,
    WaitResult,
)
from webchat_adapter.wait import wait_until_completed


class FakeWaitClient:
    wait_until_completed = wait_until_completed

    def __init__(
        self,
        statuses: list[ConversationStatus],
        *,
        messages: list[ChatMessage] | None = None,
        approval: PendingApproval | None = None,
    ) -> None:
        self.statuses = list(statuses)
        self.messages = messages or []
        self.approval = approval
        self.status_refs: list[ConversationRef] = []
        self.message_calls: list[tuple[ConversationRef, int | None, set[str] | None, bool]] = []
        self.approval_refs: list[ConversationRef] = []

    def get_status(self, ref: ConversationRef) -> ConversationStatus:
        self.status_refs.append(ref)
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def get_messages(
        self,
        ref: ConversationRef,
        *,
        limit: int | None,
        roles: set[str] | None,
        include_empty: bool,
    ) -> list[ChatMessage]:
        self.message_calls.append((ref, limit, roles, include_empty))
        return self.messages

    def get_pending_approval(self, ref: ConversationRef) -> PendingApproval | None:
        self.approval_refs.append(ref)
        return self.approval


def test_wait_until_completed_method_is_available() -> None:
    assert hasattr(ChatGPTWebClient, "wait_until_completed")


def test_wait_result_to_dict() -> None:
    result = WaitResult(
        status=ConversationStatus(status="completed"),
        message=ChatMessage(role="assistant", text="Done"),
        elapsed=1.5,
        polls=2,
    )

    assert result.to_dict() == {
        "status": {
            "status": "completed",
            "node_id": None,
            "message_id": None,
            "role": None,
            "recipient": None,
            "async_status": None,
            "finish_reason": None,
            "pending_approval": False,
            "metadata_preview": {},
        },
        "message": {
            "node_id": None,
            "message_id": None,
            "role": "assistant",
            "text": "Done",
            "create_time": None,
            "recipient": None,
            "model": None,
            "finish_reason": None,
            "metadata_preview": {},
        },
        "approval": None,
        "elapsed": 1.5,
        "polls": 2,
    }


def test_wait_result_from_dict_roundtrip() -> None:
    result = WaitResult(
        status=ConversationStatus(status="awaiting_tool_approval", pending_approval=True),
        approval=PendingApproval(
            tool_message_id="tool-msg",
            target_message_id="target-node",
            recipient="python",
        ),
        elapsed=2.5,
        polls=3,
    )

    assert WaitResult.from_dict(result.to_dict()) == result


def test_wait_result_validates_nested_types() -> None:
    with pytest.raises(TypeError, match="status must be a ConversationStatus"):
        WaitResult(status="completed")
    with pytest.raises(TypeError, match="message must be a ChatMessage or None"):
        WaitResult(status=ConversationStatus(), message="not-a-message")
    with pytest.raises(TypeError, match="approval must be a PendingApproval or None"):
        WaitResult(status=ConversationStatus(), approval="not-an-approval")


def test_wait_result_is_exported_from_public_package() -> None:
    assert webchat_adapter.WaitResult is WaitResult
    assert "WaitResult" in webchat_adapter.__all__


def test_conversation_timeout_error_is_exported_from_public_package() -> None:
    assert webchat_adapter.ConversationTimeoutError is ConversationTimeoutError
    assert "ConversationTimeoutError" in webchat_adapter.__all__


def test_wait_until_completed_returns_latest_assistant_message_on_completed() -> None:
    message = ChatMessage(role="assistant", text="Done")
    client = FakeWaitClient(
        [ConversationStatus(status="completed")],
        messages=[message],
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "completed"
    assert result.message == message
    assert result.approval is None
    assert result.polls == 1
    assert client.message_calls == [
        (ConversationRef("conversation-1"), None, {"assistant"}, True)
    ]


def test_wait_until_completed_prefers_completed_status_message_even_when_empty() -> None:
    earlier = ChatMessage(
        node_id="earlier-node",
        message_id="earlier-msg",
        role="assistant",
        text="Earlier answer",
    )
    completed = ChatMessage(
        node_id="completed-node",
        message_id="completed-msg",
        role="assistant",
        text="",
    )
    client = FakeWaitClient(
        [
            ConversationStatus(
                status="completed",
                node_id="completed-node",
                message_id="completed-msg",
            )
        ],
        messages=[earlier, completed],
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "completed"
    assert result.message == completed
    assert result.message.text == ""
    assert client.message_calls == [
        (ConversationRef("conversation-1"), None, {"assistant"}, True)
    ]


def test_wait_until_completed_completed_without_assistant_message_returns_result() -> None:
    client = FakeWaitClient([ConversationStatus(status="completed")], messages=[])

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "completed"
    assert result.message is None


def test_wait_until_completed_returns_approval_result() -> None:
    approval = PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )
    client = FakeWaitClient(
        [ConversationStatus(status="awaiting_tool_approval", pending_approval=True)],
        approval=approval,
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "awaiting_tool_approval"
    assert result.approval == approval
    assert result.message is None
    assert result.polls == 1
    assert client.approval_refs == [ConversationRef("conversation-1")]
    assert client.message_calls == []


def test_wait_until_completed_returns_approval_result_without_descriptor() -> None:
    client = FakeWaitClient(
        [ConversationStatus(status="awaiting_tool_approval", pending_approval=True)],
        approval=None,
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "awaiting_tool_approval"
    assert result.approval is None


def test_wait_until_completed_polls_until_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wait_module.time, "sleep", lambda _seconds: None)
    client = FakeWaitClient(
        [
            ConversationStatus(status="running"),
            ConversationStatus(status="tool_calling"),
            ConversationStatus(status="running"),
            ConversationStatus(status="completed"),
        ],
        messages=[ChatMessage(role="assistant", text="Done")],
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "completed"
    assert result.polls == 4
    assert len(client.status_refs) == 4


@pytest.mark.parametrize(
    "first_status",
    ["user_last_message", "tool_running", "unknown"],
)
def test_wait_until_completed_waits_for_non_terminal_statuses(
    first_status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wait_module.time, "sleep", lambda _seconds: None)
    client = FakeWaitClient(
        [
            ConversationStatus(status=first_status),
            ConversationStatus(status="completed"),
        ],
        messages=[ChatMessage(role="assistant", text="Done")],
    )

    result = client.wait_until_completed("conversation-1", timeout=90, interval=0.01)

    assert result.status.status == "completed"
    assert result.polls == 2


def test_wait_until_completed_timeout_raises_controlled_error() -> None:
    status = ConversationStatus(status="running")
    client = FakeWaitClient([status])

    with pytest.raises(ConversationTimeoutError) as exc_info:
        client.wait_until_completed("conversation-1", timeout=0, interval=0.01)

    assert exc_info.value.timeout == 0.0
    assert exc_info.value.last_status == status
    assert "running" in str(exc_info.value)


def test_wait_until_completed_validates_timeout_and_interval_before_polling() -> None:
    client = object.__new__(ChatGPTWebClient)
    client.get_status = lambda _ref: pytest.fail("status should not be fetched")

    with pytest.raises(ValueError, match="timeout must be >= 0"):
        client.wait_until_completed("conversation-1", timeout=-1)
    with pytest.raises(ValueError, match="interval must be > 0"):
        client.wait_until_completed("conversation-1", interval=0)
    with pytest.raises(TypeError, match="timeout must be a number"):
        client.wait_until_completed("conversation-1", timeout="soon")
    with pytest.raises(TypeError, match="interval must be a number"):
        client.wait_until_completed("conversation-1", interval="soon")


def test_wait_until_completed_validates_conversation_reference_before_polling() -> None:
    client = object.__new__(ChatGPTWebClient)
    client.get_status = lambda _ref: pytest.fail("status should not be fetched")

    with pytest.raises(ValueError, match="conversation_id is required"):
        client.wait_until_completed("")
