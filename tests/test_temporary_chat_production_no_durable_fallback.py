from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_capabilities import (
    TEMPORARY_CHAT,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.product_transport import BROWSER_OWNED_PRODUCT_TRANSPORT


class _Client:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _Transport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self, temporary_state: CapabilityState) -> None:
        self.temporary_state = temporary_state
        self.write_calls: list[tuple[str, str, dict]] = []
        self.capability_calls = 0
        self.normal_result = object()

    def health(self, conversation=None):
        raise AssertionError("health should not be consulted by the T8 write-mode gate")

    def capabilities(self) -> ProductCapabilities:
        self.capability_calls += 1
        return ProductCapabilities.from_entries(
            transport=self.transport_id,
            entries=(
                ProductCapability(
                    name=TEMPORARY_CHAT,
                    state=self.temporary_state,
                    owner=CapabilityOwner.TRANSPORT,
                ),
            ),
        )

    def send_text(self, text, **kwargs):
        self.write_calls.append(("send_text", text, kwargs))
        return self.normal_result

    def send_text_observed(self, text, **kwargs):
        self.write_calls.append(("send_text_observed", text, kwargs))
        raise AssertionError("blocked Temporary request reached observed transport dispatch")

    def governance(self):
        return {"transport": self.transport_id}


@pytest.mark.parametrize(
    "temporary_state",
    [
        CapabilityState.UNKNOWN,
        CapabilityState.AVAILABLE,
        CapabilityState.UNSUPPORTED,
        CapabilityState.UNIMPLEMENTED,
    ],
)
@pytest.mark.parametrize(
    "entrypoint",
    ["send", "send_text", "send_text_observed"],
)
def test_temporary_mode_fails_closed_before_transport_dispatch(
    temporary_state: CapabilityState,
    entrypoint: str,
) -> None:
    transport = _Transport(temporary_state)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(
        RuntimeError,
        match="PRODUCT_CONVERSATION_MODE_UNAVAILABLE.*fallback=none",
    ):
        getattr(runtime, entrypoint)(
            "must not become durable",
            conversation_mode="temporary",
        )

    assert transport.write_calls == []
    assert transport.capability_calls == 0


def test_invalid_conversation_mode_fails_before_transport_dispatch() -> None:
    transport = _Transport(CapabilityState.UNKNOWN)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(ValueError, match="unsupported conversation_mode"):
        runtime.send_text("hello", conversation_mode="ephemeral-ish")

    assert transport.write_calls == []


def test_non_string_conversation_mode_fails_before_transport_dispatch() -> None:
    transport = _Transport(CapabilityState.UNKNOWN)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    with pytest.raises(TypeError, match="conversation_mode must be a string"):
        runtime.send_text("hello", conversation_mode=None)  # type: ignore[arg-type]

    assert transport.write_calls == []


def test_normal_mode_delegates_to_existing_transport_without_mode_argument() -> None:
    transport = _Transport(CapabilityState.UNKNOWN)
    runtime = ChatGPTProductRuntime(_Client(), write_transport=transport)

    result = runtime.send_text(
        "ordinary",
        conversation="conversation-1",
        timeout=12.0,
        poll_interval=0.25,
        conversation_mode="normal",
    )

    assert result is transport.normal_result
    assert transport.write_calls == [
        (
            "send_text",
            "ordinary",
            {
                "conversation": "conversation-1",
                "timeout": 12.0,
                "poll_interval": 0.25,
                "on_token": None,
                "on_event": None,
            },
        )
    ]

    governance = runtime.governance()
    assert governance["conversation_mode_request_values"] == ["normal", "temporary"]
    assert governance["default_conversation_mode"] == "normal"
    assert governance["conversation_mode_fallback"] is None
    assert governance["silent_conversation_mode_fallback"] is False
    assert governance["temporary_mode_production_enabled"] is False
    assert governance["temporary_mode_fail_closed_before_write"] is True
    assert governance["temporary_mode_requires_mode_aware_write_routing"] is True
