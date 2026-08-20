from __future__ import annotations

import sys
from typing import Any, TextIO

from .revision_safe_streaming_pr8_9 import (
    ACTIVITY_COMPLETED,
    ACTIVITY_STARTED,
    ACTIVITY_TEXT_DELTA,
    ACTIVITY_TEXT_REVISION,
    ACTIVITY_TEXT_SNAPSHOT,
    ASSISTANT_TEXT_REVISION,
    ASSISTANT_TEXT_SNAPSHOT,
    CANONICAL_TEXT_FINALIZED,
    RevisionSafeTextAccumulator,
)

DEFAULT_STANDALONE_MODEL_PROFILE = "DEEP"
STANDALONE_MODEL_PROFILES: tuple[str, ...] = ("FAST", "BALANCED", "DEEP")


def normalize_standalone_model_profile(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("profile must be a string")
    profile = value.strip().upper()
    if profile not in STANDALONE_MODEL_PROFILES:
        supported = ", ".join(STANDALONE_MODEL_PROFILES)
        raise ValueError(f"unsupported profile {value!r}; expected one of: {supported}")
    return profile


class RevisionSafeTerminalRenderer:
    """Render answer text plus PR8.12 normalized activity progress truthfully.

    PR8.9 assistant text remains revision-safe and canonical-authoritative.
    PR8.12 activity is a separate observational plane: bounded status lines and
    explicitly user-visible recap/display text can be printed while tools run,
    but never participate in final-answer reconciliation.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.text = ""
        self.seen_text_event = False
        self._finished = False
        self._accumulator = RevisionSafeTextAccumulator()
        self._activity_text: dict[str, str] = {}
        self._activity_text_seen: set[str] = set()
        self._activity_open_id: str | None = None

    def _write(self, text: str) -> None:
        if text:
            self.stream.write(text)
            self.stream.flush()

    def _replace(self, text: str, *, label: str) -> None:
        if text == self.text:
            return
        if text.startswith(self.text):
            self._write(text[len(self.text) :])
        else:
            if self.text and not self.text.endswith("\n"):
                self._write("\n")
            self._write(f"[{label}]\n{text}")
        self.text = text

    @staticmethod
    def _activity_id(event: dict[str, Any]) -> str:
        value = event.get("activity_id")
        return value if isinstance(value, str) and value else "activity"

    @staticmethod
    def _activity_kind(event: dict[str, Any]) -> str:
        value = event.get("activity_kind")
        return value if isinstance(value, str) and value else "activity"

    @staticmethod
    def _activity_label(event: dict[str, Any]) -> str:
        value = event.get("label")
        return value if isinstance(value, str) and value else "Activity"

    def _close_activity_text(self) -> None:
        if self._activity_open_id is not None:
            self._write("\n")
            self._activity_open_id = None

    def _render_activity(self, event: dict[str, Any]) -> bool:
        event_type = event.get("type")
        if event_type not in {
            ACTIVITY_STARTED,
            ACTIVITY_TEXT_SNAPSHOT,
            ACTIVITY_TEXT_DELTA,
            ACTIVITY_TEXT_REVISION,
            ACTIVITY_COMPLETED,
        }:
            return False

        activity_id = self._activity_id(event)
        kind = self._activity_kind(event)
        label = self._activity_label(event)

        if event_type == ACTIVITY_STARTED:
            self._close_activity_text()
            self._write(f"[{kind}] {label}\n")
            return True

        if event_type == ACTIVITY_TEXT_SNAPSHOT:
            text = event.get("text")
            if not isinstance(text, str):
                return True
            self._close_activity_text()
            self._activity_text[activity_id] = text
            self._activity_text_seen.add(activity_id)
            self._activity_open_id = activity_id
            self._write(f"[{kind}] {text}")
            return True

        if event_type == ACTIVITY_TEXT_DELTA:
            delta = event.get("delta")
            if not isinstance(delta, str):
                return True
            if self._activity_open_id != activity_id:
                self._close_activity_text()
                self._activity_open_id = activity_id
                self._write(f"[{kind}] ")
            self._activity_text[activity_id] = self._activity_text.get(activity_id, "") + delta
            self._activity_text_seen.add(activity_id)
            self._write(delta)
            return True

        if event_type == ACTIVITY_TEXT_REVISION:
            text = event.get("text")
            if not isinstance(text, str):
                return True
            self._close_activity_text()
            self._activity_text[activity_id] = text
            self._activity_text_seen.add(activity_id)
            self._activity_open_id = activity_id
            self._write(f"[{kind} revision]\n{text}")
            return True

        self._close_activity_text()
        if activity_id not in self._activity_text_seen:
            self._write(f"[{kind}] {label}\n")
        return True

    def on_event(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        event_type = event.get("type")

        if self._render_activity(event):
            return

        if event_type == CANONICAL_TEXT_FINALIZED:
            text = event.get("text")
            if not isinstance(text, str):
                return
            self._close_activity_text()
            self.seen_text_event = True
            self._replace(text, label="canonical")
            return

        normalized = self._accumulator.apply(event)
        if normalized is None:
            return

        self._close_activity_text()
        self.seen_text_event = True
        label = (
            "revision"
            if event_type == ASSISTANT_TEXT_REVISION
            else "snapshot"
            if event_type == ASSISTANT_TEXT_SNAPSHOT
            else "stream"
        )
        self._replace(self._accumulator.text, label=label)

    def finish(self, canonical_text: str) -> None:
        if self._finished:
            return
        self._finished = True
        self._close_activity_text()
        if not isinstance(canonical_text, str):
            canonical_text = str(canonical_text)
        self._replace(canonical_text, label="canonical")
        if not self.text.endswith("\n"):
            self._write("\n")
