from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_provenance import (
    CompletionSource,
    ConversationMode,
    ConversationModeEvidenceSource,
    TemporaryLifecycleEvidenceSource,
    TemporaryLifecycleState,
)
from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.product_transport import BROWSER_OWNED_PRODUCT_TRANSPORT
from chatgpt_web_adapter.temporary_product_runtime_pr8_13 import (
    TEMPORARY_PREWRITE_PROOF,
    TEMPORARY_READBACK_PLANE,
    TemporaryFinalTextCollector,
    TemporaryProductWriteRuntime,
    TemporaryProductWriteRuntimeError,
)


class _FakeTemporaryProvider:
    connect_timeout = 0.01

    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.lease_ids: list[str] = []
        self.clear_count = 0
        self.closed = False
        self.force_gap = False
        self.force_mode_unproven = False

    def status(self):
        return SimpleNamespace(available=True, extension_connected=True)

    def set_browser_authority_lease(self, lease_id: str) -> None:
        self.lease_ids.append(lease_id)

    def clear_browser_authority_lease(self) -> None:
        self.clear_count += 1

    def _rpc(self, payload: dict, *, timeout: float, on_event=None) -> dict:
        del timeout
        self.payloads.append(dict(payload))
        request_id = payload["request_id"]

        if payload.get("endTemporaryLifecycle") is True:
            self.closed = True
            return {
                "request_id": request_id,
                "ok": True,
                "conversationMode": "temporary",
                "conversationId": payload.get("conversationId"),
                "temporaryLifecycleState": "ENDED",
            }

        if callable(on_event):
            on_event(
                {
                    "type": "assistant_text_snapshot",
                    "sequence": 1,
                    "message_id": "commentary-1",
                    "channel": "commentary",
                    "text": "I will check that first.",
                }
            )
            on_event(
                {
                    "type": "activity_started",
                    "sequence": 1,
                    "activity_id": "web-1",
                    "activity_kind": "web",
                    "label": "Using the web…",
                }
            )
            final_sequence = 3 if self.force_gap else 2
            on_event(
                {
                    "type": "assistant_text_snapshot",
                    "sequence": final_sequence,
                    "message_id": "final-1",
                    "channel": "final",
                    "text": "Final",
                }
            )
            on_event(
                {
                    "type": "assistant_text_delta",
                    "sequence": final_sequence + 1,
                    "message_id": "final-1",
                    "channel": "final",
                    "delta": " answer",
                    "finish_reason": "stop",
                }
            )

        continuation = payload.get("conversationId") is not None
        return {
            "request_id": request_id,
            "ok": True,
            "conversationId": payload.get("conversationId") or "temporary-conversation-1",
            "turnExchangeId": "turn-exchange-1",
            "responseStatus": 200,
            "conversationMode": "temporary",
            "temporaryModeProven": not self.force_mode_unproven,
            "temporaryPrewriteProof": TEMPORARY_PREWRITE_PROOF,
            "temporaryContinuationIdentityProven": continuation,
            "temporaryLifecycleToken": payload["temporaryLifecycleToken"],
            "temporaryLifecycleState": "LIVE",
            "temporaryLiveWriteAuthorityProven": True,
            "temporaryPausedConversationWriteCount": 1,
            "tabId": 123,
        }


def test_collector_prefers_explicit_final_over_commentary() -> None:
    collector = TemporaryFinalTextCollector()
    collector.apply(
        {
            "type": "assistant_text_snapshot",
            "sequence": 1,
            "message_id": "commentary",
            "channel": "commentary",
            "text": "Working on it",
        }
    )
    collector.apply(
        {
            "type": "assistant_text_snapshot",
            "sequence": 2,
            "message_id": "final",
            "channel": "final",
            "text": "Done",
        }
    )
    collector.apply(
        {
            "type": "assistant_text_delta",
            "sequence": 3,
            "message_id": "final",
            "channel": "final",
            "delta": ".",
            "finish_reason": "stop",
        }
    )

    final = collector.final_message()
    assert final is not None
    assert final.message_id == "final"
    assert final.text == "Done."
    assert final.finish_reason == "stop"
    assert collector.delivery_incomplete is False


