from __future__ import annotations

import sys
from typing import Any, TextIO

from .revision_safe_streaming_pr8_9 import (
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
    """Render PR8.9 revision-safe text events without pretending they are tokens.

    Append-only extensions are written as suffixes. A non-prefix revision starts a
    fresh labelled block so terminal output remains truthful even when already
    printed text cannot be erased portably. Sequence validation and duplicate
    suppression reuse the proven PR8.9 accumulator. Canonical final text is always
    allowed to supersede the provisional stream.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.text = ""
        self.seen_text_event = False
        self._finished = False
        self._accumulator = RevisionSafeTextAccumulator()

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

    def on_event(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        event_type = event.get("type")

        if event_type == CANONICAL_TEXT_FINALIZED:
            text = event.get("text")
            if not isinstance(text, str):
                return
            self.seen_text_event = True
            self._replace(text, label="canonical")
            return

        normalized = self._accumulator.apply(event)
        if normalized is None:
            return

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
        if not isinstance(canonical_text, str):
            canonical_text = str(canonical_text)
        self._replace(canonical_text, label="canonical")
        if not self.text.endswith("\n"):
            self._write("\n")
