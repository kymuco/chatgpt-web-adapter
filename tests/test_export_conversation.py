from __future__ import annotations

import json

import pytest

from chatgpt_web_adapter import ChatGPTWebClient, ChatMessage


def _client(messages: list[ChatMessage]) -> ChatGPTWebClient:
    client = object.__new__(ChatGPTWebClient)
    client.get_messages = lambda _url_or_id, *, limit, include_empty: messages
    return client


def test_export_conversation_method_is_available() -> None:
    assert hasattr(ChatGPTWebClient, "export_conversation")


def test_export_conversation_markdown_formats_messages() -> None:
    client = _client(
        [
            ChatMessage(role="user", text="Hello"),
            ChatMessage(role="assistant", text="Hi"),
        ]
    )

    output = client.export_conversation("conversation-1", format="markdown")

    assert output == "## User\n\nHello\n\n## Assistant\n\nHi"


def test_export_conversation_txt_formats_messages() -> None:
    client = _client(
        [
            ChatMessage(role="user", text="Hello"),
            ChatMessage(role="assistant", text="Hi"),
        ]
    )

    output = client.export_conversation("conversation-1", format="txt")

    assert output == "User:\nHello\n\nAssistant:\nHi"


def test_export_conversation_jsonl_formats_messages() -> None:
    messages = [
        ChatMessage(
            node_id="node-user",
            message_id="msg-user",
            role="user",
            text="Hello",
            create_time=1.0,
            recipient="all",
        ),
        ChatMessage(
            node_id="node-assistant",
            message_id="msg-assistant",
            role="assistant",
            text="Hi",
            create_time=2.0,
            recipient="all",
            model="gpt-5-5-thinking",
            finish_reason="stop",
            metadata_preview={"finish_details": {"type": "stop"}},
        ),
    ]
    client = _client(messages)

    output = client.export_conversation("conversation-1", format="jsonl")
    lines = output.splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == messages[0].to_dict()
    assert json.loads(lines[1]) == messages[1].to_dict()


def test_export_conversation_jsonl_preserves_unicode() -> None:
    client = _client([ChatMessage(role="user", text="РџСЂРёРІРµС‚ гЃ“г‚“гЃ«гЃЎгЃЇ")])

    output = client.export_conversation("conversation-1", format="jsonl")

    assert "РџСЂРёРІРµС‚ гЃ“г‚“гЃ«гЃЎгЃЇ" in output
    assert "\\u041f" not in output


def test_export_conversation_format_aliases() -> None:
    client = _client([ChatMessage(role="user", text="Hello")])

    assert client.export_conversation("conversation-1", format="md") == "## User\n\nHello"
    assert client.export_conversation("conversation-1", format="text") == "User:\nHello"


def test_export_conversation_default_format_is_markdown() -> None:
    client = _client([ChatMessage(role="user", text="Hello")])

    assert client.export_conversation("conversation-1") == "## User\n\nHello"


def test_export_conversation_unsupported_format_raises_value_error() -> None:
    client = _client([])

    with pytest.raises(ValueError, match="unsupported export format"):
        client.export_conversation("conversation-1", format="html")


def test_export_conversation_non_string_format_raises_type_error() -> None:
    client = _client([])

    with pytest.raises(TypeError, match="format must be a string"):
        client.export_conversation("conversation-1", format=None)


def test_export_conversation_calls_get_messages_with_export_defaults() -> None:
    client = object.__new__(ChatGPTWebClient)
    calls = []

    def get_messages(url_or_id: str, *, limit: int | None, include_empty: bool):
        calls.append((url_or_id, limit, include_empty))
        return [ChatMessage(role="user", text="Hello")]

    client.get_messages = get_messages

    output = client.export_conversation("conversation-1", format="txt")

    assert output == "User:\nHello"
    assert calls == [("conversation-1", None, True)]


def test_export_conversation_markdown_and_txt_render_empty_text_as_placeholder() -> None:
    client = _client([ChatMessage(role="tool", text="")])

    assert client.export_conversation("conversation-1", format="markdown") == "## Tool\n\n[empty]"
    assert client.export_conversation("conversation-1", format="txt") == "Tool:\n[empty]"


def test_export_conversation_jsonl_keeps_empty_text_empty() -> None:
    client = _client([ChatMessage(role="tool", text="")])

    output = client.export_conversation("conversation-1", format="jsonl")

    assert json.loads(output)["text"] == ""


def test_export_conversation_role_label_fallbacks() -> None:
    client = _client(
        [
            ChatMessage(role=None, text="No role"),
            ChatMessage(role="custom_role", text="Custom"),
            ChatMessage(role="assistant\n# injected", text="Safe label"),
        ]
    )

    output = client.export_conversation("conversation-1", format="txt")

    assert output == (
        "Message:\nNo role\n\n"
        "Custom Role:\nCustom\n\n"
        "Assistant # Injected:\nSafe label"
    )


def test_export_conversation_empty_message_list_returns_empty_string() -> None:
    client = _client([])

    assert client.export_conversation("conversation-1", format="markdown") == ""
    assert client.export_conversation("conversation-1", format="txt") == ""
    assert client.export_conversation("conversation-1", format="jsonl") == ""
