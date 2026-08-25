from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browserless_request_scope import gate_browserless_request_execute
from chatgpt_web_adapter.browserless_request_transport import BrowserlessRequestTransport
from chatgpt_web_adapter.browserless_shared_write_fence import (
    _mutation_authority,
    unfenced_mutation_callable,
)


class _CompatibleSharedClient:
    def __init__(self) -> None:
        self.timeout = 60.0
        self.base_headers = {"user-agent": "multi-transport-test"}
        self.auth = SimpleNamespace(
            accessToken="test-access-token",
            cookies={},
            turnstile_token=None,
        )
        self.send_calls: list[str] = []

    def _build_headers(self, extra=None):
        return {"authorization": "Bearer test", **dict(extra or {})}

    def _json_request(self, method, url, payload, headers):
        raise AssertionError("direct-send capture regression must not perform network I/O")

    def send(self, prompt, *, conversation=None, **kwargs):
        self.send_calls.append(prompt)
        return f"sent:{prompt}"

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation=conversation)

    def get_status(self, conversation):
        return SimpleNamespace(status="completed", message_id="message-1")

    def get_messages(self, conversation, **kwargs):
        return []


def test_second_transport_unwraps_first_transport_send_fence_before_direct_execution() -> None:
    client = _CompatibleSharedClient()
    first = BrowserlessRequestTransport(client)
    second = BrowserlessRequestTransport(client)

    # The first transport installs the shared-client mutation fence. A compatible
    # second transport therefore observes that wrapper during its original init.
    assert second._direct_send is not unfenced_mutation_callable(second._direct_send)

    def direct_probe(
        transport,
        text,
        *,
        conversation,
        timeout,
        poll_interval,
        on_token,
        on_event,
    ):
        return transport._direct_send(text, conversation=conversation)

    execute = gate_browserless_request_execute(direct_probe)

    # Real BrowserlessRequestTransport execution is already inside this authority
    # before request-scope code runs. Without direct-send normalization the captured
    # fence deterministically rejects the call as a nested `send`.
    with _mutation_authority(client, "browserless_request"):
        result = execute(
            second,
            "probe",
            conversation=None,
            timeout=1.0,
            poll_interval=0.1,
            on_token=None,
            on_event=None,
        )

    assert result == "sent:probe"
    assert client.send_calls == ["probe"]
    assert second._direct_send is unfenced_mutation_callable(second._direct_send)
    assert first._write_lock is second._write_lock
