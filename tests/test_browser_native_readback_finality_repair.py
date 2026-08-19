from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_native_client import (
    _status_finalizes_message,
    _wait_for_new_final_assistant,
)
from chatgpt_web_adapter.exceptions import ConversationTimeoutError
from chatgpt_web_adapter.messages import _message_finish_reason


def test_message_finish_reason_prefers_finish_details_type() -> None:
    message = {
        "metadata": {
            "finish_details": {"type": "stop"},
            "finish_reason": "metadata-fallback",
        },
        "finish_reason": "top-level-fallback",
    }
    assert _message_finish_reason(message) == "stop"


def test_message_finish_reason_falls_back_to_metadata_finish_reason() -> None:
    message = {"metadata": {"finish_reason": "stop"}}
    assert _message_finish_reason(message) == "stop"


def test_message_finish_reason_falls_back_to_top_level_finish_reason() -> None:
    message = {"metadata": {}, "finish_reason": "stop"}
    assert _message_finish_reason(message) == "stop"


def test_status_finality_requires_matching_message_id() -> None:
    status = SimpleNamespace(status="completed", message_id="assistant-new")
    assert _status_finalizes_message(status, "assistant-new") is True
    assert _status_finalizes_message(status, "assistant-old") is False


class _ReadbackClient:
    def __init__(self, *, status, messages) -> None:
        self.status = status
        self.messages = messages

    def get_status(self, conversation):
        return self.status

    def get_messages(self, conversation, **kwargs):
        return self.messages


def _assistant(*, message_id: str, text: str, finish_reason=None):
    return SimpleNamespace(
        message_id=message_id,
        text=text,
        finish_reason=finish_reason,
        model="gpt-test",
    )


def test_matching_completed_status_finalizes_nonempty_assistant_without_finish_reason() -> None:
    message = _assistant(message_id="assistant-new", text="done", finish_reason=None)
    client = _ReadbackClient(
        status=SimpleNamespace(status="completed", message_id="assistant-new"),
        messages=[message],
    )
    assert _wait_for_new_final_assistant(
        client,
        "conversation-1",
        baseline_assistant_ids=set(),
        timeout=0.01,
        interval=0.001,
    ) is message


def test_stale_completed_status_cannot_finalize_new_partial_assistant() -> None:
    message = _assistant(message_id="assistant-new", text="partial", finish_reason=None)
    client = _ReadbackClient(
        status=SimpleNamespace(status="completed", message_id="assistant-old"),
        messages=[message],
    )
    with pytest.raises(ConversationTimeoutError):
        _wait_for_new_final_assistant(
            client,
            "conversation-1",
            baseline_assistant_ids=set(),
            timeout=0.001,
            interval=0.001,
        )


def test_running_status_cannot_finalize_same_message_without_finish_reason() -> None:
    message = _assistant(message_id="assistant-new", text="partial", finish_reason=None)
    client = _ReadbackClient(
        status=SimpleNamespace(status="running", message_id="assistant-new"),
        messages=[message],
    )
    with pytest.raises(ConversationTimeoutError):
        _wait_for_new_final_assistant(
            client,
            "conversation-1",
            baseline_assistant_ids=set(),
            timeout=0.001,
            interval=0.001,
        )


def test_finish_reason_remains_fast_path_without_status_message_id() -> None:
    message = _assistant(message_id="assistant-new", text="done", finish_reason="stop")
    client = _ReadbackClient(
        status=SimpleNamespace(status="completed", message_id=None),
        messages=[message],
    )
    assert _wait_for_new_final_assistant(
        client,
        "conversation-1",
        baseline_assistant_ids=set(),
        timeout=0.01,
        interval=0.001,
    ) is message
