from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.cli_v02 as cli
from chatgpt_web_adapter.artifact_manifest import (
    ARTIFACT_MANIFEST_SCHEMA,
    ArtifactFileEntry,
    StableArtifactManifest,
    artifact_file_entry,
    render_artifact_manifest,
)
from chatgpt_web_adapter.conversation_snapshot import snapshot_conversation
from chatgpt_web_adapter.export import write_conversation_export
from chatgpt_web_adapter.types import ChatMessage, ConversationRef


class _ArtifactClient:
    def __init__(self, messages: list[ChatMessage], raw_payload: dict | None = None) -> None:
        self.messages = list(messages)
        self.raw_payload = raw_payload or {"conversation_id": "conversation-1"}
        self.message_calls = []
        self.payload_calls = []

    def get_messages(self, conversation, **kwargs):
        self.message_calls.append((conversation, kwargs))
        return list(self.messages)

    def _get_conversation_payload(self, conversation_id: str):
        self.payload_calls.append(conversation_id)
        return dict(self.raw_payload)


def _manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_render_is_deterministic_and_has_no_timestamp() -> None:
    manifest = StableArtifactManifest(
        artifact_kind="conversation_export",
        contract="normalized_current_branch_export_v1",
        conversation_id="conversation-1",
        index=2,
        format="jsonl",
        files=(
            ArtifactFileEntry(
                role="export",
                path="project_chat_export_2.jsonl",
                media_type="application/x-ndjson; charset=utf-8",
                bytes=12,
                sha256="a" * 64,
            ),
        ),
    )

    first = render_artifact_manifest(manifest)
    second = render_artifact_manifest(manifest)

    assert first == second
    assert first.endswith("\n")
    payload = json.loads(first)
    assert payload["schema"] == ARTIFACT_MANIFEST_SCHEMA == 1
    assert "timestamp" not in payload
    assert "created_at" not in payload


def test_artifact_file_entry_hashes_exact_bytes(tmp_path: Path) -> None:
    path = tmp_path / "artifact.txt"
    path.write_bytes("Привет\n".encode("utf-8"))

    entry = artifact_file_entry(path, role="export", media_type="text/plain; charset=utf-8")

    payload = path.read_bytes()
    assert entry.path == "artifact.txt"
    assert entry.bytes == len(payload)
    assert entry.sha256 == hashlib.sha256(payload).hexdigest()


def test_snapshot_writes_manifest_last_with_context_and_raw_hashes(tmp_path: Path) -> None:
    client = _ArtifactClient(
        [
            ChatMessage(role="user", text="Hello"),
            ChatMessage(role="assistant", text="Hi", recipient="all"),
            ChatMessage(role="assistant", text="internal", recipient="python"),
        ],
        {"conversation_id": "conversation-1", "title": "Example"},
    )

    result = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        index=7,
    )

    assert result.manifest_path == tmp_path / "project_chat_snapshot_7.manifest.json"
    payload = _manifest(result.manifest_path)
    assert payload["artifact_kind"] == "conversation_snapshot"
    assert payload["contract"] == "curated_current_branch_context_v1"
    assert payload["conversation_id"] == "conversation-1"
    assert payload["index"] == 7
    assert payload["format"] is None
    assert [item["role"] for item in payload["files"]] == ["context", "raw_payload"]
    by_role = {item["role"]: item for item in payload["files"]}
    assert by_role["context"]["sha256"] == hashlib.sha256(result.context_path.read_bytes()).hexdigest()
    assert by_role["raw_payload"]["sha256"] == hashlib.sha256(result.raw_payload_path.read_bytes()).hexdigest()
    assert result.message_count == 2


def test_context_only_snapshot_manifest_contains_only_context(tmp_path: Path) -> None:
    client = _ArtifactClient([ChatMessage(role="user", text="Hello")])

    result = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        include_raw_payload=False,
    )

    payload = _manifest(result.manifest_path)
    assert result.raw_payload_path is None
    assert client.payload_calls == []
    assert [item["role"] for item in payload["files"]] == ["context"]


def test_snapshot_manifest_collision_fails_before_canonical_reads(tmp_path: Path) -> None:
    (tmp_path / "project_chat_snapshot_3.manifest.json").write_text("{}\n", encoding="utf-8")
    client = _ArtifactClient([])

    with pytest.raises(FileExistsError, match="snapshot manifest already exists"):
        snapshot_conversation(
            client,
            "conversation-1",
            output_dir=tmp_path,
            name="project",
            index=3,
        )

    assert client.message_calls == []
    assert client.payload_calls == []


def test_export_writer_creates_portable_file_and_manifest(tmp_path: Path) -> None:
    client = _ArtifactClient(
        [
            ChatMessage(role="user", text="Hello"),
            ChatMessage(role="assistant", text="Hi"),
        ]
    )

    result = write_conversation_export(
        client,
        "https://chatgpt.com/c/conversation-1",
        output_dir=tmp_path,
        name="project",
        index=4,
        format="md",
    )

    assert result.conversation_id == "conversation-1"
    assert result.index == 4
    assert result.format == "markdown"
    assert result.export_path == tmp_path / "project_chat_export_4.md"
    assert result.export_path.read_text(encoding="utf-8") == "## User\n\nHello\n\n## Assistant\n\nHi"
    assert result.manifest_path == tmp_path / "project_chat_export_4.manifest.json"
    payload = _manifest(result.manifest_path)
    assert payload["artifact_kind"] == "conversation_export"
    assert payload["contract"] == "normalized_current_branch_export_v1"
    assert payload["format"] == "markdown"
    assert payload["files"][0]["path"] == "project_chat_export_4.md"
    assert payload["files"][0]["media_type"] == "text/markdown; charset=utf-8"
    assert result.message_count == 2


