from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import ChatConversation, ConversationRef

REQUIRED_ACTION_TYPES = {
    "oauth_required",
}


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class RequiredAction:
    """Action that must be completed outside the text stream.

    ChatGPT web can stop on UI-only cards such as connector OAuth prompts. Those
    states are not normal assistant text and are not tool approvals that can be
    allowed browserlessly. This descriptor exposes the card metadata so CLI and
    SDK consumers can surface a clear next step instead of treating the response
    as empty.
    """

    type: str
    tool_message_id: str
    reason: str | None = None
    connector_id: str | None = None
    domain: str | None = None
    path: str | None = None
    target_message_id: str | None = None
    actions: tuple[str, ...] = field(default_factory=tuple)
    is_consequential: bool | None = None
    is_read_only: bool | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RequiredAction | None":
        if not isinstance(payload, dict):
            return None
        action_type = _optional_str(payload.get("type"))
        tool_message_id = _optional_str(payload.get("tool_message_id"))
        if action_type is None or tool_message_id is None:
            return None
        raw_actions = payload.get("actions")
        actions: tuple[str, ...] = ()
        if isinstance(raw_actions, (list, tuple)):
            actions = tuple(
                item for item in (_optional_str(value) for value in raw_actions) if item
            )
        return cls(
            type=action_type,
            tool_message_id=tool_message_id,
            reason=_optional_str(payload.get("reason")),
            connector_id=_optional_str(payload.get("connector_id")),
            domain=_optional_str(payload.get("domain")),
            path=_optional_str(payload.get("path")),
            target_message_id=_optional_str(payload.get("target_message_id")),
            actions=actions,
            is_consequential=payload.get("is_consequential")
            if isinstance(payload.get("is_consequential"), bool)
            else None,
            is_read_only=payload.get("is_read_only")
            if isinstance(payload.get("is_read_only"), bool)
            else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "tool_message_id": self.tool_message_id,
            "reason": self.reason,
            "connector_id": self.connector_id,
            "domain": self.domain,
            "path": self.path,
            "target_message_id": self.target_message_id,
            "actions": list(self.actions),
            "is_consequential": self.is_consequential,
            "is_read_only": self.is_read_only,
        }


def _conversation_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload.get("mapping")
    return mapping if isinstance(mapping, dict) else {}


def _current_branch_nodes(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    mapping = _conversation_mapping(payload)
    node_id = _optional_str(payload.get("current_node"))
    branch: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    while node_id:
        if node_id in seen:
            break
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        branch.append((node_id, node))
        node_id = _optional_str(node.get("parent"))

    branch.reverse()
    return branch


def _message_from_node(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    message = node.get("message")
    return message if isinstance(message, dict) else None


def _message_role(message: dict[str, Any] | None) -> str | None:
    if not isinstance(message, dict):
        return None
    author = message.get("author")
    if not isinstance(author, dict):
        return None
    return _optional_str(author.get("role"))


def _message_metadata(message: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(message, dict):
        return {}
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _action_types(actions: Any) -> tuple[str, ...]:
    if not isinstance(actions, list):
        return ()
    result: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = _optional_str(action.get("type"))
        if action_type:
            result.append(action_type)
    return tuple(result)


def _target_message_id(actions: Any) -> str | None:
    if not isinstance(actions, list):
        return None
    for action in actions:
        if not isinstance(action, dict):
            continue
        for key in ("oauth_redirect", "deny", "allow"):
            block = action.get(key)
            if not isinstance(block, dict):
                continue
            target_message_id = _optional_str(block.get("target_message_id"))
            if target_message_id:
                return target_message_id
    return None


def _required_action_from_message(message: dict[str, Any]) -> RequiredAction | None:
    if _message_role(message) != "tool":
        return None
    tool_message_id = _optional_str(message.get("id"))
    if tool_message_id is None:
        return None

    jit_plugin_data = _message_metadata(message).get("jit_plugin_data")
    if not isinstance(jit_plugin_data, dict):
        return None
    from_server = jit_plugin_data.get("from_server")
    if not isinstance(from_server, dict):
        return None
    action_type = _optional_str(from_server.get("type"))
    if action_type not in REQUIRED_ACTION_TYPES:
        return None

    body = from_server.get("body")
    if not isinstance(body, dict):
        body = {}
    actions = body.get("actions")
    params = body.get("params")
    if not isinstance(params, dict):
        params = {}

    return RequiredAction(
        type=action_type,
        tool_message_id=tool_message_id,
        reason=_optional_str(body.get("auth_reason")),
        connector_id=_optional_str(body.get("connector_id")),
        domain=_optional_str(body.get("domain")),
        path=_optional_str(params.get("path")) or _optional_str(body.get("path")),
        target_message_id=_target_message_id(actions),
        actions=_action_types(actions),
        is_consequential=body.get("is_consequential")
        if isinstance(body.get("is_consequential"), bool)
        else None,
        is_read_only=body.get("is_read_only")
        if isinstance(body.get("is_read_only"), bool)
        else None,
    )


def find_required_action(payload: dict[str, Any]) -> RequiredAction | None:
    """Return the latest required UI action from a conversation payload."""

    candidates: list[tuple[float, RequiredAction]] = []
    for _node_id, node in _current_branch_nodes(payload):
        message = _message_from_node(node)
        if not isinstance(message, dict):
            continue
        required_action = _required_action_from_message(message)
        if required_action is None:
            continue
        create_time = message.get("create_time")
        try:
            sortable_create_time = float(create_time or 0)
        except (TypeError, ValueError):
            sortable_create_time = 0.0
        candidates.append((sortable_create_time, required_action))
    if not candidates:
        return None
    _create_time, required_action = max(candidates, key=lambda item: item[0])
    return required_action


def get_required_action(
    self: Any,
    url_or_id: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> RequiredAction | None:
    """Inspect a conversation for a pending non-text UI action.

    This is primarily for connector OAuth/linking cards, for example a Gmail
    connect prompt. It does not perform the action; it only exposes the state so
    callers can tell the user what happened.
    """

    ref = ConversationRef.from_any(url_or_id)
    payload = self._get_conversation_payload(ref.conversation_id)
    if not isinstance(payload, dict):
        return None
    return find_required_action(payload)
