"""Identity-bound, read-only verification for a completed Direct HTTP turn."""

from __future__ import annotations

from typing import Any

from .exceptions import RequestError
from .status import _status_from_payload


def _unverified() -> RequestError:
    return RequestError(
        "Direct HTTP final text is not canonically verified; "
        "the conversation write may already be committed; do not replay"
    )


def canonical_turn_text(
    payload: dict[str, Any],
    *,
    conversation_id: str,
    user_id: str,
    message_id: str,
) -> str:
    """Read only the exact completed turn on the active branch.

    Never select the globally newest assistant message. No recovery writes.
    """
    if not all(isinstance(x, str) and x for x in (conversation_id, user_id, message_id)):
        raise _unverified()
    if not isinstance(payload, dict):
        raise _unverified()
    observed_id = payload.get("conversation_id") or payload.get("id")
    if observed_id is not None and observed_id != conversation_id:
        raise _unverified()
    status = _status_from_payload(payload)
    if status.status != "completed" or status.message_id != message_id:
        raise _unverified()
    mapping = payload.get("mapping")
    node_id = payload.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(node_id, str):
        raise _unverified()
    seen: set[str] = set()
    segments: list[str] = []
    while isinstance(node_id, str) and node_id not in seen:
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        message = node.get("message")
        if isinstance(message, dict):
            author = message.get("author") or {}
            role = author.get("role")
            if role == "user":
                if message.get("id") != user_id or not segments:
                    raise _unverified()
                return "".join(reversed(segments))
            content = message.get("content") or {}
            metadata = message.get("metadata") or {}
            visible = (
                role == "assistant"
                and message.get("recipient", "all") == "all"
                and message.get("channel") in (None, "final")
                and not metadata.get("is_visually_hidden_from_conversation")
                and content.get("content_type") == "text"
            )
            if message.get("id") == message_id and (
                not visible or message.get("end_turn") is False
            ):
                raise _unverified()
            if visible:
                parts = content.get("parts")
                if not isinstance(parts, list) or not all(
                    isinstance(part, str) for part in parts
                ):
                    raise _unverified()
                segments.append("".join(parts))
        node_id = node.get("parent")
    raise _unverified()
