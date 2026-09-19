from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from chatgpt_web_adapter.browser_context_canonical_v2 import (
    BrowserContextCanonicalClientV2,
)
from chatgpt_web_adapter.browser_owned_product_transport import (
    BrowserOwnedProductTransport,
)
from chatgpt_web_adapter.conversation_read_v2 import (
    get_messages_v2,
    merge_conversation_pages,
    normalize_conversation_payload,
    read_conversation_payload_v2,
)
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.messages import get_messages
from chatgpt_web_adapter.status import _status_from_payload


def _message(
    message_id: str,
    role: str,
    text: str,
    *,
    finish: bool = False,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if finish:
        metadata["finish_details"] = {"type": "stop"}
    return {
        "id": message_id,
        "author": {"role": role},
        "recipient": "all",
        "create_time": float(message_id.strip("ua") or 0),
        "content": {"content_type": "text", "parts": [text]},
        "metadata": metadata,
        "end_turn": finish,
    }


def _legacy_payload(*message_ids: str) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for index, message_id in enumerate(message_ids):
        role = "assistant" if message_id.startswith("a") else "user"
        mapping[message_id] = {
            "id": message_id,
            "parent": message_ids[index - 1] if index else None,
            "children": [message_ids[index + 1]]
            if index + 1 < len(message_ids)
            else [],
            "message": _message(
                message_id,
                role,
                message_id,
                finish=index + 1 == len(message_ids) and role == "assistant",
            ),
        }
    return {
        "conversation_id": "conversation-1",
        "current_node": message_ids[-1] if message_ids else None,
        "mapping": mapping,
    }


def test_flat_messages_normalize_to_current_branch_mapping() -> None:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "a2",
        "messages": [
            _message("u1", "user", "hello"),
            _message("a2", "assistant", "done", finish=True),
        ],
        "page_info": {
            "has_previous_page": False,
            "has_next_page": False,
        },
    }

    normalized = normalize_conversation_payload(payload)

    assert normalized["current_node"] == "a2"
    assert normalized["mapping"]["u1"]["parent"] is None
    assert normalized["mapping"]["u1"]["children"] == ["a2"]
    assert normalized["mapping"]["a2"]["parent"] == "u1"
    assert normalized["mapping"]["a2"]["children"] == []
    assert _status_from_payload(normalized).status == "completed"

    class _Reader:
        def _get_conversation_payload(self, _conversation_id: str):
            return normalized

    messages = get_messages(_Reader(), "conversation-1")
    assert [(message.message_id, message.text) for message in messages] == [
        ("u1", "hello"),
        ("a2", "done"),
    ]


def test_nested_flat_items_translate_current_node_alias_without_guessing() -> None:
    payload = {
        "conversation_id": "conversation-1",
        "current_node": "node-a2",
        "messages": [
            {"id": "node-u1", "message": _message("u1", "user", "hello")},
            {
                "id": "node-a2",
                "message": _message("a2", "assistant", "done", finish=True),
            },
        ],
    }

    normalized = normalize_conversation_payload(payload)

    assert normalized["current_node"] == "a2"
    assert list(normalized["mapping"]) == ["u1", "a2"]


def test_flat_shape_fails_closed_on_duplicate_or_unbound_current_node() -> None:
    duplicate = {
        "messages": [
            _message("u1", "user", "one"),
            _message("u1", "user", "two"),
        ]
    }
    with pytest.raises(RequestError, match="duplicate message id"):
        normalize_conversation_payload(duplicate)

    unbound = {
        "current_node": "missing",
        "messages": [_message("u1", "user", "one")],
    }
    with pytest.raises(RequestError, match="current_node"):
        normalize_conversation_payload(unbound)


def test_paginated_pages_merge_oldest_first_and_dedupe_overlap() -> None:
    latest = {
        "conversation_id": "conversation-1",
        "current_node": "a4",
        "messages": [
            _message("u3", "user", "three"),
            _message("a4", "assistant", "four", finish=True),
        ],
        "page_info": {
            "has_previous_page": True,
            "start_cursor": "cursor-2",
        },
    }
    older = {
        "conversation_id": "conversation-1",
        "messages": [
            _message("u1", "user", "one"),
            _message("a2", "assistant", "two"),
            _message("u3", "user", "three"),
        ],
        "page_info": {"has_previous_page": False},
    }

    merged = merge_conversation_pages([latest, older])
    normalized = normalize_conversation_payload(merged)

    assert list(normalized["mapping"]) == ["u1", "a2", "u3", "a4"]
    assert normalized["current_node"] == "a4"


