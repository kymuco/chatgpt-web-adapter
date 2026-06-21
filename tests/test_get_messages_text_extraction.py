from __future__ import annotations

from webchat_adapter import ChatGPTWebClient


def _client(message: dict) -> ChatGPTWebClient:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "message-1",
        "mapping": {
            "message-1": {
                "id": "message-1",
                "parent": None,
                "message": message,
            }
        },
    }
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: payload
    return client


def _message(content: object, *, role: str = "user") -> dict:
    return {
        "id": "msg-1",
        "author": {"role": role},
        "content": content,
        "create_time": 1.0,
        "recipient": "all",
        "metadata": {},
    }


def test_get_messages_keeps_media_only_message_by_default() -> None:
    message = _message({"parts": [{"type": "image_asset_pointer"}]})

    messages = _client(message).get_messages("conversation-1")

    assert [message.text for message in messages] == ["[image]"]


def test_get_messages_filters_truly_empty_message_by_default() -> None:
    message = _message({"parts": [{"unknown": {"nested": 1}}]})

    messages = _client(message).get_messages("conversation-1")

    assert messages == []


def test_get_messages_include_empty_true_keeps_truly_empty_message() -> None:
    message = _message({"parts": [{"unknown": {"nested": 1}}]})

    messages = _client(message).get_messages("conversation-1", include_empty=True)

    assert len(messages) == 1
    assert messages[0].text == ""


def test_get_messages_does_not_crash_on_tool_message_without_text() -> None:
    message = _message({"result": {"ok": True}}, role="tool")

    messages = _client(message).get_messages("conversation-1", include_empty=True)

    assert len(messages) == 1
    assert messages[0].role == "tool"
    assert messages[0].text == ""