def test_export_auto_index_uses_manifest_sequence_across_formats(tmp_path: Path) -> None:
    client = _ArtifactClient([ChatMessage(role="user", text="Hello")])
    (tmp_path / "project_chat_export_2.manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "project_chat_export_5.manifest.json").write_text("{}\n", encoding="utf-8")

    result = write_conversation_export(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        format="jsonl",
    )

    assert result.index == 6
    assert result.export_path.name == "project_chat_export_6.jsonl"
    assert result.manifest_path.name == "project_chat_export_6.manifest.json"


def test_export_manifest_collision_fails_before_canonical_read(tmp_path: Path) -> None:
    (tmp_path / "project_chat_export_9.manifest.json").write_text("{}\n", encoding="utf-8")
    client = _ArtifactClient([])

    with pytest.raises(FileExistsError, match="export manifest already exists"):
        write_conversation_export(
            client,
            "conversation-1",
            output_dir=tmp_path,
            name="project",
            index=9,
            format="txt",
        )

    assert client.message_calls == []


def test_export_writer_uses_normalized_current_branch_read_contract(tmp_path: Path) -> None:
    client = _ArtifactClient([ChatMessage(role="tool", text="")])

    write_conversation_export(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        format="txt",
    )

    conversation, kwargs = client.message_calls[0]
    assert isinstance(conversation, ConversationRef)
    assert conversation.conversation_id == "conversation-1"
    assert kwargs == {"limit": None, "include_empty": True}


def test_snapshot_cli_json_embeds_stable_manifest(monkeypatch, capsys, tmp_path: Path) -> None:
    context_path = tmp_path / "project_chat_context_2.md"
    raw_path = tmp_path / "project_chat_payload_2.json"
    manifest_path = tmp_path / "project_chat_snapshot_2.manifest.json"
    context_path.write_text("## USER\n\nHello\n", encoding="utf-8")
    raw_path.write_text("{}\n", encoding="utf-8")
    manifest_payload = {
        "schema": 1,
        "artifact_kind": "conversation_snapshot",
        "contract": "curated_current_branch_context_v1",
        "conversation_id": "conversation-1",
        "index": 2,
        "format": None,
        "files": [],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    monkeypatch.setattr(cli.legacy_cli, "ChatGPTWebClient", lambda **kwargs: object())
    monkeypatch.setattr(
        cli,
        "snapshot_conversation",
        lambda *args, **kwargs: SimpleNamespace(
            conversation_id="conversation-1",
            index=2,
            context_path=context_path,
            raw_payload_path=raw_path,
            manifest_path=manifest_path,
            message_count=2,
        ),
    )

    code = cli.main(["snapshot", "conversation-1", "--output-dir", str(tmp_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["command"] == "snapshot"
    assert payload["ok"] is True
    assert payload["manifest"] == manifest_payload
    assert payload["paths"]["context"].endswith("project_chat_context_2.md")
    assert payload["paths"]["raw_payload"].endswith("project_chat_payload_2.json")


def test_export_cli_json_uses_same_artifact_envelope(monkeypatch, capsys, tmp_path: Path) -> None:
    export_path = tmp_path / "project_chat_export_3.jsonl"
    manifest_path = tmp_path / "project_chat_export_3.manifest.json"
    export_path.write_text("{}", encoding="utf-8")
    manifest_payload = {
        "schema": 1,
        "artifact_kind": "conversation_export",
        "contract": "normalized_current_branch_export_v1",
        "conversation_id": "conversation-1",
        "index": 3,
        "format": "jsonl",
        "files": [],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    monkeypatch.setattr(cli.legacy_cli, "ChatGPTWebClient", lambda **kwargs: object())
    monkeypatch.setattr(
        cli,
        "write_conversation_export",
        lambda *args, **kwargs: SimpleNamespace(
            conversation_id="conversation-1",
            index=3,
            format="jsonl",
            export_path=export_path,
            manifest_path=manifest_path,
            message_count=1,
        ),
    )

    code = cli.main(
        [
            "export",
            "conversation-1",
            "--format",
            "jsonl",
            "--name",
            "project",
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["command"] == "export"
    assert payload["format"] == "jsonl"
    assert payload["manifest"] == manifest_payload
    assert payload["paths"]["export"].endswith("project_chat_export_3.jsonl")


def test_snapshot_and_export_contracts_remain_distinct(tmp_path: Path) -> None:
    client = _ArtifactClient([ChatMessage(role="user", text="Hello")])

    snapshot = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        index=1,
        include_raw_payload=False,
    )
    exported = write_conversation_export(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        index=1,
        format="markdown",
    )

    snapshot_manifest = _manifest(snapshot.manifest_path)
    export_manifest = _manifest(exported.manifest_path)
    assert snapshot_manifest["artifact_kind"] == "conversation_snapshot"
    assert export_manifest["artifact_kind"] == "conversation_export"
    assert snapshot_manifest["contract"] != export_manifest["contract"]
    assert snapshot.context_path.name != exported.export_path.name
