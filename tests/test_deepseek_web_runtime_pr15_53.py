from __future__ import annotations

from dataclasses import replace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.deepseek_web_provider import (
    DeepSeekWebTurnResult,
    DeepSeekWebWriteOutcomeAmbiguousError,
)
from chatgpt_web_adapter.product_capabilities import (
    CONTINUATION,
    NEW_CHAT,
    STREAMING,
    TEXT_TURNS,
    CapabilityState,
)
from chatgpt_web_adapter.product_provenance import CompletionSource
from chatgpt_web_adapter.product_support import ProductTransportSupportTier


class _Status:
    available = True
    extension_connected = True


class _FakeDeepSeekProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, float | None]] = []

    def status(self):
        return _Status()

    def send_text(self, text, *, conversation=None, timeout=None):
        conversation_id = None
        if conversation is not None:
            conversation_id = adapter.ConversationRef.from_any(conversation).conversation_id
        resolved = conversation_id or "local-deepseek-conversation"
        self.calls.append((text, conversation_id, timeout))
        return DeepSeekWebTurnResult(
            conversation_id=resolved,
            assistant_text=f"answer:{text}",
            final_url="https://chat.deepseek.com/a/chat/s/server-route-is-opaque",
            tab_id=42,
            tab_was_active=False,
            elapsed_ms=1200,
            submit_strategy="send_button_click",
            submit_button_selector="div[role='button'].ds-icon-button",
            completion_proof="stable_assistant_dom",
            stable_for_ms=9001,
        )


def test_deepseek_runtime_passes_frozen_provider_boundary() -> None:
    runtime = adapter.DeepSeekWebRuntime(provider=_FakeDeepSeekProvider())

    boundary = adapter.product_provider_boundary(runtime)

    assert boundary.provider_id == "deepseek"
    assert boundary.product_semantics == "ordinary-deepseek"
    assert boundary.transport == "deepseek-web"
    assert boundary.automatic_write_retry is False
    assert boundary.fallback_transport is None
    assert boundary.ambiguous_write_requires_reconciliation is True
    assert boundary.incremental_observation_is_canonical_finality is False


def test_deepseek_capability_surface_is_bounded_and_experimental() -> None:
    runtime = adapter.DeepSeekWebRuntime(provider=_FakeDeepSeekProvider())
    capabilities = runtime.capabilities()

    assert capabilities.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL
    assert capabilities.state(TEXT_TURNS) is CapabilityState.AVAILABLE
    assert capabilities.state(NEW_CHAT) is CapabilityState.AVAILABLE
    assert capabilities.state(CONTINUATION) is CapabilityState.AVAILABLE
    assert capabilities.state(STREAMING) is CapabilityState.UNIMPLEMENTED

    available = {
        entry.name
        for entry in capabilities.entries
        if entry.state is CapabilityState.AVAILABLE
    }
    assert available == {TEXT_TURNS, NEW_CHAT, CONTINUATION}


def test_deepseek_new_chat_and_continuation_preserve_local_identity() -> None:
    provider = _FakeDeepSeekProvider()
    runtime = adapter.DeepSeekWebRuntime(provider=provider)

    first = runtime.send_text_observed("first")
    conversation_id = first.response.conversation.conversation_id
    second = runtime.send_text_observed("second", conversation=conversation_id)

    assert conversation_id == "local-deepseek-conversation"
    assert second.response.conversation.conversation_id == conversation_id
    assert first.response.text == "answer:first"
    assert second.response.text == "answer:second"
    assert provider.calls == [
        ("first", None, 150.0),
        ("second", conversation_id, 150.0),
    ]


def test_deepseek_completion_is_transport_dom_proof_not_canonical_readback() -> None:
    runtime = adapter.DeepSeekWebRuntime(provider=_FakeDeepSeekProvider())

    execution = runtime.send_text_observed("proof")

    assert execution.provenance is not None
    assert execution.provenance.completion.source is CompletionSource.TRANSPORT_RETURN
    assert execution.provenance.completion.canonical_completion_proven is False
    assert "stable_for_ms=9001" in (
        execution.provenance.completion.finality_detail or ""
    )
    assert execution.observation == {
        "provider_id": "deepseek",
        "completion_proof": "stable_assistant_dom",
        "stable_for_ms": 9001,
        "continuation": False,
    }


def test_deepseek_transport_rejects_streaming_before_write() -> None:
    provider = _FakeDeepSeekProvider()
    transport = adapter.DeepSeekWebProductTransport(provider)

    with pytest.raises(ValueError, match="does not expose incremental streaming"):
        transport.send_text("no stream", on_event=lambda event: None)

    assert provider.calls == []


def test_deepseek_ambiguous_provider_failure_is_no_retry_reconciliation_required() -> None:
    provider = adapter.DeepSeekWebTurnProvider()
    provider._rpc = lambda *args, **kwargs: {
        "protocol": 1,
        "request_id": args[0]["request_id"],
        "ok": False,
        "error": (
            "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            "ASSISTANT_RESPONSE_NOT_OBSERVED"
        ),
    }

    with pytest.raises(DeepSeekWebWriteOutcomeAmbiguousError) as caught:
        provider.send_text("ambiguous")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_deepseek_provider_payload_uses_provider_dispatch_and_no_wire_endpoint() -> None:
    provider = adapter.DeepSeekWebTurnProvider()
    captured = {}

    def rpc(payload, **kwargs):
        captured.update(payload)
        return {
            "protocol": 1,
            "request_id": payload["request_id"],
            "ok": True,
            "providerId": "deepseek",
            "conversationId": "opaque-local-id",
            "assistantText": "done",
            "finalUrl": "https://chat.deepseek.com/a/chat/s/anything",
            "completionProof": "stable_assistant_dom",
            "stableForMs": 9000,
        }

    provider._rpc = rpc
    result = provider.send_text("hello")

    assert captured["type"] == "turn"
    assert captured["providerId"] == "deepseek"
    assert captured["conversationId"] is None
    assert "url" not in captured
    assert "endpoint" not in captured
    assert result.conversation_id == "opaque-local-id"
