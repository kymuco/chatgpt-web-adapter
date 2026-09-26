from __future__ import annotations

from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_web import (
    GEMINI_PROVIDER_ID,
    GEMINI_WEB_TRANSPORT,
    ORDINARY_GEMINI_PRODUCT_SEMANTICS,
    GeminiBrowserTurnProvider,
    GeminiWebRuntime,
    GeminiWebTransport,
    GeminiWebWriteOutcomeAmbiguousError,
)
from chatgpt_web_adapter.product_capabilities import (
    CONTINUATION,
    NEW_CHAT,
    TEXT_TURNS,
    CapabilityState,
)
from chatgpt_web_adapter.product_provenance import CompletionSource
from chatgpt_web_adapter.product_provider import product_provider_boundary
from chatgpt_web_adapter.product_support import ProductTransportSupportTier

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


class _FakeGeminiProvider(GeminiBrowserTurnProvider):
    def __init__(self) -> None:
        super().__init__(connect_timeout=0.1, turn_timeout=5.0)
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None):
        self.requests.append(dict(payload))
        conversation_id = payload.get("conversationId") or "opaque-1"
        return {
            "protocol": 1,
            "type": "turn_result",
            "request_id": payload["request_id"],
            "ok": True,
            "providerId": GEMINI_PROVIDER_ID,
            "conversationId": conversation_id,
            "responseText": "proof response",
            "finalUrl": "https://gemini.google.com/app/opaque-route",
            "tabId": 17,
            "elapsedMs": 1250,
            "finalityEvidence": "PAGE_DOM_STABLE_COMPLETION",
            "canonicalCompletionProven": False,
            "routeIdentityProven": True,
            "automaticWriteRetry": False,
        }

    def status(self):
        return type(
            "Status",
            (),
            {
                "available": True,
                "extension_connected": True,
                "runtime_tab_id": 17,
            },
        )()


def test_gemini_runtime_passes_provider_boundary_without_canonical_claim() -> None:
    runtime = GeminiWebRuntime(GeminiWebTransport(_FakeGeminiProvider()))

    boundary = product_provider_boundary(runtime)

    assert boundary.provider_id == GEMINI_PROVIDER_ID == "gemini"
    assert boundary.product_semantics == ORDINARY_GEMINI_PRODUCT_SEMANTICS
    assert boundary.transport == GEMINI_WEB_TRANSPORT == "gemini-web"
    assert boundary.canonical_readback_required is False
    assert boundary.canonical_interface is None
    assert boundary.automatic_write_retry is False
    assert boundary.fallback_transport is None


def test_gemini_capability_surface_is_minimal_and_experimental() -> None:
    capabilities = GeminiWebTransport(_FakeGeminiProvider()).capabilities()

    assert (
        capabilities.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL
    )
    assert capabilities.state(TEXT_TURNS) is CapabilityState.AVAILABLE
    assert capabilities.state(NEW_CHAT) is CapabilityState.AVAILABLE
    assert capabilities.state(CONTINUATION) is CapabilityState.AVAILABLE


def test_gemini_new_chat_and_continuation_use_one_rpc_each() -> None:
    provider = _FakeGeminiProvider()

    first = provider.send_text("first")
    second = provider.send_text("second", conversation=first.conversation_id)

    assert first.conversation_id == second.conversation_id == "opaque-1"
    assert len(provider.requests) == 2
    assert provider.requests[0]["providerId"] == "gemini"
    assert provider.requests[0]["conversationId"] is None
    assert provider.requests[1]["conversationId"] == "opaque-1"
    assert all(request["type"] == "turn" for request in provider.requests)


def test_gemini_execution_keeps_page_finality_noncanonical() -> None:
    transport = GeminiWebTransport(_FakeGeminiProvider())

    execution = transport.send_text_observed("hello")

    assert execution.response.text == "proof response"
    assert execution.response.conversation.conversation_id == "opaque-1"
    assert execution.provenance is not None
    assert execution.provenance.completion.source is CompletionSource.TRANSPORT_RETURN
    assert execution.provenance.completion.canonical_completion_proven is False
    assert (
        execution.provenance.completion.finality_detail == "PAGE_DOM_STABLE_COMPLETION"
    )
    assert execution.observation["automatic_write_retry"] is False
    assert execution.observation["route_identity_proven"] is True


