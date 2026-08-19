from __future__ import annotations

import json

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.temporary_chat_canonical_read_probe import (
    main,
    probe_temporary_canonical_read,
)


class _FakeClient:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[str] = []

    def _get_conversation_payload(self, conversation_id: str):
        self.calls.append(conversation_id)
        if self.error is not None:
            raise self.error
        return self.payload


def _readable_payload() -> dict:
    return {
        "id": "ephemeral-1",
        "current_node": "assistant-node",
        "mapping": {
            "user-node": {
                "parent": None,
                "message": {
                    "id": "user-message",
                    "author": {"role": "user"},
                    "content": {"parts": ["SECRET USER TEXT"]},
                },
            },
            "assistant-node": {
                "parent": "user-node",
                "message": {
                    "id": "assistant-message",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "end_turn": True,
                    "metadata": {"finish_details": {"type": "stop"}},
                    "content": {"parts": ["SECRET ASSISTANT TEXT"]},
                },
            },
        },
    }


def test_temporary_canonical_read_requires_exactly_one_source_tab_state() -> None:
    client = _FakeClient(_readable_payload())

    with pytest.raises(ValueError, match="exactly one source Temporary tab state"):
        probe_temporary_canonical_read(
            "ephemeral-1",
            client=client,
        )

    with pytest.raises(ValueError, match="exactly one source Temporary tab state"):
        probe_temporary_canonical_read(
            "ephemeral-1",
            source_temporary_tab_confirmed_open=True,
            source_temporary_tab_confirmed_closed=True,
            client=client,
        )

    assert client.calls == []


def test_temporary_canonical_read_rejects_product_url_as_backend_id() -> None:
    with pytest.raises(ValueError, match="raw backend id"):
        probe_temporary_canonical_read(
            "https://chatgpt.com/c/ephemeral-1",
            source_temporary_tab_confirmed_open=True,
            client=_FakeClient(_readable_payload()),
        )


def test_temporary_canonical_read_uses_one_payload_read_without_attach_or_write() -> None:
    client = _FakeClient(_readable_payload())

    result = probe_temporary_canonical_read(
        "ephemeral-1",
        source_temporary_tab_confirmed_open=True,
        client=client,
    )

    assert client.calls == ["ephemeral-1"]
    assert result.probe_context == "temporary_canonical_direct_id_read_while_live"
    assert result.source_temporary_tab_state == "OPEN"
    assert result.source_temporary_tab_confirmed_open is True
    assert result.source_temporary_tab_confirmed_closed is False
    assert result.canonical_payload_read_calls == 1
    assert result.canonical_read_succeeded is True
    assert result.canonical_readability_status == "READABLE"
    assert result.browser_navigation_performed is False
    assert result.product_route_open_attempted is False
    assert result.attach_performed is False
    assert result.write_performed is False
    assert result.http_referer_uses_conversation_route_shape is True
    assert result.payload_id_present is True
    assert result.payload_id_matches_requested is True
    assert result.mapping_present is True
    assert result.mapping_node_count == 2
    assert result.current_node_present is True
    assert result.current_branch_node_count == 2
    assert result.current_branch_message_count == 2
    assert result.user_message_count == 1
    assert result.assistant_message_count == 1
    assert result.lifecycle_status == "completed"
    assert result.current_role == "assistant"
    assert result.finish_reason_present is True

    serialized = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "SECRET USER TEXT" not in serialized
    assert "SECRET ASSISTANT TEXT" not in serialized
    assert result.raw_payload_exported is False
    assert result.message_text_exported is False


def test_temporary_canonical_read_after_source_close_is_distinct_context() -> None:
    client = _FakeClient(
        error=RequestError(
            "conversation status=404: not found",
            request_stage="conversation_fetch",
        )
    )

    result = probe_temporary_canonical_read(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        client=client,
    )

    assert client.calls == ["ephemeral-1"]
    assert result.probe_context == "temporary_canonical_direct_id_read_after_source_close"
    assert result.source_temporary_tab_state == "CLOSED"
    assert result.source_temporary_tab_confirmed_open is False
    assert result.source_temporary_tab_confirmed_closed is True
    assert result.canonical_read_succeeded is False
    assert result.canonical_readability_status == "NOT_FOUND"
    assert result.http_status == 404


def test_temporary_canonical_read_preserves_not_found_as_experiment_result() -> None:
    client = _FakeClient(
        error=RequestError(
            "conversation status=404: not found",
            request_stage="conversation_fetch",
        )
    )

    result = probe_temporary_canonical_read(
        "ephemeral-1",
        source_temporary_tab_confirmed_open=True,
        client=client,
    )

    assert client.calls == ["ephemeral-1"]
    assert result.canonical_read_succeeded is False
    assert result.canonical_readability_status == "NOT_FOUND"
    assert result.http_status == 404
    assert result.request_stage == "conversation_fetch"
    assert result.mapping_present is False
    assert result.current_branch_message_count == 0


def test_temporary_canonical_read_preserves_access_denied_distinct_from_not_found() -> None:
    client = _FakeClient(error=RequestError("conversation status=403: forbidden"))

    result = probe_temporary_canonical_read(
        "ephemeral-1",
        source_temporary_tab_confirmed_closed=True,
        client=client,
    )

    assert result.canonical_readability_status == "ACCESS_DENIED"
    assert result.http_status == 403
    assert result.canonical_read_succeeded is False
    assert result.source_temporary_tab_state == "CLOSED"


def test_cli_requires_explicit_source_tab_state(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["ephemeral-1"])
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert captured == {
        "ok": False,
        "error": "TEMPORARY_CANONICAL_READ_SOURCE_TAB_STATE_CONFIRMATION_REQUIRED",
    }


def test_cli_rejects_conflicting_source_tab_states(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "ephemeral-1",
            "--source-temporary-tab-confirmed-open",
            "--source-temporary-tab-confirmed-closed",
        ]
    )
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert captured == {
        "ok": False,
        "error": "TEMPORARY_CANONICAL_READ_SOURCE_TAB_STATE_CONFLICT",
    }
