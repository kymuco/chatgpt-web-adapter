from __future__ import annotations

import inspect

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.conversation_prepare import (
    build_prepare_headers,
    build_text_prepare_payload,
    prepare_text_turn,
)


def test_build_text_prepare_payload_matches_observed_partial_query_shape() -> None:
    payload = build_text_prepare_payload(
        "hello",
        model="gpt-5-6-thinking",
        conversation={"conversation_id": "conv-1", "message_id": "parent-1"},
        reasoning_effort="extended",
        partial_query_message_id="user-1",
    )

    assert payload["action"] == "next"
    assert payload["fork_from_shared_post"] is False
    assert payload["parent_message_id"] == "parent-1"
    assert payload["conversation_id"] == "conv-1"
    assert payload["model"] == "gpt-5-6-thinking"
    assert payload["client_prepare_state"] == "success"
    assert payload["partial_query"] == {
        "id": "user-1",
        "author": {"role": "user"},
        "content": {"content_type": "text", "parts": ["hello"]},
    }
    assert payload["thinking_effort"] == "extended"


def test_build_text_prepare_payload_uses_client_created_root_for_new_turn() -> None:
    payload = build_text_prepare_payload("hello", model="gpt-5-3-mini")
    assert payload["parent_message_id"] == "client-created-root"
    assert "conversation_id" not in payload


def test_build_prepare_headers_uses_no_token_and_target_route() -> None:
    class Client:
        def _build_headers(self, extra):
            return {key: value for key, value in extra.items() if value is not None}

    headers = build_prepare_headers(Client(), conversation_id="conv-1")
    assert headers["x-conduit-token"] == "no-token"
    assert headers["x-openai-target-path"] == "/backend-api/f/conversation/prepare"
    assert headers["x-openai-target-route"] == "/backend-api/f/conversation/prepare"
    assert headers["referer"].endswith("/c/conv-1")


def test_prepare_text_turn_retains_token_only_in_memory() -> None:
    class Client:
        def _build_headers(self, extra):
            return {key: value for key, value in extra.items() if value is not None}

        def _json_request(self, method, url, payload, headers):
            assert method == "POST"
            assert url.endswith("/backend-api/f/conversation/prepare")
            assert headers["x-conduit-token"] == "no-token"
            return 200, {"status": "ok", "conduit_token": "secret-conduit"}

    result, payload = prepare_text_turn(
        Client(),
        "secret prompt",
        model="gpt-5-6-thinking",
        conversation={"conversation_id": "conv-1", "message_id": "parent-1"},
        reasoning_effort="standard",
        partial_query_message_id="user-1",
    )
    assert result.status_ok is True
    assert result.conduit_token_present is True
    assert result.conduit_token == "secret-conduit"
    assert "secret-conduit" not in repr(result)
    assert payload["partial_query"]["content"]["parts"] == ["secret prompt"]


def test_normal_send_is_wired_to_prepare_boundary_when_provider_is_installed() -> None:
    source = inspect.getsource(adapter._original_send)
    assert "prepare_text_turn" in source
    assert "CHAT_CONVERSATION_PREPARE_URL" in source


def test_new_chat_prepare_omits_partial_query_and_initial_conduit() -> None:
    class Client:
        def _build_headers(self, extra):
            return {key: value for key, value in extra.items() if value is not None}

        def _json_request(self, method, url, payload, headers):
            assert "partial_query" not in payload
            assert payload["client_prepare_state"] == "none"
            assert payload["client_prepare_dispatch"] == "debounced"
            assert payload["client_prepare_source"] == "window_focus"
            assert "x-conduit-token" not in headers
            return 200, {"status": "ok", "conduit_token": "secret-conduit"}

    result, payload = prepare_text_turn(
        Client(),
        "hello",
        model="gpt-5-6-thinking",
        include_partial_query=False,
        client_prepare_state="none",
        client_prepare_dispatch="debounced",
        client_prepare_source="window_focus",
        initial_conduit_token=None,
    )

    assert result.status_ok is True
    assert "partial_query" not in payload
