from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.cli as cli
from chatgpt_web_adapter.conversation_snapshot import (
    ConversationSnapshot,
    render_snapshot_context,
    snapshot_conversation,
)
from chatgpt_web_adapter.types import ChatMessage


class _SnapshotClient:
    def __init__(self, messages: list[ChatMessage], raw_payload: dict) -> None:
        self.messages = messages
        self.raw_payload = raw_payload
        self.message_calls = []
        self.payload_calls = []

    def get_messages(self, conversation, **kwargs):
        self.message_calls.append((conversation, kwargs))
        return list(self.messages)

    def _get_conversation_payload(self, conversation_id: str):
        self.payload_calls.append(conversation_id)
        return self.raw_payload


def test_render_snapshot_context_is_stable_and_ends_with_newline() -> None:
    output = render_snapshot_context(
        [
            ChatMessage(role="user", text="Hello"),
            ChatMessage(role="assistant", text="Hi"),
        ]
    )

    assert output == "## USER\n\nHello\n\n---\n\n## ASSISTANT\n\nHi\n"


def test_snapshot_filters_internal_assistant_messages_and_auto_numbers(tmp_path: Path) -> None:
    (tmp_path / "organism_lab_chat_context_1.md").write_text("old\n", encoding="utf-8")
    (tmp_path / "organism_lab_chat_context_3.md").write_text("old\n", encoding="utf-8")

    client = _SnapshotClient(
        [
            ChatMessage(role="user", text="  hello  "),
            ChatMessage(role="assistant", text="answer", recipient="all"),
            ChatMessage(role="assistant", text="internal", recipient="python"),
            ChatMessage(role="assistant", text="  final  ", recipient=None),
            ChatMessage(role="user", text="   "),
            ChatMessage(role="tool", text="tool output"),
        ],
        {
            "conversation_id": "conversation-1",
            "title": "Пример",
        },
    )

    result = snapshot_conversation(
        client,
        "https://chatgpt.com/c/conversation-1",
        output_dir=tmp_path,
        name="organism_lab",
    )

    assert result.conversation_id == "conversation-1"
    assert result.index == 4
    assert result.message_count == 3
    assert result.context_path == tmp_path / "organism_lab_chat_context_4.md"
    assert result.raw_payload_path == tmp_path / "organism_lab_chat_payload_4.json"
    assert result.context_path.read_text(encoding="utf-8") == (
        "## USER\n\nhello\n\n---\n\n"
        "## ASSISTANT\n\nanswer\n\n---\n\n"
        "## ASSISTANT\n\nfinal\n"
    )
    raw_text = result.raw_payload_path.read_text(encoding="utf-8")
    assert "Пример" in raw_text
    assert "\\u041f" not in raw_text
    assert json.loads(raw_text) == client.raw_payload
    assert client.message_calls == [
        (
            "https://chatgpt.com/c/conversation-1",
            {
                "limit": None,
                "roles": ("user", "assistant"),
                "include_empty": False,
            },
        )
    ]
    assert client.payload_calls == ["conversation-1"]


def test_snapshot_context_only_skips_raw_payload_request(tmp_path: Path) -> None:
    client = _SnapshotClient(
        [ChatMessage(role="user", text="Hello")],
        {"conversation_id": "conversation-1"},
    )

    result = snapshot_conversation(
        client,
        "conversation-1",
        output_dir=tmp_path,
        name="project",
        include_raw_payload=False,
    )

    assert result.raw_payload_path is None
    assert client.payload_calls == []
    assert result.context_path.exists()


def test_snapshot_explicit_index_never_overwrites_existing_context(tmp_path: Path) -> None:
    path = tmp_path / "project_chat_context_7.md"
    path.write_text("keep me\n", encoding="utf-8")
    client = _SnapshotClient([], {})

    with pytest.raises(FileExistsError, match="snapshot context already exists"):
        snapshot_conversation(
            client,
            "conversation-1",
            output_dir=tmp_path,
            name="project",
            index=7,
        )

    assert path.read_text(encoding="utf-8") == "keep me\n"
    assert client.message_calls == []


@pytest.mark.parametrize("name", ["", "..", "bad/name", "bad\\name", "bad:name"])
def test_snapshot_rejects_unsafe_file_names(tmp_path: Path, name: str) -> None:
    client = _SnapshotClient([], {})

    with pytest.raises((TypeError, ValueError)):
        snapshot_conversation(
            client,
            "conversation-1",
            output_dir=tmp_path,
            name=name,
        )


def test_snapshot_cli_replaces_manual_export_script(monkeypatch, capsys, tmp_path: Path) -> None:
    captured = {}
    fake_client = object()

    def fake_client_factory(**kwargs):
        captured["client_kwargs"] = kwargs
        return fake_client

    result = ConversationSnapshot(
        conversation_id="conversation-1",
        index=12,
        context_path=tmp_path / "organism_lab_chat_context_12.md",
        raw_payload_path=tmp_path / "organism_lab_chat_payload_12.json",
        message_count=27,
    )

    def fake_snapshot(client, conversation, **kwargs):
        captured["snapshot"] = (client, conversation, kwargs)
        return result

    monkeypatch.setattr(cli, "ChatGPTWebClient", fake_client_factory)
    monkeypatch.setattr(cli, "snapshot_conversation", fake_snapshot)

    code = cli.main(
        [
            "snapshot",
            "https://chatgpt.com/c/conversation-1",
            "--name",
            "organism_lab",
            "--output-dir",
            str(tmp_path),
            "--timeout",
            "45",
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert captured["client_kwargs"]["timeout"] == 45.0
    assert captured["snapshot"] == (
        fake_client,
        "https://chatgpt.com/c/conversation-1",
        {
            "output_dir": tmp_path,
            "name": "organism_lab",
            "index": None,
            "include_raw_payload": True,
        },
    )
    assert str(result.context_path.resolve()) in output
    assert str(result.raw_payload_path.resolve()) in output
    assert "messages:    27" in output


def test_snapshot_cli_context_only_forwards_raw_opt_out(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    monkeypatch.setattr(cli, "ChatGPTWebClient", lambda **kwargs: object())

    def fake_snapshot(client, conversation, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            context_path=tmp_path / "context.md",
            raw_payload_path=None,
            message_count=1,
        )

    monkeypatch.setattr(cli, "snapshot_conversation", fake_snapshot)

    code = cli.main(
        [
            "snapshot",
            "conversation-1",
            "--output-dir",
            str(tmp_path),
            "--context-only",
        ]
    )

    assert code == 0
    assert captured["include_raw_payload"] is False
