from __future__ import annotations

import pytest

import chatgpt_web_adapter
from chatgpt_web_adapter import (
    ApprovalEvent,
    ApprovalResult,
    ApprovalRound,
    ChatConversation,
    ChatMetrics,
    ChatResponse,
    PendingApproval,
)
from chatgpt_web_adapter.approval_types import (
    APPROVAL_EVENT_TYPES,
    APPROVAL_RESULT_STATUSES,
    APPROVAL_ROUND_STATUSES,
)


def _approval() -> PendingApproval:
    return PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )


def _event() -> ApprovalEvent:
    return ApprovalEvent(
        type="approval_detected",
        conversation_id="conversation-1",
        round_index=1,
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
    )


def _response() -> ChatResponse:
    return ChatResponse(
        text="Done",
        title="Approval workflow",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="assistant-msg",
            finish_reason="stop",
            parent_message_id="assistant-msg",
        ),
        metrics=ChatMetrics(first_token=0.1, last_token=0.3, total=0.4),
    )


def test_approval_event_accepts_known_event_types() -> None:
    for event_type in APPROVAL_EVENT_TYPES:
        assert ApprovalEvent(type=event_type).type == event_type


def test_approval_event_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="unsupported approval event type"):
        ApprovalEvent(type="unknown")


def test_approval_event_normalizes_optional_strings() -> None:
    event = ApprovalEvent(
        type=" approval_detected ",
        conversation_id=" conversation-1 ",
        tool_message_id=" tool-msg ",
        target_message_id=" target-node ",
        recipient=" python ",
        reason=" allowed_by_policy ",
    )

    assert event.type == "approval_detected"
    assert event.conversation_id == "conversation-1"
    assert event.tool_message_id == "tool-msg"
    assert event.target_message_id == "target-node"
    assert event.recipient == "python"
    assert event.reason == "allowed_by_policy"


@pytest.mark.parametrize("round_index", [0, -1])
def test_approval_event_rejects_non_positive_round_index(round_index: int) -> None:
    with pytest.raises(ValueError, match="round_index must be positive"):
        ApprovalEvent(type="approval_detected", round_index=round_index)


def test_approval_event_rejects_non_integer_round_index() -> None:
    with pytest.raises(TypeError, match="round_index must be an integer"):
        ApprovalEvent(type="approval_detected", round_index="abc")


def test_approval_event_allowed_accepts_bool_or_none() -> None:
    assert ApprovalEvent(type="approval_allowed", allowed=True).allowed is True
    assert ApprovalEvent(type="approval_denied", allowed=False).allowed is False
    assert ApprovalEvent(type="approval_detected").allowed is None


def test_approval_event_allowed_rejects_non_bool_values() -> None:
    with pytest.raises(TypeError, match="allowed must be a bool or None"):
        ApprovalEvent(type="approval_allowed", allowed="false")


def test_approval_event_metadata_none_becomes_empty_dict() -> None:
    event = ApprovalEvent(type="approval_detected", metadata_preview=None)

    assert event.metadata_preview == {}


def test_approval_event_metadata_non_dict_raises_type_error() -> None:
    with pytest.raises(TypeError, match="metadata_preview must be a dict"):
        ApprovalEvent(type="approval_detected", metadata_preview="bad")


def test_approval_event_deep_copies_metadata_on_construction() -> None:
    metadata = {"nested": {"value": 1}}
    event = ApprovalEvent(type="approval_detected", metadata_preview=metadata)

    metadata["nested"]["value"] = 2

    assert event.metadata_preview == {"nested": {"value": 1}}


def test_approval_event_to_dict_deep_copies_metadata() -> None:
    event = ApprovalEvent(
        type="approval_detected",
        metadata_preview={"nested": {"value": 1}},
    )

    payload = event.to_dict()
    payload["metadata_preview"]["nested"]["value"] = 2

    assert event.metadata_preview == {"nested": {"value": 1}}


def test_approval_event_from_dict_roundtrip() -> None:
    event = ApprovalEvent(
        type="approval_allowed",
        conversation_id="conversation-1",
        round_index=1,
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient="python",
        allowed=True,
        reason="recipient_allowed",
        metadata_preview={"safe": True},
    )

    assert ApprovalEvent.from_dict(event.to_dict()) == event


def test_approval_event_from_dict_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="approval event payload must be a dict"):
        ApprovalEvent.from_dict(None)


def test_approval_round_accepts_known_statuses() -> None:
    for status in APPROVAL_ROUND_STATUSES:
        assert ApprovalRound(index=1, status=status).status == status


def test_approval_round_validates_positive_index() -> None:
    with pytest.raises(ValueError, match="index must be positive"):
        ApprovalRound(index=0)
    with pytest.raises(TypeError, match="index must be an integer"):
        ApprovalRound(index="abc")


