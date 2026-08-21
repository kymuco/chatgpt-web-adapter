from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.temporary_product_runtime_pr8_13 import (
    TemporaryProductWriteRuntimeError,
)


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Provider:
    def status(self):
        return SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=77,
        )

    def send_text(self, *args, **kwargs):
        raise AssertionError("focused PR8.13.1 tests must not use the ordinary provider writer")


class _TemporaryRuntime:
    def __init__(self) -> None:
        self.state = "NOT_ESTABLISHED"
        self.conversation_id: str | None = None
        self.calls: list[tuple[str, str, dict]] = []
        self.close_count = 0

    def lifecycle_snapshot(self):
        return {
            "state": self.state,
            "conversation_id": self.conversation_id,
            "token_present": self.state == "LIVE",
            "token_exported": False,
        }

    def send_text(self, text, **kwargs):
        self.calls.append(("send_text", text, dict(kwargs)))
        return object()

    def send_text_observed(self, text, **kwargs):
        self.calls.append(("send_text_observed", text, dict(kwargs)))
        return object()

    def close(self):
        self.close_count += 1
        was_live = self.state == "LIVE"
        self.state = "NOT_ESTABLISHED"
        self.conversation_id = None
        return was_live


class _NormalRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.result = object()

    def send_text(self, text, **kwargs):
        self.calls.append(("send_text", text, dict(kwargs)))
        return self.result


def _transport() -> tuple[BrowserOwnedProductTransport, _TemporaryRuntime]:
    transport = BrowserOwnedProductTransport(_Client(), provider=_Provider())  # type: ignore[arg-type]
    temporary = _TemporaryRuntime()
    transport._temporary_runtime = temporary  # type: ignore[assignment]
    return transport, temporary


def test_fresh_temporary_public_send_omits_internal_routing_identity() -> None:
    transport, temporary = _transport()

    result = transport.send_text_observed(
        "first",
        conversation_mode="temporary",
    )

    assert result is not None
    assert temporary.calls == [
        (
            "send_text_observed",
            "first",
            {
                "conversation": None,
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]


def test_second_temporary_public_send_implicitly_continues_live_runtime_session() -> None:
    transport, temporary = _transport()
    temporary.state = "LIVE"
    temporary.conversation_id = "temporary-routing-1"

    transport.send_text_observed(
        "second",
        conversation_mode="temporary",
    )

    assert temporary.calls[0][2]["conversation"] == "temporary-routing-1"


def test_product_runtime_public_api_implicitly_continues_without_temporary_id() -> None:
    transport, temporary = _transport()
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)
    temporary.state = "LIVE"
    temporary.conversation_id = "temporary-routing-1"

    result = runtime.send_text(
        "second",
        conversation_mode="temporary",
    )

    assert result is not None
    assert temporary.calls == [
        (
            "send_text",
            "second",
            {
                "conversation": "temporary-routing-1",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]

    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="PR8_13_1_TEMPORARY_EXPLICIT_CONVERSATION_FORBIDDEN",
    ):
        runtime.send_text(
            "must not write",
            conversation="temporary-routing-1",
            conversation_mode="temporary",
        )

    assert len(temporary.calls) == 1


def test_explicit_temporary_conversation_argument_is_rejected_before_low_level_write() -> None:
    transport, temporary = _transport()
    temporary.state = "LIVE"
    temporary.conversation_id = "temporary-routing-1"

    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="PR8_13_1_TEMPORARY_EXPLICIT_CONVERSATION_FORBIDDEN",
    ) as caught:
        transport.send_text_observed(
            "must not write",
            conversation="temporary-routing-1",
            conversation_mode="temporary",
        )

    assert temporary.calls == []
    assert caught.value.write_may_have_been_submitted is False
    assert caught.value.reconciliation_required is False
    assert caught.value.request_stage == "temporary_session_api_preflight"


def test_live_session_without_internal_routing_identity_fails_closed_before_write() -> None:
    transport, temporary = _transport()
    temporary.state = "LIVE"
    temporary.conversation_id = None

    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="PR8_13_1_TEMPORARY_LIVE_SESSION_ROUTING_ID_MISSING",
    ) as caught:
        transport.send_text(
            "must not write",
            conversation_mode="temporary",
        )

    assert temporary.calls == []
    assert caught.value.write_may_have_been_submitted is False
    assert caught.value.reconciliation_required is False


def test_explicit_end_then_next_temporary_send_is_fresh_again() -> None:
    transport, temporary = _transport()
    temporary.state = "LIVE"
    temporary.conversation_id = "temporary-routing-1"

    assert transport.end_temporary_lifecycle() is True
    assert temporary.close_count == 1

    transport.send_text_observed(
        "new session",
        conversation_mode="temporary",
    )

    assert temporary.calls[0][2]["conversation"] is None


def test_normal_mode_keeps_explicit_conversation_behavior() -> None:
    transport, temporary = _transport()
    normal = _NormalRuntime()
    transport._runtime = normal  # type: ignore[assignment]

    # Deliberately make the Temporary state malformed. Normal mode must not
    # inspect it and must preserve the ordinary explicit conversation handle.
    temporary.state = "LIVE"
    temporary.conversation_id = None

    result = transport.send_text(
        "ordinary",
        conversation="conversation-1",
        conversation_mode="normal",
    )

    assert result is normal.result
    assert normal.calls == [
        (
            "send_text",
            "ordinary",
            {
                "conversation": "conversation-1",
                "timeout": 150.0,
                "poll_interval": 0.5,
                "on_token": None,
                "on_event": None,
            },
        )
    ]
    assert temporary.calls == []


def test_governance_declares_session_only_public_temporary_contract() -> None:
    transport, _temporary = _transport()
    governance = transport.governance()

    assert governance["temporary_chat_public_continuation_model"] == "LIVE_RUNTIME_SESSION_ONLY"
    assert governance["temporary_chat_public_conversation_argument_supported"] is False
    assert governance["temporary_chat_same_runtime_implicit_continuation"] is True
    assert governance["temporary_chat_explicit_conversation_argument_fail_closed_before_write"] is True
    assert governance["temporary_chat_internal_routing_identity_is_public_authority"] is False
    assert governance["temporary_chat_new_session_after_explicit_end"] is True
