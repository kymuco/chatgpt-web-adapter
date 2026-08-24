from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browserless_request_transport import (
    BrowserlessRequestTransport,
    BrowserlessRequestTransportError,
)


class _NeverReadCanonicalClient:
    def __init__(self) -> None:
        self.status_calls = 0
        self.message_calls = 0

    def get_status(self, conversation):
        self.status_calls += 1
        raise AssertionError("missing submitted identity must fail before canonical status")

    def get_messages(self, conversation, **kwargs):
        self.message_calls += 1
        raise AssertionError("missing submitted identity must fail before canonical messages")


@pytest.mark.parametrize("submitted_message_id", [None, "", "   "])
def test_canonical_finality_fails_closed_without_submitted_assistant_identity(
    submitted_message_id,
) -> None:
    transport = object.__new__(BrowserlessRequestTransport)
    client = _NeverReadCanonicalClient()
    transport.canonical_client = client
    response = SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id=submitted_message_id,
        )
    )

    with pytest.raises(
        BrowserlessRequestTransportError,
        match="submitted browserless assistant identity is missing",
    ) as captured:
        transport._canonical_finalize(
            response,
            previous_message_id="old-parent",
            timeout=0.1,
            poll_interval=0.01,
        )

    error = captured.value
    assert error.request_stage == "canonical_reconciliation"
    assert error.write_may_have_been_submitted is True
    assert error.reconciliation_required is True
    assert client.status_calls == 0
    assert client.message_calls == 0
