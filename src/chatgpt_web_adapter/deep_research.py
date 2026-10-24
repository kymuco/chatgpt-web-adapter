"""Read-only observation of an existing ChatGPT Deep Research widget.

This is not a Deep Research launcher or a conversation-completion signal.
The private site widget shape is experimental and may change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from .status import _current_branch_nodes, _message_from_node, _message_metadata, _message_role
from .types import ChatConversation, ConversationRef

DeepResearchState = Literal["unknown", "running", "needs_input", "completed"]

_RUNNING = {"running", "in_progress", "pending", "started", "researching", "searching"}
_NEEDS_INPUT = {"waiting_for_user_response_on_plan", "waiting_for_user_input", "awaiting_user_input"}


@dataclass(frozen=True)
class DeepResearchObservation:
    conversation_id: str
    status: DeepResearchState
    report_id: str | None = None
    report_text: str | None = None


def _json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _is_deep_research_call(message: dict[str, Any] | None) -> bool:
    if not isinstance(message, dict):
        return False
    if _message_role(message) != "assistant" or message.get("recipient") != "api_tool.call_tool":
        return False
    content = message.get("content")
    if not isinstance(content, dict):
        return False
    text = content.get("text")
    if not isinstance(text, str):
        return False
    normalized = text.lower().replace("_", "").replace("-", "").replace(" ", "")
    return "deepresearch" in normalized


def _research_widget(payload: dict[str, Any]) -> dict[str, Any] | None:
    # Restrict to the current canonical branch and the last matched invocation.
    branch = _current_branch_nodes(payload)
    latest_tool: dict[str, Any] | None = None
    for (_, call_node), (_, response_node) in zip(branch, branch[1:]):
        call = _message_from_node(call_node)
        response = _message_from_node(response_node)
        if not _is_deep_research_call(call) or not isinstance(response, dict):
            continue
        author = response.get("author")
        if (
            _message_role(response) == "tool"
            and isinstance(author, dict)
            and author.get("name") == "api_tool.call_tool"
        ):
            latest_tool = response

    if latest_tool is None:
        return None
    sdk = _message_metadata(latest_tool).get("chatgpt_sdk")
    if not isinstance(sdk, dict):
        return None
    # The initial venus_widget_state in tool_response_metadata can remain stale.
    # Only the saved widget_state is eligible as completion evidence.
    return _json_object(sdk.get("widget_state"))


def get_deep_research(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> DeepResearchObservation:
    """Observe Deep Research via one canonical conversation GET, never a Send.

    Unknown is not evidence of absence or non-submission. Ordinary assistant
    status='completed' and the initial research plan are not research finality.
    """

    ref = ConversationRef.from_any(url_or_id)
    result = DeepResearchObservation(ref.conversation_id, "unknown")
    payload = self._get_conversation_payload(ref.conversation_id)
    if not isinstance(payload, dict):
        return result

    widget = _research_widget(payload)
    if widget is None:
        return result
    state = widget.get("status")
    if not isinstance(state, str):
        return result
    state = state.lower().strip()

    if state == "completed":
        report = _json_object(widget.get("report_message"))
        if report is None or report.get("status") != "finished_successfully":
            return result
        report_id = report.get("id")
        content = report.get("content")
        if not isinstance(report_id, str) or not report_id.strip():
            return result
        if not isinstance(content, dict) or content.get("content_type") != "text":
            return result
        parts = content.get("parts")
        if (
            not isinstance(parts, list)
            or len(parts) != 1
            or not isinstance(parts[0], str)
            or not parts[0].strip()
        ):
            return result
        # Preserve report bytes/text as supplied, including product citation markers.
        return DeepResearchObservation(ref.conversation_id, "completed", report_id, parts[0])

    if state in _RUNNING:
        return DeepResearchObservation(ref.conversation_id, "running")
    if state in _NEEDS_INPUT:
        return DeepResearchObservation(ref.conversation_id, "needs_input")
    return result
