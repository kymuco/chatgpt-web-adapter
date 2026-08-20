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
    """Render PR8.9 answer text and PR8.12 activity truthfully.

    The default mode reproduces the user-visible ChatGPT turn: assistant
    commentary, normalized activity, recap/display text, then the revision-safe
    final answer. ``final_answer_only=True`` suppresses every intermediate plane
    and renders only the terminal assistant answer while keeping canonical
    readback authoritative.
    """

    _GENERIC_COMPLETION_LABELS = {
        "Web activity complete",
        "Reasoning summary complete",
        "Browsing update complete",
        "Tool activity complete",
    }
    _TEXT_ACTIVITY_START_LABELS = {
        "Reasoning summary",
        "Browsing update",
    }

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        final_answer_only: bool = False,
    ) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.final_answer_only = bool(final_answer_only)
        self.text = ""
        self.seen_text_event = False
        self._finished = False
        self._accumulator = RevisionSafeTextAccumulator()
        self._activity_text: dict[str, str] = {}
        self._activity_text_seen: set[str] = set()
        self._activity_open_id: str | None = None
        self._output_ends_with_newline = True
        self._last_activity_status: tuple[str, str] | None = None

        # Final-only state. Explicit OpenAI output-channel evidence wins. When
        # the web payload omits that marker, activity plus a new assistant
        # message id provides a conservative compatibility fallback.
        self._final_only_activity_seen = False
        self._final_only_suppressed_message_ids: set[str] = set()
        self._final_only_active_message_id: str | None = None

    def _write(self, text: str) -> None:
        if text:
            self.stream.write(text)
            self.stream.flush()
            self._output_ends_with_newline = text.endswith("\n")

    def _ensure_line_boundary(self) -> None:
        if not self._output_ends_with_newline:
            self._write("\n")

    def _replace(self, text: str, *, label: str) -> None:
        if text == self.text:
            return
        if text.startswith(self.text):
            self._write(text[len(self.text) :])
        else:
            self._ensure_line_boundary()
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

    @staticmethod
    def _message_id(event: dict[str, Any]) -> str | None:
        value = event.get("message_id")
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _assistant_channel(event: dict[str, Any]) -> str | None:
        value = event.get("channel")
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized in {"final", "commentary"} else None

    def _activity_status_line(self, kind: str, label: str) -> None:
        status = (kind, label)
        if status == self._last_activity_status:
            return
        self._ensure_line_boundary()
        self._write(f"[{kind}] {label}\n")
        self._last_activity_status = status

    def _close_activity_text(self) -> None:
        if self._activity_open_id is not None:
            self._ensure_line_boundary()
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

        if self.final_answer_only:
            self._final_only_activity_seen = True
            return True

        activity_id = self._activity_id(event)
        kind = self._activity_kind(event)
        label = self._activity_label(event)

        if event_type == ACTIVITY_STARTED:
            self._close_activity_text()
            if label in self._TEXT_ACTIVITY_START_LABELS:
                return True
            self._activity_status_line(kind, label)
            return True

        if event_type == ACTIVITY_TEXT_SNAPSHOT:
            text = event.get("text")
            if not isinstance(text, str):
                return True
            self._close_activity_text()
            self._ensure_line_boundary()
            self._activity_text[activity_id] = text
            self._activity_text_seen.add(activity_id)
            self._activity_open_id = activity_id
            self._last_activity_status = None
            self._write(f"[{kind}] {text}")
            return True

        if event_type == ACTIVITY_TEXT_DELTA:
            delta = event.get("delta")
            if not isinstance(delta, str):
                return True
            if self._activity_open_id != activity_id:
                self._close_activity_text()
                self._ensure_line_boundary()
                self._activity_open_id = activity_id
                self._last_activity_status = None
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
            self._ensure_line_boundary()
            self._activity_text[activity_id] = text
            self._activity_text_seen.add(activity_id)
            self._activity_open_id = activity_id
            self._last_activity_status = None
            self._write(f"[{kind} revision]\n{text}")
            return True

        self._close_activity_text()
        if activity_id in self._activity_text_seen:
            return True
        if label in self._GENERIC_COMPLETION_LABELS:
            return True
        self._activity_status_line(kind, label)
        return True

    def _final_only_accepts(self, event: dict[str, Any]) -> bool:
        if not self.final_answer_only:
            return True

        message_id = self._message_id(event)
        channel = self._assistant_channel(event)

        if channel == "commentary":
            if message_id:
                self._final_only_suppressed_message_ids.add(message_id)
            return False

        if channel == "final":
            if self._final_only_active_message_id is None:
                self._final_only_active_message_id = message_id
            return (
                self._final_only_active_message_id is None
                or message_id is None
                or message_id == self._final_only_active_message_id
            )

        if self._final_only_active_message_id is not None:
            return message_id is None or message_id == self._final_only_active_message_id

        if self._final_only_activity_seen:
            if message_id is None or message_id not in self._final_only_suppressed_message_ids:
                self._final_only_active_message_id = message_id
                return True
            return False

        # Without an explicit channel or a product activity boundary, emitting
        # would risk leaking a commentary preamble. Fail closed; finish() will
        # still print canonical final text if no streamable final marker appears.
        if message_id:
            self._final_only_suppressed_message_ids.add(message_id)
        return False

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
            self._last_activity_status = None
            self.seen_text_event = True
            self._replace(text, label="canonical")
            return

        if not self._final_only_accepts(event):
            return

        normalized = self._accumulator.apply(event)
        if normalized is None:
            return

        self._close_activity_text()
        self._last_activity_status = None
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
        self._last_activity_status = None
        if not isinstance(canonical_text, str):
            canonical_text = str(canonical_text)
        self._replace(canonical_text, label="canonical")
        if not self._output_ends_with_newline:
            self._write("\n")
