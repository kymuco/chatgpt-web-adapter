"""Offline regressions for canonical Deep Research readback (no Send)."""

from __future__ import annotations

import json

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.deep_research import DeepResearchObservation


def _conversation(widget, *, marker="connector_openai_deep_research"):
    call = {
        "id": "call-1",
        "author": {"role": "assistant"},
        "recipient": "api_tool.call_tool",
        "content": {"content_type": "code", "text": json.dumps({"tool": marker})},
    }
    response = {
        "id": "tool-1",
        "author": {"role": "tool", "name": "api_tool.call_tool"},
        "recipient": "all",
        "content": {"content_type": "code", "text": "response"},
        "metadata": {
            "chatgpt_sdk": {
                "tool_response_metadata": {
                    "venus_widget_state": {"status": "waiting_for_user_response_on_plan"}
                },
                "widget_state": json.dumps(widget),
            }
        },
    }
    closing = {
        "id": "assistant-1",
        "author": {"role": "assistant"},
        "recipient": "all",
        "content": {"content_type": "text", "parts": ["Research initiated"]},
        "metadata": {"finish_details": {"type": "stop"}},
        "end_turn": True,
    }
    nodes = [call, response, closing]
    mapping = {}
    for index, message in enumerate(nodes):
        key = message["id"]
        mapping[key] = {
            "id": key,
            "parent": nodes[index - 1]["id"] if index else None,
            "children": [nodes[index + 1]["id"]] if index < len(nodes) - 1 else [],
            "message": message,
        }
    return {"conversation_id": "conversation-1", "mapping": mapping, "current_node": "assistant-1"}


def _client(cls, payload):
    client = object.__new__(cls)
    reads = []

    def read(cid):
        reads.append(cid)
        return payload

    client._get_conversation_payload = read
    client.send = lambda *_args, **_kwargs: pytest.fail("must not issue Send")
    return client, reads


@pytest.mark.parametrize("cls", [ChatGPTWebClient, BrowserlessHTTPClient])
def test_completed_report_is_read_once_with_exact_content(cls):
    text = "# Technical report\n\n\ue200cite\ue202turn1search0\ue201"
    report = {
        "id": "report-1",
        "status": "finished_successfully",
        "content": {"content_type": "text", "parts": [text]},
    }
    client, reads = _client(cls, _conversation({"status": "completed", "report_message": report}))

    result = client.get_deep_research("conversation-1")

    assert isinstance(result, DeepResearchObservation)
    assert result.status == "completed"
    assert result.report_id == "report-1"
    assert result.report_text == text
    assert reads == ["conversation-1"]


@pytest.mark.parametrize(
    ("widget", "expected"),
    [
        ({"status": "in_progress"}, "running"),
        ({"status": "waiting_for_user_response_on_plan"}, "needs_input"),
        ({"status": "failed"}, "unknown"),
        ({"status": "completed"}, "unknown"),
        (
            {
                "status": "completed",
                "report_message": {
                    "id": "report-1",
                    "status": "finished_successfully",
                    "content": {"content_type": "text", "parts": []},
                },
            },
            "unknown",
        ),
    ],
)
def test_widget_state_never_confuses_assistant_completion_with_research_finality(
    widget, expected
):
    client, _ = _client(ChatGPTWebClient, _conversation(widget))
    result = client.get_deep_research("conversation-1")
    assert result.status == expected
    assert result.report_text is None
    assert result.report_id is None


def test_research_result_requires_identified_deep_research_call():
    report = {
        "id": "report-1",
        "status": "finished_successfully",
        "content": {"content_type": "text", "parts": ["Report"]},
    }
    client, _ = _client(
        ChatGPTWebClient,
        _conversation({"status": "completed", "report_message": report}, marker="connector_other"),
    )
    assert client.get_deep_research("conversation-1").status == "unknown"


def test_bad_widget_json_and_unrelated_conversation_fail_closed():
    payload = _conversation({"status": "completed"})
    payload["mapping"]["tool-1"]["message"]["metadata"]["chatgpt_sdk"]["widget_state"] = "{"
    client, _ = _client(ChatGPTWebClient, payload)
    assert client.get_deep_research("conversation-1").status == "unknown"

    client, _ = _client(ChatGPTWebClient, {"mapping": {}, "current_node": None})
    assert client.get_deep_research("conversation-1").status == "unknown"


def test_invalid_conversation_id_does_not_fetch():
    client, reads = _client(ChatGPTWebClient, _conversation({"status": "running"}))
    with pytest.raises(ValueError, match="conversation_id is required"):
        client.get_deep_research("")
    assert reads == []
