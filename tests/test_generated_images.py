"""Offline, read-only generated-image correlation (never sends a turn)."""

from __future__ import annotations

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.generated_images import GeneratedImageObservation


def _payload(*, parts=None, marker=True, alternate=False):
    image = {
        "content_type": "image_asset_pointer",
        "asset_pointer": "sediment://opaque-private-value",
        "mime_type": "image/png",
        "width": 1254,
        "height": 1254,
        "size_bytes": 3150084,
    }
    tool = {
        "id": "tool-image-1",
        "author": {"role": "tool", "name": "opaque.image.tool"},
        "content": {"content_type": "multimodal_text", "parts": parts or [image]},
        "metadata": {"image_gen_title": "Generated image"} if marker else {},
    }
    final = {
        "id": "final-1",
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": [""]},
    }
    mapping = {
        "tool": {
            "parent": None,
            "message": tool,
        },
        "final": {
            "parent": "tool",
            "message": final,
        },
    }
    if alternate:
        mapping["unselected"] = {
            "parent": None,
            "message": {
                **tool,
                "id": "other-tool",
            },
        }
    return {"mapping": mapping, "current_node": "final"}


def _file(**overrides):
    value = {
        "origination_message_id": "tool-image-1",
        "file_id": "file-image-1",
        "file_name": "generated.png",
        "file_size_bytes": 3150084,
        "mime_type": "image/png",
        "state": "ready",
        "image_gen_attribution": {"is_delayed": False},
    }
    value.update(overrides)
    return value


def _client(monkeypatch, cls, payload, files=None, *, status=200):
    client = object.__new__(cls)
    calls = []

    def history(cid):
        calls.append(("history", cid))
        return payload

    def read(_client, *, url, headers, stage):
        assert url.endswith("/conversation-1/files")
        assert headers == {"accept": "application/json"}
        assert stage == "discovery"
        calls.append(("files", url))
        return status, {"files": files if files is not None else [_file()]}

    client._get_full_conversation_payload = history
    client._build_headers = lambda _extra: {"accept": "application/json"}
    client.send = lambda *_args, **_kwargs: pytest.fail("never send")
    monkeypatch.setattr("chatgpt_web_adapter.generated_images._json_get", read)
    return client, calls


@pytest.mark.parametrize("cls", [ChatGPTWebClient, BrowserlessHTTPClient])
def test_one_realistic_generated_image_correlates_to_owned_file(monkeypatch, cls):
    client, calls = _client(monkeypatch, cls, _payload())

    images = client.get_generated_images("conversation-1")

    assert images == [
        GeneratedImageObservation(
            "conversation-1",
            "tool-image-1",
            "generated.png",
            "image/png",
            1254,
            1254,
            3150084,
        )
    ]
    assert [kind for kind, _ in calls] == ["history", "files"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"origination_message_id": "other-message"},
        {"file_size_bytes": 3150085},
        {"mime_type": "image/webp"},
        {"state": "processing"},
        {"file_id": None},
        {"image_gen_attribution": None},
    ],
)
def test_unproven_file_correlation_never_promotes_to_image(monkeypatch, kwargs):
    client, _ = _client(monkeypatch, ChatGPTWebClient, _payload(), [_file(**kwargs)])
    assert client.get_generated_images("conversation-1") == []


def test_ambiguous_file_matches_fail_closed(monkeypatch):
    client, _ = _client(
        monkeypatch,
        ChatGPTWebClient,
        _payload(),
        [_file(), _file(file_id="file-image-2", file_name="second.png")],
    )
    assert client.get_generated_images("conversation-1") == []


def test_duplicate_name_fails_even_if_one_origin_matches(monkeypatch):
    client, _ = _client(
        monkeypatch,
        ChatGPTWebClient,
        _payload(),
        [_file(), _file(file_id="other", origination_message_id="elsewhere")],
    )
    assert client.get_generated_images("conversation-1") == []


def test_inactive_branch_never_contributes_image(monkeypatch):
    client, calls = _client(
        monkeypatch, ChatGPTWebClient, _payload(marker=False, alternate=True)
    )
    assert client.get_generated_images("conversation-1") == []
    assert [kind for kind, _ in calls] == ["history"]


def test_non_image_or_malformed_part_does_not_query_files(monkeypatch):
    client, calls = _client(
        monkeypatch,
        ChatGPTWebClient,
        _payload(parts=[{"content_type": "image_asset_pointer", "size_bytes": 12}]),
    )
    assert client.get_generated_images("conversation-1") == []
    assert [kind for kind, _ in calls] == ["history"]


def test_nonready_image_is_not_inferred_from_assistant_completion(monkeypatch):
    client, _ = _client(
        monkeypatch, ChatGPTWebClient, _payload(), [_file(state="processing")]
    )
    assert client.get_generated_images("conversation-1") == []


def test_unavailable_file_listing_raises_without_send(monkeypatch):
    client, calls = _client(monkeypatch, ChatGPTWebClient, _payload(), status=503)
    with pytest.raises(RequestError, match="discovery failed"):
        client.get_generated_images("conversation-1")
    assert [kind for kind, _ in calls] == ["history", "files"]


def test_rejects_invalid_conversation_id_before_reads(monkeypatch):
    client, calls = _client(monkeypatch, ChatGPTWebClient, _payload())
    with pytest.raises(ValueError, match="conversation_id is required"):
        client.get_generated_images("")
    assert calls == []


def test_equal_image_parts_cannot_claim_same_artifact_twice(monkeypatch):
    image = _payload()["mapping"]["tool"]["message"]["content"]["parts"][0]
    client, _ = _client(
        monkeypatch, ChatGPTWebClient, _payload(parts=[image, dict(image)])
    )
    assert client.get_generated_images("conversation-1") == []
