from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.product_runtime as product_runtime
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.product_runtime import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    ChatGPTProductRuntime,
    DEFAULT_PRODUCT_TRANSPORT,
    ProductRuntimeExecution,
    SUPPORTED_PRODUCT_TRANSPORTS,
    assemble_product_runtime,
    normalize_product_transport,
)


class _Provider:
    def __init__(self, *, tab_id: int | None = 41, connected: bool = True) -> None:
        self.tab_id = tab_id
        self.connected = connected

    def status(self) -> BrowserNativeBridgeStatus:
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=self.connected,
            runtime_tab_id=self.tab_id,
        )


class _Client:
    def __init__(self, status: str = "completed") -> None:
        self.status_value = status

    def get_status(self, conversation):
        return SimpleNamespace(status=self.status_value)

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


def test_transport_selection_is_closed_and_browser_owned_by_default() -> None:
    assert DEFAULT_PRODUCT_TRANSPORT == BROWSER_OWNED_PRODUCT_TRANSPORT
    assert SUPPORTED_PRODUCT_TRANSPORTS == ("browser-owned",)
    assert normalize_product_transport(" browser-owned ") == "browser-owned"
    with pytest.raises(ValueError, match="unsupported product transport"):
        normalize_product_transport("legacy-direct")


def test_new_chat_readiness_does_not_require_preexisting_runtime_tab() -> None:
    runtime = ChatGPTProductRuntime(_Client(), provider=_Provider(tab_id=None))

    health = runtime.health()

    assert health.transport == "browser-owned"
    assert health.ready is True
    assert health.runtime_tab_id is None
    assert health.runtime_tab_preexisting is False
    assert health.canonical_read_checked is False
    assert health.fallback_transport is None


def test_continuation_requires_canonical_completed_status() -> None:
    client = _Client(status="running")
    runtime = ChatGPTProductRuntime(client, provider=_Provider())

    health = runtime.health("conversation-1")

    assert health.ready is False
    assert health.canonical_status == "running"
    assert health.canonical_read_checked is True


def test_reassembled_runtime_observes_same_external_runtime_tab() -> None:
    provider = _Provider(tab_id=77)
    first = ChatGPTProductRuntime(_Client(), provider=provider)
    second = ChatGPTProductRuntime(_Client(), provider=provider)

    first_health = first.health("conversation-1")
    second_health = second.health("conversation-1")

    assert first_health.runtime_tab_id == 77
    assert second_health.runtime_tab_id == 77
    assert first_health.runtime_tab_preexisting is True
    assert second_health.runtime_tab_preexisting is True


def test_send_text_delegates_exactly_once_without_fallback() -> None:
    runtime = ChatGPTProductRuntime(_Client(), provider=_Provider())
    calls = []
    expected = object()

    def fake_send_text(text, **kwargs):
        calls.append((text, kwargs))
        return expected

    runtime._writer.send_text = fake_send_text

    result = runtime.send_text(
        "hello",
        conversation="conversation-1",
        timeout=12.0,
        poll_interval=0.25,
    )

    assert result is expected
    assert calls == [
        (
            "hello",
            {
                "conversation": "conversation-1",
                "timeout": 12.0,
                "poll_interval": 0.25,
                "on_token": None,
                "on_event": None,
            },
        )
    ]
    assert runtime.governance()["fallback_transport"] is None
    assert runtime.governance()["legacy_direct_write_fallback"] is False


def test_observed_send_preserves_transport_and_writer_observation() -> None:
    runtime = ChatGPTProductRuntime(_Client(), provider=_Provider())
    response = object()
    observation = SimpleNamespace(to_dict=lambda: {"runtime_tab_id": 77})
    runtime._writer.send_text_observed = lambda *args, **kwargs: SimpleNamespace(
        response=response,
        observation=observation,
    )

    execution = runtime.send_text_observed("hello")

    assert isinstance(execution, ProductRuntimeExecution)
    assert execution.transport == "browser-owned"
    assert execution.response is response
    assert execution.observation is observation


def test_assembly_disables_interactive_login_and_sentinel(monkeypatch) -> None:
    captured = {}

    class FakeClient(_Client):
        def __init__(self, **kwargs):
            super().__init__()
            captured.update(kwargs)

    monkeypatch.setattr(product_runtime, "ChatGPTWebClient", FakeClient)
    provider = _Provider()

    runtime = assemble_product_runtime(
        transport="browser-owned",
        provider=provider,
        auth_file="saved-auth.json",
        client_timeout=33,
    )

    assert isinstance(runtime, ChatGPTProductRuntime)
    assert captured["auth_file"] == "saved-auth.json"
    assert captured["timeout"] == 33
    assert captured["auto_refresh_auth"] is True
    assert captured["auto_login"] is False
    assert captured["auto_sentinel"] is False
