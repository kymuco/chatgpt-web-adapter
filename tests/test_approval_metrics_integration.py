from __future__ import annotations

import webchat_adapter
from webchat_adapter import ApprovalResult, ChatConversation, ChatMetrics, ChatResponse


def test_approval_result_from_dict_preserves_expanded_metrics_class() -> None:
    result = ApprovalResult(
        status="completed",
        response=ChatResponse(
            text="Done",
            conversation=ChatConversation(
                conversation_id="conversation-1",
                message_id="assistant-msg",
            ),
            metrics=ChatMetrics(
                first_token=0.1,
                last_token=0.3,
                total=0.4,
                requirements_latency=0.05,
                stream_duration=0.35,
                chars_per_second=11.0,
                backend_status=200,
            ),
        ),
    )

    restored = ApprovalResult.from_dict(result.to_dict())

    assert restored == result
    assert isinstance(restored.response.metrics, webchat_adapter.ChatMetrics)
    assert restored.response.metrics.backend_status == 200
