from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from .messages import get_messages as _get_messages_from_payload
from .types import ChatConversation, ChatMessage, ConversationRef

CANONICAL_CONVERSATION_SNAPSHOT_SCHEMA = "cwa.canonical_conversation_snapshot.v1"
CanonicalConversationReadScope = Literal["full_history"]


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class ConversationReadProvenance:
    """Bounded, transport-independent evidence for one canonical conversation read."""

    complete: bool
    canonical_record_count: int
    read_scope: CanonicalConversationReadScope = "full_history"

    def __post_init__(self) -> None:
        if isinstance(self.canonical_record_count, bool) or not isinstance(
            self.canonical_record_count, int
        ):
            raise TypeError("canonical_record_count must be an int")
        if self.canonical_record_count < 0:
            raise ValueError("canonical_record_count must be non-negative")
        if self.read_scope != "full_history":
            raise ValueError(f"unsupported read_scope: {self.read_scope!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "canonical_record_count": self.canonical_record_count,
            "read_scope": self.read_scope,
        }


@dataclass(frozen=True)
class CanonicalConversationSnapshot:
    """Stable in-memory projection of one complete canonical conversation read.

    ``to_dict()`` exposes the stable CWA snapshot schema. ``to_canonical_payload()``
    is an advanced escape hatch for callers that need the complete normalized
    conversation payload without depending on private client methods.
    """

    conversation_id: str
    messages: tuple[ChatMessage, ...]
    current_node: str | None
    title: str | None
    provenance: ConversationReadProvenance
    _canonical_payload: dict[str, Any] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        ref = ConversationRef(self.conversation_id)
        object.__setattr__(self, "conversation_id", ref.conversation_id)
        if not isinstance(self.messages, tuple) or not all(
            isinstance(message, ChatMessage) for message in self.messages
        ):
            raise TypeError("messages must be a tuple of ChatMessage values")
        if not isinstance(self.provenance, ConversationReadProvenance):
            raise TypeError("provenance must be ConversationReadProvenance")
        if not isinstance(self._canonical_payload, dict):
            raise TypeError("canonical payload must be a dict")
        object.__setattr__(self, "current_node", _optional_str(self.current_node))
        object.__setattr__(self, "title", _optional_str(self.title))
        object.__setattr__(
            self, "_canonical_payload", copy.deepcopy(self._canonical_payload)
        )

    @property
    def complete(self) -> bool:
        return self.provenance.complete

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CANONICAL_CONVERSATION_SNAPSHOT_SCHEMA,
            "conversation_id": self.conversation_id,
            "current_node": self.current_node,
            "title": self.title,
            "complete": self.complete,
            "message_count": self.message_count,
            "provenance": self.provenance.to_dict(),
            "messages": [message.to_dict() for message in self.messages],
        }

    def to_canonical_payload(self) -> dict[str, Any]:
        """Return a defensive copy of the complete normalized conversation payload."""

        return copy.deepcopy(self._canonical_payload)


@dataclass
class _FixedConversationPayloadReader:
    payload: dict[str, Any]

    def _get_conversation_payload(self, _conversation_id: str) -> dict[str, Any]:
        return self.payload


def canonical_snapshot_from_payload(
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
    payload: dict[str, Any],
) -> CanonicalConversationSnapshot:
    """Build one public snapshot from an already-complete canonical payload."""

    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("canonical conversation payload must contain mapping")

    ref = ConversationRef.from_any(conversation)
    payload_conversation_id = _optional_str(payload.get("conversation_id"))
    if (
        payload_conversation_id is not None
        and payload_conversation_id != ref.conversation_id
    ):
        raise ValueError("conversation identity does not match canonical payload")

    messages = tuple(
        _get_messages_from_payload(
            _FixedConversationPayloadReader(payload),
            ref,
            limit=None,
            include_empty=True,
        )
    )
    provenance = ConversationReadProvenance(
        complete=True,
        canonical_record_count=len(mapping),
    )
    return CanonicalConversationSnapshot(
        conversation_id=ref.conversation_id,
        messages=messages,
        current_node=_optional_str(payload.get("current_node")),
        title=_optional_str(payload.get("title")),
        provenance=provenance,
        _canonical_payload=payload,
    )


def get_conversation_snapshot(
    self: Any,
    conversation: ConversationRef | ChatConversation | dict[str, Any] | str,
) -> CanonicalConversationSnapshot:
    """Read complete canonical history once and return a stable in-memory snapshot."""

    ref = ConversationRef.from_any(conversation)
    full_reader = getattr(self, "_get_full_conversation_payload", None)
    if not callable(full_reader):
        raise TypeError(
            "canonical conversation snapshot requires _get_full_conversation_payload()"
        )
    payload = full_reader(ref.conversation_id)
    return canonical_snapshot_from_payload(ref, payload)


__all__ = [
    "CANONICAL_CONVERSATION_SNAPSHOT_SCHEMA",
    "CanonicalConversationSnapshot",
    "ConversationReadProvenance",
    "canonical_snapshot_from_payload",
    "get_conversation_snapshot",
]