def test_gemini_streaming_callbacks_fail_before_write() -> None:
    provider = _FakeGeminiProvider()
    transport = GeminiWebTransport(provider)

    with pytest.raises(ValueError, match="streaming callbacks"):
        transport.send_text("hello", on_event=lambda event: None)

    assert provider.requests == []


def test_extension_assembles_gemini_handler_outside_chatgpt_turn_layers() -> None:
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    base = (EXT / "service_worker.js").read_text(encoding="utf-8")
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    worker = (EXT / "service_worker_gemini_provider.js").read_text(encoding="utf-8")

    assert "https://gemini.google.com/*" in manifest
    assert 'importScripts("service_worker_gemini_provider.js");' in runtime
    assert runtime.index("service_worker_deepseek_provider.js") < runtime.index(
        "service_worker_gemini_provider.js"
    )
    assert runtime.index("service_worker_gemini_provider.js") < runtime.index(
        "service_worker_native_message_router.js"
    )
    assert "registerProductProviderTurnHandler(" in worker
    assert "registerNativeTurnDiagnosticHandler(" not in worker
    assert "CWA_NATIVE_TURN_LAYERS" not in worker
    assert "productProviderTurnHandlers = new Map()" in base

    start = base.index("async function dispatchNativeTurn(message)")
    end = base.index("\nfunction sleep(", start)
    dispatch = base[start:end]
    assert "await dispatchProductProviderTurn(message)" in dispatch
    assert dispatch.index(
        "await dispatchProductProviderTurn(message)"
    ) < dispatch.index("const matching = []")


def test_gemini_worker_uses_page_dom_not_private_http_payloads() -> None:
    worker = (EXT / "service_worker_gemini_provider.js").read_text(encoding="utf-8")

    assert "https://gemini.google.com" in worker
    assert "div.ql-editor" in worker
    assert "rich-textarea" in worker
    assert "model-response" in worker
    assert "message-content" in worker
    assert "CWA_GEMINI_STABLE_MS = 9000" in worker
    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "/api/" not in worker
    assert "Network.enable" not in worker
    assert "Network.request" not in worker
    assert "automaticWriteRetry: false" in worker
    assert 'finalityEvidence: "PAGE_DOM_STABLE_COMPLETION"' in worker
    assert "canonicalCompletionProven: false" in worker
    assert "GEMINI_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED" in worker
    assert "_cwaGeminiSubmitExpression" in worker
    assert "control.click()" in worker
    assert "Input.dispatchKeyEvent" not in worker
    assert "_cwaGeminiReattachForObservation" in worker
    assert "_cwaGeminiPostSubmitAmbiguousError" in worker
    assert "POST_SUBMIT_OBSERVATION_FAILED" in worker
    submit_index = worker.index("await _cwaGeminiSubmitOnce(")
    ambiguity_index = worker.index(
        "throw _cwaGeminiPostSubmitAmbiguousError(error);",
        submit_index,
    )
    assert ambiguity_index > submit_index
    assert worker.count("await _cwaGeminiSubmitOnce(") == 1


def test_gemini_bridge_response_loss_after_delegation_requires_reconciliation() -> None:
    provider = GeminiBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        raise RequestError(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: socket closed",
            request_stage="browser_native_bridge",
        )

    provider._rpc = rpc

    with pytest.raises(GeminiWebWriteOutcomeAmbiguousError) as caught:
        provider.send_text("one delegated turn")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_gemini_predelegation_bridge_failure_remains_ordinary_request_error() -> None:
    provider = GeminiBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        raise RequestError(
            "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: no running bridge",
            request_stage="browser_native_bridge",
        )

    provider._rpc = rpc

    with pytest.raises(RequestError) as caught:
        provider.send_text("not delegated")

    assert not isinstance(caught.value, GeminiWebWriteOutcomeAmbiguousError)


def test_gemini_ambiguous_post_submit_outcome_requires_reconciliation() -> None:
    provider = GeminiBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        return {
            "protocol": 1,
            "type": "turn_result",
            "request_id": payload["request_id"],
            "ok": False,
            "error": (
                "GEMINI_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
                "PAGE_FINALITY_TIMEOUT"
            ),
        }

    provider._rpc = rpc

    with pytest.raises(GeminiWebWriteOutcomeAmbiguousError) as caught:
        provider.send_text("one delegated turn")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False
