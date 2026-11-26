"""Identity-bound, read-only verification for a completed Direct HTTP turn."""

from __future__ import annotations

import time
from typing import Any, Callable

from .exceptions import RequestError
from .status import _status_from_payload


class CanonicalTurnError(RequestError):
    """Safe, fixed reason code; never includes conversation contents or IDs."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"Direct HTTP final text is not canonically verified ({reason}); "
            "the conversation write may already be committed; do not replay",
            request_stage="canonical_final_text",
        )


def _unverified(reason: str) -> CanonicalTurnError:
    return CanonicalTurnError(reason)


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
    if not all(
        isinstance(x, str) and x for x in (conversation_id, user_id, message_id)
    ):
        raise _unverified("missing_identity")
    if not isinstance(payload, dict):
        raise _unverified("invalid_payload")
    observed_id = payload.get("conversation_id") or payload.get("id")
    if observed_id is not None and observed_id != conversation_id:
        raise _unverified("conversation_mismatch")
    status = _status_from_payload(payload)
    if status.status != "completed" or status.message_id != message_id:
        raise _unverified("turn_not_completed_or_not_current")
    mapping = payload.get("mapping")
    node_id = payload.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(node_id, str):
        raise _unverified("invalid_mapping")
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
                    raise _unverified("user_mismatch_or_empty_text")
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
                raise _unverified("final_not_visible_or_incomplete")
            if visible:
                parts = content.get("parts")
                if not isinstance(parts, list) or not all(
                    isinstance(part, str) for part in parts
                ):
                    raise _unverified("invalid_parts")
                segments.append("".join(parts))
        node_id = node.get("parent")
    raise _unverified("user_ancestor_missing")


def verify_canonical_turn(
    read: Callable[[str], dict[str, Any]],
    *,
    conversation_id: str | None,
    user_id: str | None,
    message_id: str | None,
) -> str:
    """Bounded read-only recovery after one submitted write; never resend."""
    if not all(isinstance(x, str) and x for x in (conversation_id, user_id, message_id)):
        raise _unverified("missing_identity")
    for attempt in range(3):
        try:
            payload = read(conversation_id)
        except RequestError as error:
            # Only transient read failures are retried. Auth and other
            # permanent HTTP errors fail immediately.
            if attempt == 2 or error.status_code not in (None, 408, 429, 500, 502, 503, 504):
                raise _unverified("read_failed") from error
        else:
            try:
                return canonical_turn_text(
                    payload, conversation_id=conversation_id,
                    user_id=user_id, message_id=message_id,
                )
            except CanonicalTurnError as error:
                if attempt == 2 or error.reason not in (
                    "turn_not_completed_or_not_current", "user_ancestor_missing",
                    "final_not_visible_or_incomplete",
                ):
                    raise
        time.sleep(0.25 * (2 ** attempt))
    raise AssertionError("unreachable canonical verification state")
