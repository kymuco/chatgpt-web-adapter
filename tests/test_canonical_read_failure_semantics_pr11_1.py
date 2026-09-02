from __future__ import annotations

import pytest

from chatgpt_web_adapter.browser_native_client import _wait_for_new_final_assistant
from chatgpt_web_adapter.exceptions import RequestError


def _canonical_payload() -> dict:
    return {
        "conversation_id": "conversation-1",
        "title": "Canonical read retry",
        "current_node": "assistant-node",
        "mapping": {
            "assistant-node": {
                "id": "assistant-node",
                "parent": None,
                "children": [],
                "message": {
                    "id": "assistant-1",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {
                        "content_type": "text",
                        "parts": ["CANONICAL_OK"],
                    },
                    "metadata": {
                        "finish_details": {"type": "stop"},
                        "model_slug": "gpt-test",
                    },
                },
            }
        },
    }


class _CanonicalReader:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.reads = 0

    def _get_conversation_payload(self, conversation_id: str):
        assert conversation_id == "conversation-1"
        self.reads += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_deterministic_403_fails_immediately_after_one_read(monkeypatch) -> None:
    client = _CanonicalReader(
        [RequestError("conversation status=403: access challenged")]
    )
    monkeypatch.setattr("chatgpt_web_adapter.browser_native_client.time.sleep", lambda _: None)

    with pytest.raises(RequestError) as raised:
        _wait_for_new_final_assistant(
            client,
            "conversation-1",
            baseline_assistant_ids=set(),
            timeout=60.0,
            interval=0.5,
        )

    assert raised.value.status_code == 403
    assert client.reads == 1


def test_exact_404_visibility_lag_is_retryable(monkeypatch) -> None:
    client = _CanonicalReader(
        [
            RequestError("conversation status=404: not visible yet"),
            _canonical_payload(),
        ]
    )
    monkeypatch.setattr("chatgpt_web_adapter.browser_native_client.time.sleep", lambda _: None)

    message = _wait_for_new_final_assistant(
        client,
        "conversation-1",
        baseline_assistant_ids=set(),
        timeout=60.0,
        interval=0.5,
    )

    assert message.message_id == "assistant-1"
    assert message.text == "CANONICAL_OK"
    assert client.reads == 2


def test_unclassified_canonical_reader_failure_is_not_hidden(monkeypatch) -> None:
    client = _CanonicalReader([ValueError("canonical payload decoder failed")])
    monkeypatch.setattr("chatgpt_web_adapter.browser_native_client.time.sleep", lambda _: None)

    with pytest.raises(ValueError, match="canonical payload decoder failed"):
        _wait_for_new_final_assistant(
            client,
            "conversation-1",
            baseline_assistant_ids=set(),
            timeout=60.0,
            interval=0.5,
        )

    assert client.reads == 1
