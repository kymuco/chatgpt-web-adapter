from __future__ import annotations

from typing import Any

from .types import ChatConversation, ConversationRef, ConversationStatus

ACTIVE_ASYNC_STATUSES = {
    "running",
    "in_progress",
    "pending",
    "queued",
    "started",
    "streaming",
}
COMPLETED_ASYNC_STATUSES = {
    "completed",
    "complete",
    "finished",
    "done",
    "success",
    "succeeded",
}
PENDING_APPROVAL_BOOL_KEYS = (
    "pending_approval",
    "requires_approval",
    "requires_action",
    "pending_tool_approval",
)
PENDING_APPROVAL_COLLECTION_KEYS = (
    "approval_request",
    "approval_requests",
    "pending_approvals",
)
STATUS_METADATA_PREVIEW_KEYS = (
    "async_status",
    "finish_details",
    "finish_reason",
    "is_complete",
    "status",
    "model_slug",
    "jit_plugin_data",
)


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _normalized_status(value: str | None) -> str | None:
    value = _optional_str(value)
    return value.lower() if value else None


def _conversation_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload.get("mapping")
    return mapping if isinstance(mapping, dict) else {}


def _current_node_id(payload: dict[str, Any]) -> str | None:
    return _optional_str(payload.get("current_node"))


def _current_node(payload: dict[str, Any]) -> dict[str, Any] | None:
    node_id = _current_node_id(payload)
    if node_id is None:
        return None
    node = _conversation_mapping(payload).get(node_id)
    return node if isinstance(node, dict) else None


def _message_from_node(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    message = node.get("message")
    return message if isinstance(message, dict) else None


def _message_metadata(message: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(message, dict):
        return {}
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _message_role(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None
    author = message.get("author")
    if not isinstance(author, dict):
        return None
    return _optional_str(author.get("role"))


def _message_finish_reason(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None

    metadata = _message_metadata(message)
    finish_details = metadata.get("finish_details")
    if isinstance(finish_details, dict):
        finish_type = _optional_str(finish_details.get("type"))
        if finish_type:
            return finish_type

    finish_reason = _optional_str(metadata.get("finish_reason"))
    if finish_reason:
        return finish_reason

    return _optional_str(message.get("finish_reason"))


def _async_status(
    payload: dict[str, Any],
    node: dict[str, Any] | None,
    message: dict[str, Any] | None,
) -> str | None:
    metadata = _message_metadata(message)
    sources = (payload, node if isinstance(node, dict) else {}, metadata)
    for source in sources:
        for key in ("async_status", "status"):
            value = _optional_str(source.get(key))
            if value:
                return value
    return None


def _metadata_preview(message: dict[str, Any] | None) -> dict[str, Any]:
    metadata = _message_metadata(message)
    return {key: metadata[key] for key in STATUS_METADATA_PREVIEW_KEYS if key in metadata}


def _truthy_approval_signal(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return False


def _has_generic_pending_approval_signal(*sources: dict[str, Any]) -> bool:
    for source in sources:
        for key in PENDING_APPROVAL_BOOL_KEYS:
            if _truthy_approval_signal(source.get(key)):
                return True
        for key in PENDING_APPROVAL_COLLECTION_KEYS:
            if _truthy_approval_signal(source.get(key)):
                return True
    return False


def _confirm_action_pending_approval(payload: dict[str, Any]) -> bool:
    mapping = _conversation_mapping(payload)
    for node in mapping.values():
        if not isinstance(node, dict) or node.get("children"):
            continue
        message = _message_from_node(node)
        if not isinstance(message, dict):
            continue
        if _message_role(message) != "tool":
            continue
        metadata = _message_metadata(message)
        jit_plugin_data = metadata.get("jit_plugin_data")
        if not isinstance(jit_plugin_data, dict):
            continue
        from_server = jit_plugin_data.get("from_server")
        if not isinstance(from_server, dict) or from_server.get("type") != "confirm_action":
            continue
        body = from_server.get("body")
        if not isinstance(body, dict):
            continue
        actions = body.get("actions")
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, dict) or action.get("type") != "allow":
                continue
            allow = action.get("allow")
            if isinstance(allow, dict) and _optional_str(allow.get("target_message_id")):
                return True
    return False


def _has_pending_approval(
    payload: dict[str, Any],
    node: dict[str, Any] | None,
    message: dict[str, Any] | None,
) -> bool:
    metadata = _message_metadata(message)
    node_dict = node if isinstance(node, dict) else {}
    return _has_generic_pending_approval_signal(payload, node_dict, metadata) or _confirm_action_pending_approval(payload)


def _recipient_is_tool(recipient: str | None) -> bool:
    return recipient not in {None, "", "all"}


def _status_from_signals(
    *,
    role: str | None,
    recipient: str | None,
    async_status: str | None,
    finish_reason: str | None,
    pending_approval: bool,
) -> str:
    normalized_async_status = _normalized_status(async_status)

    if pending_approval:
        return "awaiting_tool_approval"
    if role == "tool":
        return "tool_running"
    if role == "assistant" and _recipient_is_tool(recipient):
        return "tool_calling"
    if normalized_async_status in ACTIVE_ASYNC_STATUSES:
        return "running"
    if role == "assistant" and not finish_reason and recipient in {None, "all"}:
        return "running"
    if role == "user":
        return "user_last_message"
    if role == "assistant" and recipient in {None, "all"} and finish_reason:
        return "completed"
    if role == "assistant" and recipient in {None, "all"} and normalized_async_status in COMPLETED_ASYNC_STATUSES:
        return "completed"
    return "unknown"


def _unknown_status(payload: dict[str, Any] | None = None) -> ConversationStatus:
    async_status = _optional_str(payload.get("async_status")) if isinstance(payload, dict) else None
    return ConversationStatus(status="unknown", async_status=async_status)


def _status_from_payload(payload: dict[str, Any]) -> ConversationStatus:
    node_id = _current_node_id(payload)
    node = _current_node(payload)
    message = _message_from_node(node)
    if node_id is None or node is None or message is None:
        return _unknown_status(payload)

    role = _message_role(message)
    recipient = _optional_str(message.get("recipient"))
    async_status = _async_status(payload, node, message)
    finish_reason = _message_finish_reason(message)
    pending_approval = _has_pending_approval(payload, node, message)
    status = _status_from_signals(
        role=role,
        recipient=recipient,
        async_status=async_status,
        finish_reason=finish_reason,
        pending_approval=pending_approval,
    )

    return ConversationStatus(
        status=status,
        node_id=node_id,
        message_id=message.get("id"),
        role=role,
        recipient=recipient,
        async_status=async_status,
        finish_reason=finish_reason,
        pending_approval=pending_approval,
        metadata_preview=_metadata_preview(message),
    )


def get_status(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> ConversationStatus:
    """Inspect the current lifecycle status of an existing conversation."""

    ref = ConversationRef.from_any(url_or_id)
    payload = self._get_conversation_payload(ref.conversation_id)
    if not isinstance(payload, dict):
        return ConversationStatus(status="unknown")
    return _status_from_payload(payload)
