from __future__ import annotations

from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.product_capabilities import (
    CONTINUATION,
    NEW_CHAT,
    TEXT_TURNS,
    CapabilityState,
)
from chatgpt_web_adapter.product_provenance import CompletionSource
from chatgpt_web_adapter.product_provider import product_provider_boundary
from chatgpt_web_adapter.product_support import ProductTransportSupportTier
from chatgpt_web_adapter.qwen_web import (
    ORDINARY_QWEN_PRODUCT_SEMANTICS,
    QWEN_PROVIDER_ID,
    QWEN_WEB_TRANSPORT,
    QwenBrowserTurnProvider,
    QwenWebRuntime,
    QwenWebTransport,
    QwenWebWriteOutcomeAmbiguousError,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


class _FakeQwenProvider(QwenBrowserTurnProvider):
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
            "providerId": QWEN_PROVIDER_ID,
            "conversationId": conversation_id,
            "responseText": "proof response",
            "finalUrl": "https://chat.qwen.ai/c/opaque-route",
            "tabId": 17,
            "elapsedMs": 1250,
            "finalityEvidence": "PAGE_DOM_STABLE_COMPLETION",
            "canonicalCompletionProven": False,
            "routeIdentityProven": True,
            "automaticWriteRetry": False,
            "networkStreamVerified": payload.get("streamNetwork") is True,
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


def test_qwen_runtime_passes_provider_boundary_without_canonical_claim() -> None:
    runtime = QwenWebRuntime(QwenWebTransport(_FakeQwenProvider()))

    boundary = product_provider_boundary(runtime)

    assert boundary.provider_id == QWEN_PROVIDER_ID == "qwen"
    assert boundary.product_semantics == ORDINARY_QWEN_PRODUCT_SEMANTICS
    assert boundary.transport == QWEN_WEB_TRANSPORT == "qwen-web"
    assert boundary.canonical_readback_required is False
    assert boundary.canonical_interface is None
    assert boundary.automatic_write_retry is False
    assert boundary.fallback_transport is None


def test_qwen_capability_surface_is_minimal_and_experimental() -> None:
    capabilities = QwenWebTransport(_FakeQwenProvider()).capabilities()

    assert (
        capabilities.transport_support_tier is ProductTransportSupportTier.EXPERIMENTAL
    )
    assert capabilities.state(TEXT_TURNS) is CapabilityState.UNKNOWN
    assert capabilities.state(NEW_CHAT) is CapabilityState.UNKNOWN
    assert capabilities.state(CONTINUATION) is CapabilityState.UNKNOWN


def test_qwen_new_chat_and_continuation_use_one_rpc_each() -> None:
    provider = _FakeQwenProvider()

    first = provider.send_text("first")
    second = provider.send_text("second", conversation=first.conversation_id)

    assert first.conversation_id == second.conversation_id == "opaque-1"
    assert len(provider.requests) == 2
    assert provider.requests[0]["providerId"] == "qwen"
    assert provider.requests[0]["conversationId"] is None
    assert provider.requests[1]["conversationId"] == "opaque-1"
    assert all(request["type"] == "turn" for request in provider.requests)


def test_qwen_execution_keeps_page_finality_noncanonical() -> None:
    transport = QwenWebTransport(_FakeQwenProvider())

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


def test_qwen_streaming_callbacks_fail_before_write() -> None:
    provider = _FakeQwenProvider()
    transport = QwenWebTransport(provider)

    with pytest.raises(ValueError, match="streaming callbacks"):
        transport.send_text("hello", on_event=lambda event: None)

    assert provider.requests == []


def test_extension_assembles_qwen_handler_outside_chatgpt_turn_layers() -> None:
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    base = (EXT / "service_worker.js").read_text(encoding="utf-8")
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    worker = (EXT / "service_worker_qwen_provider.js").read_text(encoding="utf-8")

    assert "https://chat.qwen.ai/*" in manifest
    assert 'importScripts("service_worker_qwen_provider.js");' in runtime
    assert runtime.index("service_worker_qwen_provider.js") < runtime.index(
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


def test_qwen_worker_uses_page_dom_not_private_http_payloads() -> None:
    worker = (EXT / "service_worker_qwen_provider.js").read_text(encoding="utf-8")

    assert "https://chat.qwen.ai" in worker
    assert "div.response-message-content.phase-answer" in worker
    assert "button.stop-button" in worker
    assert "CWA_QWEN_STABLE_MS = 9000" in worker
    assert "_cwaQwenIsConversationRoute" in worker
    assert "textarea.message-input-textarea" in worker
    assert "button.send-button" in worker
    assert "composer.value !== requestedText" in worker
    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "/api/" not in worker
    assert "Network.enable" not in worker
    assert "Network.request" not in worker
    assert "automaticWriteRetry: false" in worker
    assert 'finalityEvidence: "PAGE_DOM_STABLE_COMPLETION"' in worker
    assert "canonicalCompletionProven: false" in worker
    assert "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED" in worker
    assert "_cwaQwenSubmitExpression" in worker
    assert "control.click()" in worker
    assert "Input.dispatchKeyEvent" not in worker
    assert "_cwaQwenReattachForObservation" in worker
    assert "_cwaQwenPostSubmitAmbiguousError" in worker
    assert "POST_SUBMIT_OBSERVATION_FAILED" in worker
    submit_helper_start = worker.index("async function _cwaQwenSubmitOnce(")
    submit_helper_end = worker.index(
        "\nfunction _cwaQwenLatestNewText",
        submit_helper_start,
    )
    submit_helper = worker[submit_helper_start:submit_helper_end]
    assert "DebuggerDetached(error)" in submit_helper
    assert "throw _cwaQwenPostSubmitAmbiguousError(error);" in submit_helper
    assert "throw error;" not in submit_helper
    submit_index = worker.index("await _cwaQwenSubmitOnce(")
    ambiguity_index = worker.index(
        "throw _cwaQwenPostSubmitAmbiguousError(error);",
        submit_index,
    )
    assert ambiguity_index > submit_index
    assert worker.count("await _cwaQwenSubmitOnce(") == 1


def test_qwen_bridge_response_loss_after_delegation_requires_reconciliation() -> None:
    provider = QwenBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        raise RequestError(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: socket closed",
            request_stage="browser_native_bridge",
        )

    provider._rpc = rpc

    with pytest.raises(QwenWebWriteOutcomeAmbiguousError) as caught:
        provider.send_text("one delegated turn")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_qwen_predelegation_bridge_failure_remains_ordinary_request_error() -> None:
    provider = QwenBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        raise RequestError(
            "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: no running bridge",
            request_stage="browser_native_bridge",
        )

    provider._rpc = rpc

    with pytest.raises(RequestError) as caught:
        provider.send_text("not delegated")

    assert not isinstance(caught.value, QwenWebWriteOutcomeAmbiguousError)


def test_qwen_ambiguous_post_submit_outcome_requires_reconciliation() -> None:
    provider = QwenBrowserTurnProvider(connect_timeout=0.1, turn_timeout=5.0)

    def rpc(payload, *, timeout, on_event=None):
        return {
            "protocol": 1,
            "type": "turn_result",
            "request_id": payload["request_id"],
            "ok": False,
            "error": (
                "QWEN_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
                "PAGE_FINALITY_TIMEOUT"
            ),
        }

    provider._rpc = rpc

    with pytest.raises(QwenWebWriteOutcomeAmbiguousError) as caught:
        provider.send_text("one delegated turn")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_qwen_extension_syntax_if_node_available() -> None:
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js not installed")
    result = subprocess.run(
        [node, "--check", str(EXT / "service_worker_qwen_provider.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_qwen_auth_export_is_explicit_and_separate_from_page_turn() -> None:
    worker = (EXT / "service_worker_qwen_provider.js").read_text(encoding="utf-8")
    turn = worker.split("async function _cwaQwenHandleTurn(message) {", 1)[1]
    assert 'if (message?.operation === "export_auth")' in turn
    assert "QWEN_TEXT_REQUIRED" in turn
    assert "localStorage.getItem" not in turn
    assert "Network.getCookies" not in turn
    assert "Authorization" not in worker
    assert "chrome.cookies" not in worker
    assert '["new-chat", "guest"]' in worker


def test_qwen_browser_turn_creates_background_tab_without_replacing_chats() -> None:
    source = (EXT / "service_worker_qwen_provider.js").read_text(encoding="utf-8")
    assert 'chrome.tabs.create({url: CWA_QWEN_ORIGIN + "/", active: false})' in source
    assert "chrome.tabs.update(" not in source
    assert "chrome.tabs.query(" in source
    assert "QWEN_NEW_CHAT_TAB_NOT_OPEN" in source
    assert "QWEN_CONTINUATION_TAB_NOT_OPEN" in source
    assert "_cwaQwenIsEmptyChatRoute" in source


def test_qwen_browser_stream_delivers_snapshots_including_revisions():
    provider = _FakeQwenProvider()
    original_rpc = provider._rpc

    def rpc(payload, *, timeout, on_event=None):
        assert payload["streamTextObservations"] is True
        for text in ["Hello", "Hello world", "Corrected answer"]:
            on_event({"providerId": "qwen", "type": "text_snapshot", "text": text})
        on_event({"providerId": "other", "type": "text_snapshot", "text": "wrong"})
        return original_rpc(payload, timeout=timeout)

    provider._rpc = rpc
    snapshots = []
    result = QwenWebTransport(provider).send_text("hello", on_text=snapshots.append)
    assert snapshots == ["Hello", "Hello world", "Corrected answer"]
    assert result.text == "proof response"
    assert len(provider.requests) == 1


def test_qwen_network_tokens_pass_through_without_dom_substitution():
    provider = _FakeQwenProvider()
    original_rpc = provider._rpc

    def rpc(payload, *, timeout, on_event=None):
        assert payload["streamNetwork"] is True
        assert payload["streamTextObservations"] is False
        on_event({"providerId": "qwen", "type": "text_delta", "text": "A"})
        on_event({"providerId": "qwen", "type": "text_snapshot", "text": "ignored"})
        on_event({"providerId": "qwen", "type": "text_delta", "text": "B"})
        return original_rpc(payload, timeout=timeout)

    provider._rpc = rpc
    tokens = []
    QwenWebTransport(provider).send_text("hello", on_token=tokens.append)
    assert tokens == ["A", "B"]
