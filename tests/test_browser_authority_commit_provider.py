from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_commit_provider import (
    CommitBoundProductModelProfileProvider,
)
from chatgpt_web_adapter.browser_native_client import submit_browser_native
from chatgpt_web_adapter.exceptions import RequestError


class _RecordingProvider(CommitBoundProductModelProfileProvider):
    def __init__(self) -> None:
        super().__init__(connect_timeout=0.1, turn_timeout=1.0)
        self.turn_payloads: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None):
        del timeout, on_event
        self.turn_payloads.append(dict(payload))
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "conversationId": payload.get("conversationId") or "new-conversation",
            "responseStatus": 200,
            "responseMimeType": "text/event-stream",
            "finalUrl": "https://chatgpt.com/c/test",
            "tabId": 17,
            "tabWasActive": False,
            "browserAuthorityLeaseId": payload.get("browserAuthorityLeaseId"),
            "attachmentCount": 0,
        }


class _BaselineClient:
    def __init__(self, provider: _RecordingProvider) -> None:
        self._browser_native_turn_provider = provider
        self.provider = provider
        self.baseline_leases: list[str | None] = []
        self.events: list[dict[str, object]] = []

    def _record_lease(self) -> None:
        self.baseline_leases.append(
            self.provider._current_browser_authority_lease_id()
        )

    def get_messages(self, conversation, **kwargs):
        del conversation, kwargs
        self._record_lease()
        return []

    def get_status(self, conversation):
        del conversation
        self._record_lease()
        return SimpleNamespace(status="completed")

    def _emit_event(self, callback, event_type, **payload):
        event = {"type": event_type, **payload}
        self.events.append(event)
        if callback is not None:
            callback(event)


class _FailingBaselineClient(_BaselineClient):
    def get_messages(self, conversation, **kwargs):
        del conversation, kwargs
        self._record_lease()
        raise RequestError("baseline unavailable", request_stage="test_prewrite")


def test_continuation_baseline_does_not_expose_uncommitted_lease() -> None:
    provider = _RecordingProvider()
    client = _BaselineClient(provider)

    provider.set_browser_authority_lease("lease-new")

    assert provider._pending_browser_authority_lease_id() == "lease-new"
    assert provider._current_browser_authority_lease_id() is None

    submission = submit_browser_native(
        client,
        "continue",
        conversation="conversation-1",
        timeout=1.0,
        poll_interval=0.01,
    )

    assert client.baseline_leases
    assert set(client.baseline_leases) == {None}
    assert len(provider.turn_payloads) == 1
    assert provider.turn_payloads[0]["browserAuthorityLeaseId"] == "lease-new"
    assert provider._current_browser_authority_lease_id() == "lease-new"
    assert submission.turn.browser_authority_lease_id == "lease-new"

    provider.clear_browser_authority_lease()
    assert provider._pending_browser_authority_lease_id() is None
    assert provider._current_browser_authority_lease_id() is None


def test_new_chat_activates_pending_lease_at_actual_turn_boundary() -> None:
    provider = _RecordingProvider()
    client = _BaselineClient(provider)

    provider.set_browser_authority_lease("lease-new-chat")
    submission = submit_browser_native(
        client,
        "hello",
        conversation=None,
        timeout=1.0,
        poll_interval=0.01,
    )

    assert client.baseline_leases == []
    assert len(provider.turn_payloads) == 1
    assert provider.turn_payloads[0]["browserAuthorityLeaseId"] == "lease-new-chat"
    assert submission.turn.browser_authority_lease_id == "lease-new-chat"
    assert provider._current_browser_authority_lease_id() == "lease-new-chat"


def test_continuation_baseline_failure_happens_before_provider_write() -> None:
    provider = _RecordingProvider()
    client = _FailingBaselineClient(provider)

    provider.set_browser_authority_lease("lease-never-delegated")

    with pytest.raises(RequestError, match="baseline unavailable"):
        submit_browser_native(
            client,
            "continue",
            conversation="conversation-1",
            timeout=1.0,
            poll_interval=0.01,
        )

    assert client.baseline_leases == [None]
    assert provider.turn_payloads == []
    assert provider._current_browser_authority_lease_id() is None
    assert (
        provider._pending_browser_authority_lease_id()
        == "lease-never-delegated"
    )

    provider.clear_browser_authority_lease()
    assert provider._pending_browser_authority_lease_id() is None


def test_default_browser_transport_uses_commit_bound_provider() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "src"
        / "chatgpt_web_adapter"
        / "browser_owned_product_transport.py"
    ).read_text(encoding="utf-8")

    assert "CommitBoundProductModelProfileProvider" in source
    assert "provider = CommitBoundProductModelProfileProvider()" in source
