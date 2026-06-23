from __future__ import annotations

from chatgpt_web_adapter import ChatGPTWebClient


def _client(metadata: dict) -> ChatGPTWebClient:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "assistant-1",
        "mapping": {
            "assistant-1": {
                "id": "assistant-1",
                "parent": None,
                "message": {
                    "id": "msg-assistant-1",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Answer"]},
                    "create_time": 1.0,
                    "recipient": "all",
                    "metadata": metadata,
                },
            }
        },
    }
    client = object.__new__(ChatGPTWebClient)
    client._get_conversation_payload = lambda _conversation_id: payload
    return client


def test_get_messages_reads_model_slug_from_nested_model_container() -> None:
    messages = _client({"model": {"slug": "gpt-5-5-thinking"}}).get_messages(
        "conversation-1"
    )

    assert messages[0].model == "gpt-5-5-thinking"


def test_get_messages_reads_model_id_from_nested_selected_model_container() -> None:
    messages = _client({"selected_model": {"id": "gpt-4.1"}}).get_messages(
        "conversation-1"
    )

    assert messages[0].model == "gpt-4.1"


def test_get_messages_prefers_direct_model_slug_over_nested_container() -> None:
    messages = _client(
        {
            "model_slug": "direct-model",
            "model": {"slug": "nested-model"},
        }
    ).get_messages("conversation-1")

    assert messages[0].model == "direct-model"