def test_approval_round_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="unsupported approval round status"):
        ApprovalRound(index=1, status="unknown")


def test_approval_round_accepts_pending_approval() -> None:
    approval = _approval()
    round_item = ApprovalRound(index=1, approval=approval)

    assert round_item.approval == approval


def test_approval_round_rejects_non_pending_approval() -> None:
    with pytest.raises(TypeError, match="approval must be a PendingApproval or None"):
        ApprovalRound(index=1, approval="bad")


def test_approval_round_rejects_non_approval_event_items() -> None:
    with pytest.raises(TypeError, match="events must contain ApprovalEvent items"):
        ApprovalRound(index=1, events=["bad"])


def test_approval_round_normalizes_error() -> None:
    round_item = ApprovalRound(index=1, error=" failed ")

    assert round_item.error == "failed"


def test_approval_round_to_dict() -> None:
    event = _event()
    approval = _approval()
    round_item = ApprovalRound(
        index=1,
        approval=approval,
        status="detected",
        events=[event],
        error="none",
    )

    assert round_item.to_dict() == {
        "index": 1,
        "approval": approval.to_dict(),
        "status": "detected",
        "events": [event.to_dict()],
        "error": "none",
    }


def test_approval_round_from_dict_roundtrip() -> None:
    round_item = ApprovalRound(
        index=1,
        approval=_approval(),
        status="completed",
        events=[_event()],
        error="none",
    )

    assert ApprovalRound.from_dict(round_item.to_dict()) == round_item


def test_approval_round_from_dict_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="approval round payload must be a dict"):
        ApprovalRound.from_dict(None)


def test_approval_result_accepts_known_statuses() -> None:
    for status in APPROVAL_RESULT_STATUSES:
        assert ApprovalResult(status=status).status == status


def test_approval_result_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="unsupported approval result status"):
        ApprovalResult(status="unknown")


def test_approval_result_rejects_non_round_items() -> None:
    with pytest.raises(TypeError, match="rounds must contain ApprovalRound items"):
        ApprovalResult(rounds=["bad"])


def test_approval_result_rejects_non_event_items() -> None:
    with pytest.raises(TypeError, match="events must contain ApprovalEvent items"):
        ApprovalResult(events=["bad"])


def test_approval_result_accepts_chat_response() -> None:
    response = _response()
    result = ApprovalResult(response=response)

    assert result.response == response


def test_approval_result_rejects_non_chat_response() -> None:
    with pytest.raises(TypeError, match="response must be a ChatResponse or None"):
        ApprovalResult(response="bad")


def test_approval_result_normalizes_error() -> None:
    result = ApprovalResult(status="failed", error=" failed ")

    assert result.error == "failed"


def test_approval_result_to_dict_with_response_preview() -> None:
    event = _event()
    round_item = ApprovalRound(index=1, approval=_approval(), events=[event])
    response = _response()
    result = ApprovalResult(
        status="completed",
        rounds=[round_item],
        events=[event],
        response=response,
        error=None,
    )

    assert result.to_dict() == {
        "status": "completed",
        "rounds": [round_item.to_dict()],
        "events": [event.to_dict()],
        "response": {
            "text": "Done",
            "title": "Approval workflow",
            "conversation": response.conversation.to_dict(),
            "metrics": {
                "first_token": 0.1,
                "last_token": 0.3,
                "total": 0.4,
            },
        },
        "error": None,
    }


def test_approval_result_from_dict_roundtrip_with_response() -> None:
    result = ApprovalResult(
        status="completed",
        rounds=[ApprovalRound(index=1, approval=_approval(), events=[_event()])],
        events=[_event()],
        response=_response(),
    )

    assert ApprovalResult.from_dict(result.to_dict()) == result


def test_approval_result_from_dict_roundtrip_without_response() -> None:
    result = ApprovalResult(
        status="denied",
        rounds=[ApprovalRound(index=1, approval=_approval(), status="denied")],
        events=[ApprovalEvent(type="approval_denied", allowed=False, reason="policy_denied")],
        error="policy_denied",
    )

    assert ApprovalResult.from_dict(result.to_dict()) == result


def test_approval_result_from_dict_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="approval result payload must be a dict"):
        ApprovalResult.from_dict(None)


def test_approval_types_are_exported_from_public_package() -> None:
    assert chatgpt_web_adapter.ApprovalEvent is ApprovalEvent
    assert chatgpt_web_adapter.ApprovalRound is ApprovalRound
    assert chatgpt_web_adapter.ApprovalResult is ApprovalResult
    assert "ApprovalEvent" in chatgpt_web_adapter.__all__
    assert "ApprovalRound" in chatgpt_web_adapter.__all__
    assert "ApprovalResult" in chatgpt_web_adapter.__all__