def test_temporary_runtime_returns_page_owned_final_and_private_live_authority() -> None:
    provider = _FakeTemporaryProvider()
    runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]
    visible_events: list[dict] = []

    execution = runtime.send_text_observed(
        "hello",
        on_event=lambda event: visible_events.append(dict(event)),
    )

    assert execution.response.text == "Final answer"
    assert execution.response.request.temporary is True
    assert execution.response.conversation.conversation_id == "temporary-conversation-1"
    assert execution.response.conversation.message_id == "final-1"
    assert execution.response.conversation.finish_reason == "stop"
    assert provider.clear_count == 1
    assert len(provider.lease_ids) == 1
    assert visible_events[0]["channel"] == "commentary"

    provenance = execution.provenance
    assert provenance is not None
    assert provenance.readback_plane == TEMPORARY_READBACK_PLANE
    assert provenance.completion.source is CompletionSource.TRANSPORT_RETURN
    assert provenance.completion.canonical_completion_proven is False
    assert provenance.conversation_mode is not None
    assert provenance.conversation_mode.requested_conversation_mode is ConversationMode.TEMPORARY
    assert provenance.conversation_mode.observed_conversation_mode is ConversationMode.TEMPORARY
    assert (
        provenance.conversation_mode.observed_mode_evidence_source
        is ConversationModeEvidenceSource.PRODUCT_MODE_OBSERVATION
    )
    assert provenance.conversation_mode.observed_mode_proven is True
    assert provenance.temporary_lifecycle is not None
    assert (
        provenance.temporary_lifecycle.temporary_lifecycle_state
        is TemporaryLifecycleState.LIVE
    )
    assert (
        provenance.temporary_lifecycle.lifecycle_evidence_source
        is TemporaryLifecycleEvidenceSource.PRODUCT_LIFECYCLE_OBSERVATION
    )
    assert provenance.temporary_lifecycle.live_write_authority_proven is True

    observation = execution.observation.to_dict()
    assert observation["temporary_mode_proven"] is True
    assert observation["temporary_prewrite_proof"] == TEMPORARY_PREWRITE_PROOF
    assert "temporaryLifecycleToken" not in observation
    assert "temporary_lifecycle_token" not in observation
    assert "temporaryLifecycleToken" not in provenance.to_dict()["transport_metadata"]

    snapshot = runtime.lifecycle_snapshot()
    assert snapshot == {
        "state": "LIVE",
        "conversation_id": "temporary-conversation-1",
        "token_present": True,
        "token_exported": False,
    }


def test_same_runtime_continuation_reuses_private_lifecycle_token() -> None:
    provider = _FakeTemporaryProvider()
    runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]

    first = runtime.send_text_observed("first")
    conversation_id = first.response.conversation.conversation_id
    assert conversation_id == "temporary-conversation-1"

    second = runtime.send_text_observed("second", conversation=conversation_id)
    assert second.response.conversation.conversation_id == conversation_id
    assert second.observation.temporary_continuation_identity_proven is True

    turn_payloads = [
        payload
        for payload in provider.payloads
        if payload.get("endTemporaryLifecycle") is not True
    ]
    assert len(turn_payloads) == 2
    assert turn_payloads[0]["temporaryLifecycleToken"] == turn_payloads[1]["temporaryLifecycleToken"]
    assert turn_payloads[0]["conversationId"] is None
    assert turn_payloads[1]["conversationId"] == conversation_id


def test_conversation_id_alone_cannot_recreate_temporary_continuation_authority() -> None:
    provider = _FakeTemporaryProvider()
    original = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]
    first = original.send_text_observed("first")
    conversation_id = first.response.conversation.conversation_id
    assert conversation_id is not None

    fresh_runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]
    before = len(provider.payloads)
    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="TEMPORARY_LIFECYCLE_NOT_LIVE",
    ):
        fresh_runtime.send_text_observed("must fail", conversation=conversation_id)
    assert len(provider.payloads) == before


