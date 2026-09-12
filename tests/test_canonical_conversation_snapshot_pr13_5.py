from __future__ import annotations

import json
from pathlib import Path

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.canonical_conversation_snapshot import (
    canonical_snapshot_from_payload,
)
from chatgpt_web_adapter.conversation_snapshot import snapshot_conversation


def _canonical_payload() -> dict:
    return {
        "conversation_id": "conversation-1",
        "title": "Snapshot example",
        "current_node": "assistant-1",
        "mapping": {
            "user-1": {
                "id": "user-1",
                "parent": None,
                "children": ["assistant-1"],
                "message": {
                    "id": "user-message-1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Hello"]},
                },
            },
            "assistant-1": {
                "id": "assistant-1",
                "parent": "user-1",
                "children": [],
                "message": {
                    "id": "assistant-message-1",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": ["Hi"]},
                },
            },
        },
    }


def test_web_client_snapshot_reads_full_payload_once_and_exposes_stable_projection() -> (
    None
):
    client = adapter.ChatGPTWebClient.__new__(adapter.ChatGPTWebClient)
    calls: list[str] = []
    payload = _canonical_payload()

    def full_reader(conversation_id: str) -> dict:
        calls.append(conversation_id)
        return payload

    client._get_full_conversation_payload = full_reader

    snapshot = client.get_conversation_snapshot("https://chatgpt.com/c/conversation-1")

    assert calls == ["conversation-1"]
    assert isinstance(snapshot, adapter.CanonicalConversationSnapshot)
    assert snapshot.conversation_id == "conversation-1"
    assert snapshot.title == "Snapshot example"
    assert snapshot.current_node == "assistant-1"
    assert snapshot.complete is True
    assert snapshot.message_count == 2
    assert [message.text for message in snapshot.messages] == ["Hello", "Hi"]
    assert snapshot.provenance.canonical_record_count == 2

    stable = snapshot.to_dict()
    assert stable["schema"] == adapter.CANONICAL_CONVERSATION_SNAPSHOT_SCHEMA
    assert stable["complete"] is True
    assert stable["message_count"] == 2
    assert [message["role"] for message in stable["messages"]] == [
        "user",
        "assistant",
    ]
    assert "mapping" not in stable


def test_canonical_payload_escape_hatch_is_complete_and_defensively_copied() -> None:
    payload = _canonical_payload()
    snapshot = canonical_snapshot_from_payload("conversation-1", payload)

    first = snapshot.to_canonical_payload()
    first["title"] = "mutated"
    first["mapping"].clear()

    second = snapshot.to_canonical_payload()
    assert second["title"] == "Snapshot example"
    assert len(second["mapping"]) == 2
    assert payload["title"] == "Snapshot example"
    assert len(payload["mapping"]) == 2


def test_runtime_exposes_first_class_snapshot_without_transport_details() -> None:
    snapshot = canonical_snapshot_from_payload("conversation-1", _canonical_payload())

    class _Canonical:
        def get_conversation_snapshot(self, conversation):
            assert conversation == "conversation-1"
            return snapshot

    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = _Canonical()

    assert runtime.get_conversation_snapshot("conversation-1") is snapshot


def test_runtime_snapshot_fails_clearly_for_legacy_injected_canonical_client() -> None:
    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = object()

    try:
        runtime.get_conversation_snapshot("conversation-1")
    except TypeError as error:
        assert "get_conversation_snapshot" in str(error)
    else:
        raise AssertionError("expected legacy canonical client to fail explicitly")


def test_file_snapshot_reuses_first_class_snapshot_instead_of_double_read(
    tmp_path: Path,
) -> None:
    snapshot = canonical_snapshot_from_payload("conversation-1", _canonical_payload())

    class _FirstClassClient:
        def __init__(self) -> None:
            self.calls = 0

        def get_conversation_snapshot(self, conversation):
            self.calls += 1
            assert conversation == "conversation-1"
            return snapshot

        def get_messages(self, *args, **kwargs):
            raise AssertionError(
                "first-class snapshot must avoid a second message read"
            )

        def _get_full_conversation_payload(self, *args, **kwargs):
            raise AssertionError(
                "first-class snapshot must avoid a second payload read"
            )

    client = _FirstClassClient()
    result = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
    )

    assert client.calls == 1
    assert result.message_count == 2
    assert result.context_path.read_text(encoding="utf-8") == (
        "## USER\n\nHello\n\n---\n\n## ASSISTANT\n\nHi\n"
    )
    raw_payload = json.loads(result.raw_payload_path.read_text(encoding="utf-8"))
    assert raw_payload == _canonical_payload()


def test_snapshot_types_are_root_exported_shared_support() -> None:
    expected = (
        "CANONICAL_CONVERSATION_SNAPSHOT_SCHEMA",
        "CanonicalConversationSnapshot",
        "ConversationReadProvenance",
    )
    for name in expected:
        assert name in adapter.__all__
        assert hasattr(adapter, name)
        assert (
            adapter.public_surface_tier(name)
            is adapter.PublicSurfaceTier.SHARED_SUPPORT
        )


def test_snapshot_capability_protocol_is_additive_and_primary() -> None:
    snapshot = canonical_snapshot_from_payload("conversation-1", _canonical_payload())

    class _SnapshotCapability:
        def get_conversation_snapshot(self, conversation):
            return snapshot

    assert isinstance(
        _SnapshotCapability(), adapter.CanonicalConversationSnapshotClient
    )
    assert "CanonicalConversationSnapshotClient" in adapter.__all__
    assert (
        adapter.public_surface_tier("CanonicalConversationSnapshotClient")
        is adapter.PublicSurfaceTier.PRIMARY_PRODUCTION
    )
