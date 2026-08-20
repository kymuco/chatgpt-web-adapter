from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ASSISTANT_TEXT_SNAPSHOT = "assistant_text_snapshot"
ASSISTANT_TEXT_DELTA = "assistant_text_delta"
ASSISTANT_TEXT_REVISION = "assistant_text_revision"
CANONICAL_TEXT_FINALIZED = "canonical_text_finalized"

EXACT_MATCH = "EXACT_MATCH"
CANONICAL_EXTENDS_STREAM = "CANONICAL_EXTENDS_STREAM"
STREAM_REVISED_BY_CANONICAL = "STREAM_REVISED_BY_CANONICAL"
STREAM_INCOMPLETE = "STREAM_INCOMPLETE"
UNAVAILABLE = "UNAVAILABLE"

_TEXT_EVENT_TYPES = {
    ASSISTANT_TEXT_SNAPSHOT,
    ASSISTANT_TEXT_DELTA,
    ASSISTANT_TEXT_REVISION,
}


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


@dataclass
class RevisionSafeTextAccumulator:
    """Reconstruct one provisional assistant message from revision-safe events.

    Sequence gaps never fail the product write. They mark the observation stream
    incomplete so canonical finalization can reconcile conservatively.
    """

    text: str = ""
    message_id: str | None = None
    last_sequence: int = 0
    observation_count: int = 0
    revision_count: int = 0
    delta_count: int = 0
    snapshot_count: int = 0
    delivery_incomplete: bool = False

    def apply(self, event: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            return None
        event_type = event.get("type")
        if event_type not in _TEXT_EVENT_TYPES:
            return None
        sequence = _positive_int(event.get("sequence"))
        if sequence is None:
            self.delivery_incomplete = True
            return None
        if sequence <= self.last_sequence:
            # Duplicate/reordered frames are ignored; the final canonical plane
            # remains authoritative and no write action is coupled to delivery.
            return None
        if self.last_sequence and sequence != self.last_sequence + 1:
            self.delivery_incomplete = True
        self.last_sequence = sequence

        message_id = _optional_text(event.get("message_id"))
        if self.message_id and message_id and message_id != self.message_id:
            self.delivery_incomplete = True
        if message_id:
            self.message_id = message_id

        normalized = dict(event)
        if event_type == ASSISTANT_TEXT_SNAPSHOT:
            text = event.get("text")
            if not isinstance(text, str):
                self.delivery_incomplete = True
                return None
            self.text = text
            self.snapshot_count += 1
        elif event_type == ASSISTANT_TEXT_DELTA:
            delta = event.get("delta")
            if not isinstance(delta, str):
                self.delivery_incomplete = True
                return None
            self.text += delta
            self.delta_count += 1
        else:
            text = event.get("text")
            if not isinstance(text, str):
                self.delivery_incomplete = True
                return None
            self.text = text
            self.revision_count += 1

        self.observation_count += 1
        normalized["provisional_text_length"] = len(self.text)
        normalized["delivery_incomplete"] = self.delivery_incomplete
        return normalized

    def reconcile(self, canonical_text: str) -> str:
        if not self.observation_count:
            return UNAVAILABLE
        if self.text == canonical_text:
            return EXACT_MATCH
        if self.delivery_incomplete:
            return STREAM_INCOMPLETE
        if canonical_text.startswith(self.text):
            return CANONICAL_EXTENDS_STREAM
        return STREAM_REVISED_BY_CANONICAL

    def finalization_event(
        self,
        *,
        canonical_text: str,
        conversation_id: str,
        message_id: str | None,
        model: str | None,
        finish_reason: str | None,
    ) -> dict[str, Any]:
        return {
            "type": CANONICAL_TEXT_FINALIZED,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "model": model,
            "finish_reason": finish_reason,
            "text": canonical_text,
            "text_length": len(canonical_text),
            "streamed_text_length": len(self.text) if self.observation_count else 0,
            "stream_observation_count": self.observation_count,
            "stream_revision_count": self.revision_count,
            "stream_delta_count": self.delta_count,
            "stream_delivery_incomplete": self.delivery_incomplete,
            "reconciliation": self.reconcile(canonical_text),
        }