def test_explicit_end_revokes_local_continuation_authority() -> None:
    provider = _FakeTemporaryProvider()
    runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]
    first = runtime.send_text_observed("first")
    conversation_id = first.response.conversation.conversation_id
    assert conversation_id is not None

    assert runtime.close() is True
    assert provider.closed is True
    assert runtime.lifecycle_snapshot()["state"] == "NOT_ESTABLISHED"

    before = len(provider.payloads)
    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="TEMPORARY_LIFECYCLE_NOT_LIVE",
    ):
        runtime.send_text_observed("after end", conversation=conversation_id)
    assert len(provider.payloads) == before


def test_incomplete_temporary_stream_fails_without_second_write() -> None:
    provider = _FakeTemporaryProvider()
    provider.force_gap = True
    runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]

    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="TEMPORARY_PAGE_READBACK_INCOMPLETE",
    ):
        runtime.send_text_observed("one write only")

    turn_payloads = [
        payload
        for payload in provider.payloads
        if payload.get("endTemporaryLifecycle") is not True
    ]
    assert len(turn_payloads) == 1
    assert runtime.lifecycle_snapshot()["state"] == "NOT_ESTABLISHED"


def test_unproven_temporary_mode_is_rejected_after_single_delegation() -> None:
    provider = _FakeTemporaryProvider()
    provider.force_mode_unproven = True
    runtime = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]

    with pytest.raises(
        TemporaryProductWriteRuntimeError,
        match="TEMPORARY_MODE_NOT_PROVEN",
    ):
        runtime.send_text_observed("one write only")

    turn_payloads = [
        payload
        for payload in provider.payloads
        if payload.get("endTemporaryLifecycle") is not True
    ]
    assert len(turn_payloads) == 1


class _CanonicalClient:
    def get_status(self, conversation):
        return SimpleNamespace(status="completed")

    def get_messages(self, conversation, **kwargs):
        return []

    def attach_conversation(self, conversation):
        return SimpleNamespace(conversation_id=conversation)


class _ModeAwareFakeTransport:
    transport_id = BROWSER_OWNED_PRODUCT_TRANSPORT

    def __init__(self, execution) -> None:
        self.execution = execution
        self.calls: list[dict] = []

    def health(self, conversation=None):
        raise AssertionError("not used")

    def capabilities(self):
        raise AssertionError("not used")

    def governance(self):
        return {
            "temporary_chat_product_runtime_selection_supported": True,
            "browser_authority_product_runtime_policy_supported": False,
            "model_profile_product_runtime_selection_supported": False,
        }

    def send_text(self, text, **kwargs):
        raise AssertionError("not used")

    def send_text_observed(self, text, **kwargs):
        self.calls.append(dict(kwargs))
        return self.execution


def test_product_runtime_dispatches_temporary_only_to_explicit_mode_aware_transport() -> None:
    provider = _FakeTemporaryProvider()
    low_level = TemporaryProductWriteRuntime(provider)  # type: ignore[arg-type]
    execution = low_level.send_text_observed("seed")
    transport = _ModeAwareFakeTransport(execution)
    runtime = ChatGPTProductRuntime(_CanonicalClient(), write_transport=transport)

    result = runtime.send_text_observed("temporary", conversation_mode="temporary")

    assert result.provenance is not None
    assert result.provenance.conversation_mode is not None
    assert result.provenance.conversation_mode.observed_conversation_mode is ConversationMode.TEMPORARY
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert callable(call["on_event"])
    assert {key: value for key, value in call.items() if key != "on_event"} == {
        "conversation": None,
        "timeout": 150.0,
        "poll_interval": 0.5,
        "on_token": None,
        "conversation_mode": "temporary",
    }
