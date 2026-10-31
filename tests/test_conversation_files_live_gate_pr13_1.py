from __future__ import annotations

import pytest

from tools.pr13_1_conversation_files_live_gate import conversation_id_from_selector


def test_raw_conversation_id_is_preserved() -> None:
    assert conversation_id_from_selector("conversation-123") == "conversation-123"


def test_chatgpt_conversation_url_extracts_id() -> None:
    assert (
        conversation_id_from_selector(
            "https://chatgpt.com/c/conversation-123?utm_source=fixture"
        )
        == "conversation-123"
    )


@pytest.mark.parametrize(
    "selector",
    [
        "https://chatgpt.com/g/g-p-6ade211b7c10819194ec0adbdc964fe3-cwa/c/conversation-456",
        "https://www.chatgpt.com/g/g-example/c/conversation-456/?model=gpt-6",
    ],
)
def test_project_chat_url_matches_shared_conversation_ref(selector: str) -> None:
    assert conversation_id_from_selector(selector) == "conversation-456"


def test_nested_chatgpt_route_extracts_single_c_segment() -> None:
    assert (
        conversation_id_from_selector(
            "https://chatgpt.com/g/g-fixture/c/conversation-456"
        )
        == "conversation-456"
    )


@pytest.mark.parametrize(
    "selector",
    [
        "http://chatgpt.com/c/conversation-123",
        "https://example.com/c/conversation-123",
        "https://chatgpt.com/share/conversation-123",
        "https://chatgpt.com/c/one/c/two",
        "https://chatgpt.com/other/c/conversation-123",
        "https://chatgpt.com/g/not-a-project/c/conversation-123",
        "https://chatgpt.com/g/g-example/c/conversation-123/extra",
    ],
)
def test_noncanonical_or_ambiguous_url_fails_closed(selector: str) -> None:
    with pytest.raises(ValueError, match="CHATGPT_CONVERSATION_URL_REQUIRED"):
        conversation_id_from_selector(selector)