class _RequestClient:
    def __init__(self, responses: list[tuple[int, Any]]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def _build_headers(self, additions: dict[str, str]) -> dict[str, str]:
        return dict(additions)

    def _json_request(self, method, url, payload, headers):
        assert method == "GET"
        assert payload is None
        assert headers["accept"] == "application/json"
        self.urls.append(url)
        return self.responses.pop(0)


def test_current_endpoint_paginates_with_before_cursor() -> None:
    latest = {
        "conversation_id": "conversation-1",
        "current_node": "a4",
        "messages": [
            _message("u3", "user", "three"),
            _message("a4", "assistant", "four", finish=True),
        ],
        "page_info": {
            "has_previous_page": True,
            "start_cursor": "cursor-2",
        },
    }
    older = {
        "conversation_id": "conversation-1",
        "messages": [
            _message("u1", "user", "one"),
            _message("a2", "assistant", "two"),
        ],
        "page_info": {"has_previous_page": False},
    }
    client = _RequestClient([(200, latest), (200, older)])

    payload = read_conversation_payload_v2(
        client,
        "conversation-1",
        current_base_url="https://chatgpt.com/backend-api/conversations",
        legacy_url_template=(
            "https://chatgpt.com/backend-api/conversation/{conversation_id}"
        ),
        include_all_pages=True,
    )

    assert list(payload["mapping"]) == ["u1", "a2", "u3", "a4"]
    assert len(client.urls) == 2
    first = urlparse(client.urls[0])
    second = urlparse(client.urls[1])
    assert first.path == "/backend-api/conversations/conversation-1"
    assert parse_qs(first.query) == {
        "include_has_versions": ["true"],
        "num_turns": ["20"],
    }
    assert parse_qs(second.query)["before"] == ["cursor-2"]


def test_only_current_404_authorizes_legacy_endpoint_fallback() -> None:
    client = _RequestClient(
        [(404, {"detail": "missing"}), (200, _legacy_payload("u1", "a2"))]
    )

    payload = read_conversation_payload_v2(
        client,
        "conversation-1",
        current_base_url="https://chatgpt.com/backend-api/conversations",
        legacy_url_template=(
            "https://chatgpt.com/backend-api/conversation/{conversation_id}"
        ),
    )

    assert payload["current_node"] == "a2"
    assert len(client.urls) == 2
    assert urlparse(client.urls[1]).path == "/backend-api/conversation/conversation-1"


@pytest.mark.parametrize("status", [401, 403, 422, 500])
def test_current_non_404_failure_never_falls_back_to_legacy(status: int) -> None:
    client = _RequestClient([(status, {"detail": "no"})])

    with pytest.raises(RequestError) as captured:
        read_conversation_payload_v2(
            client,
            "conversation-1",
            current_base_url="https://chatgpt.com/backend-api/conversations",
            legacy_url_template=(
                "https://chatgpt.com/backend-api/conversation/{conversation_id}"
            ),
        )

    assert captured.value.status_code == status
    assert len(client.urls) == 1


def test_message_limit_uses_latest_page_when_it_already_satisfies_limit() -> None:
    class _Reader:
        def __init__(self):
            self.latest_reads = 0
            self.full_reads = 0

        def _get_conversation_payload(self, _conversation_id: str):
            self.latest_reads += 1
            return {
                **_legacy_payload("u3", "a4"),
                "page_info": {"has_previous_page": True},
            }

        def _get_full_conversation_payload(self, _conversation_id: str):
            self.full_reads += 1
            return _legacy_payload("u1", "a2", "u3", "a4")

    reader = _Reader()

    bounded = get_messages_v2(reader, "conversation-1", limit=1)
    assert [message.message_id for message in bounded] == ["a4"]
    assert (reader.latest_reads, reader.full_reads) == (1, 0)

    unbounded = get_messages_v2(reader, "conversation-1")
    assert [message.message_id for message in unbounded] == ["u1", "a2", "u3", "a4"]
    assert (reader.latest_reads, reader.full_reads) == (1, 1)

    empty = get_messages_v2(reader, "conversation-1", limit=0)
    assert empty == []
    assert (reader.latest_reads, reader.full_reads) == (1, 1)


def test_message_limit_uses_full_reader_when_latest_page_is_insufficient() -> None:
    class _Reader:
        def __init__(self):
            self.latest_reads = 0
            self.full_reads = 0

        def _get_conversation_payload(self, _conversation_id: str):
            self.latest_reads += 1
            return {
                **_legacy_payload("u3", "a4"),
                "page_info": {"has_previous_page": True},
            }

        def _get_full_conversation_payload(self, _conversation_id: str):
            self.full_reads += 1
            return _legacy_payload("u1", "a2", "u3", "a4")

    reader = _Reader()
    messages = get_messages_v2(reader, "conversation-1", limit=3)

    assert [message.message_id for message in messages] == ["a2", "u3", "a4"]
    assert (reader.latest_reads, reader.full_reads) == (1, 1)


def test_browser_context_v2_exposes_complete_first_class_snapshot() -> None:
    class _Provider:
        connect_timeout = 1.0

        def _load_descriptor(self):
            raise AssertionError("wire transport is replaced for this unit test")

    class _Source:
        pass

    client = BrowserContextCanonicalClientV2(_Source(), _Provider())
    client._get_full_conversation_payload = lambda _conversation_id: _legacy_payload(
        "u1",
        "a2",
    )

    snapshot = client.get_conversation_snapshot("conversation-1")

    assert snapshot.conversation_id == "conversation-1"
    assert snapshot.complete is True
    assert [message.message_id for message in snapshot.messages] == ["u1", "a2"]


def test_default_browser_owned_transport_uses_v2_canonical_client() -> None:
    class _Canonical:
        def get_status(self, conversation):
            raise AssertionError("not used")

        def get_messages(self, conversation, **kwargs):
            raise AssertionError("not used")

        def attach_conversation(self, conversation):
            raise AssertionError("not used")

    transport = BrowserOwnedProductTransport(_Canonical())

    assert isinstance(transport.canonical_client, BrowserContextCanonicalClientV2)
