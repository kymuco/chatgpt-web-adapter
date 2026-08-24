from __future__ import annotations

from time import monotonic
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_scope import (
    _BROWSERLESS_REQUEST_SCOPE_OWNER,
)
from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.types import ChatConversation, ChatMessage, ChatResponse


class _CanonicalRaceClient:
    def get_status(self, conversation):
        return SimpleNamespace(
            status="completed",
            finish_reason="stop",
            message_id="submitted-message",
        )

    def get_messages(self, conversation, **kwargs):
        return [
            ChatMessage(
                role="assistant",
                text="foreign concurrent answer",
                message_id="foreign-message",
                finish_reason="stop",
            )
        ]


class _CanonicalStatusRaceClient:
    def __init__(self, status_message_id="foreign-message") -> None:
        self.status_message_id = status_message_id

    def get_status(self, conversation):
        return SimpleNamespace(
            status="completed",
            finish_reason="stop",
            message_id=self.status_message_id,
        )

    def get_messages(self, conversation, **kwargs):
        return [
            ChatMessage(
                role="assistant",
                text="submitted partial answer",
                message_id="submitted-message",
                finish_reason="stop",
            )
        ]


def _submitted_response() -> ChatResponse:
    return ChatResponse(
        text="submitted stream",
        conversation=ChatConversation(
            conversation_id="conversation-1",
            message_id="submitted-message",
            parent_message_id="submitted-message",
        ),
    )


def test_canonical_finality_rejects_foreign_concurrent_branch_identity() -> None:
    transport = object.__new__(BrowserlessRequestTransport)
    transport.canonical_client = _CanonicalRaceClient()

    with pytest.raises(
        BrowserlessRequestTransportError,
        match="readback assistant identity does not match the submitted browserless turn",
    ) as captured:
        transport._canonical_finalize(
            _submitted_response(),
            previous_message_id="old-parent",
            timeout=0.1,
            poll_interval=0.01,
        )

    error = captured.value
    assert error.request_stage == "canonical_reconciliation"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True


def test_canonical_finality_rejects_completed_status_from_foreign_turn() -> None:
    transport = object.__new__(BrowserlessRequestTransport)
    transport.canonical_client = _CanonicalStatusRaceClient()

    with pytest.raises(
        BrowserlessRequestTransportError,
        match="completion status identity does not match the submitted browserless turn",
    ) as captured:
        transport._canonical_finalize(
            _submitted_response(),
            previous_message_id="old-parent",
            timeout=0.1,
            poll_interval=0.01,
        )

    error = captured.value
    assert error.request_stage == "canonical_reconciliation"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True


def test_canonical_finality_fails_closed_without_status_identity() -> None:
    transport = object.__new__(BrowserlessRequestTransport)
    transport.canonical_client = _CanonicalStatusRaceClient(status_message_id=None)

    with pytest.raises(
        BrowserlessRequestTransportError,
        match="completion status identity does not match the submitted browserless turn",
    ) as captured:
        transport._canonical_finalize(
            _submitted_response(),
            previous_message_id="old-parent",
            timeout=0.1,
            poll_interval=0.01,
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.write_may_have_been_submitted is True


def test_browserless_recovery_poll_sleep_respects_short_total_deadline() -> None:
    client = object.__new__(ChatGPTWebClient)
    client._emit_event = lambda *args, **kwargs: None

    def fail_payload(_conversation_id):
        raise RequestError("conversation still unavailable")

    client._get_conversation_payload = fail_payload

    owner_token = _BROWSERLESS_REQUEST_SCOPE_OWNER.set(object())
    started = monotonic()
    try:
        message, text, payload = client._poll_conversation_after_prepare(
            "conversation-1",
            previous_message_id="parent-message",
            timeout=0.05,
            interval=0.01,
            reason="browserless_deadline_regression",
        )
    finally:
        elapsed = monotonic() - started
        _BROWSERLESS_REQUEST_SCOPE_OWNER.reset(owner_token)

    assert message is None
    assert text == ""
    assert payload is None
    # Before the guard, the legacy max(0.5, interval) sleep made this exceed
    # half a second. Leave broad scheduler margin while still proving that the
    # browserless total deadline, not the legacy minimum sleep, owns the wait.
    assert elapsed < 0.30