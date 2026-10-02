from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from chatgpt_web_adapter.conversation_snapshot import snapshot_conversation
from chatgpt_web_adapter.export import write_conversation_export
from chatgpt_web_adapter.types import ChatMessage

_IS_POSIX = os.name != "nt"


class _ArtifactClient:
    """Minimal client: snapshot and export only read messages and a raw payload."""

    def __init__(self, messages: list[ChatMessage], raw_payload: dict) -> None:
        self.messages = messages
        self.raw_payload = raw_payload

    def get_messages(self, conversation, **kwargs):
        return list(self.messages)

    def _get_conversation_payload(self, conversation_id: str):
        return self.raw_payload


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.skipif(not _IS_POSIX, reason="POSIX permission semantics")
def test_snapshot_artifacts_are_owner_only_on_posix(tmp_path: Path) -> None:
    """The raw canonical payload can carry sensitive conversation data, so new snapshot
    artifacts (context, payload, manifest) must default to 0600 on POSIX - the same
    posture auth_store applies to auth material (issue #170)."""
    client = _ArtifactClient(
        [ChatMessage(role="user", text="Hello")],
        {"conversation_id": "conversation-1", "secret": "payload"},
    )

    result = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
    )

    for path in (result.context_path, result.raw_payload_path, result.manifest_path):
        assert _mode(path) == 0o600
    # contents are untouched: the context still renders and the payload round-trips
    assert result.context_path.read_text(encoding="utf-8") == "## USER\n\nHello\n"
    assert result.raw_payload_path.read_text(encoding="utf-8").startswith("{")


@pytest.mark.skipif(not _IS_POSIX, reason="POSIX permission semantics")
def test_export_artifacts_are_owner_only_on_posix(tmp_path: Path) -> None:
    """Exports and their manifests carry the same conversation content, so they default
    to owner-only permissions on POSIX as well (issue #170)."""
    client = _ArtifactClient([ChatMessage(role="user", text="Hello")], {})

    result = write_conversation_export(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
    )

    for path in (result.export_path, result.manifest_path):
        assert _mode(path) == 0o600
    assert result.export_path.read_text(encoding="utf-8") == "## User\n\nHello"
