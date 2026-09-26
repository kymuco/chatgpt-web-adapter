from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.google_translate_web import (
    GOOGLE_TRANSLATE_PRODUCT_ID,
    GOOGLE_TRANSLATE_TEXT_CAPABILITY,
    GoogleTranslateOutcomeAmbiguousError,
    GoogleTranslateWebRuntime,
)


class _Bridge:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response
        self.payload: dict[str, object] | None = None

    def status(self):
        return SimpleNamespace(available=True, extension_connected=True)

    def _rpc(self, payload, *, timeout, on_event=None):
        self.payload = dict(payload)
        if self.response is None:
            raise AssertionError("synthetic response required")
        return dict(self.response)


def _success_response() -> dict[str, object]:
    return {
        "ok": True,
        "productId": GOOGLE_TRANSLATE_PRODUCT_ID,
        "capability": GOOGLE_TRANSLATE_TEXT_CAPABILITY,
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "translatedText": "La casa es azul.",
        "finalUrl": "https://translate.google.com/?sl=en&tl=es&op=translate",
        "tabId": 17,
        "elapsedMs": 450,
        "finalityEvidence": "PAGE_DOM_STABLE_RESULT",
        "canonicalResultProven": False,
        "automaticWriteRetry": False,
        "fallbackTransport": None,
        "conversationSemantics": False,
    }


def test_google_translate_runtime_is_explicitly_non_chat() -> None:
    runtime = GoogleTranslateWebRuntime(bridge=_Bridge(_success_response()))

    assert runtime.product_id == "google-translate"
    assert runtime.product_semantics == "google-translate-web-text"
    assert runtime.transport == "google-translate-web"
    assert runtime.capability == "translate_text"
    assert runtime.support_tier == "EXPERIMENTAL"

    assert not hasattr(runtime, "provider_id")
    assert not hasattr(runtime, "capabilities")
    assert not hasattr(runtime, "send_text")
    assert not hasattr(runtime, "write_transport")

    with pytest.raises((TypeError, ValueError), match="provider_id"):
        adapter.product_provider_boundary(runtime)


def test_google_translate_translation_has_structured_parameters_without_conversation() -> None:
    bridge = _Bridge(_success_response())
    runtime = GoogleTranslateWebRuntime(bridge=bridge)

    result = runtime.translate(
        "The house is blue.",
        source_language="en",
        target_language="es",
    )

    assert result.text == "La casa es azul."
    assert result.source_language == "en"
    assert result.target_language == "es"
    assert result.finality_evidence == "PAGE_DOM_STABLE_RESULT"
    assert result.canonical_result_proven is False
    assert result.automatic_write_retry is False
    assert result.fallback_transport is None
    assert result.conversation_semantics is False

    assert bridge.payload is not None
    assert bridge.payload["type"] == "translate_text"
    assert bridge.payload["text"] == "The house is blue."
    assert bridge.payload["sourceLanguage"] == "en"
    assert bridge.payload["targetLanguage"] == "es"
    assert "conversationId" not in bridge.payload
    assert "providerId" not in bridge.payload


def test_google_translate_governance_refuses_schema2_claim() -> None:
    runtime = GoogleTranslateWebRuntime(bridge=_Bridge(_success_response()))
    governance = runtime.governance()

    assert governance["product_provider_boundary_schema"] is None
    assert governance["implements_product_write_transport"] is False
    assert governance["conversation_semantics"] is False
    assert governance["canonical_result_interface"] is None
    assert governance["canonical_result_proven"] is False
    assert governance["automatic_write_retry"] is False
    assert governance["fallback_transport"] is None
    assert governance["ambiguous_operation_requires_reconciliation"] is True
    assert governance["browser_owned"] is True
    assert governance["official_api_used"] is False
    assert governance["private_http_protocol_used"] is False


def test_google_translate_bridge_response_loss_after_delegation_is_ambiguous() -> None:
    class LostBridge(_Bridge):
        def _rpc(self, payload, *, timeout, on_event=None):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: socket closed",
                request_stage="browser_native_bridge",
            )

    runtime = GoogleTranslateWebRuntime(bridge=LostBridge())

    with pytest.raises(GoogleTranslateOutcomeAmbiguousError) as caught:
        runtime.translate("Hello", source_language="en", target_language="es")

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_google_translate_predelegation_failure_remains_ordinary() -> None:
    class MissingBridge(_Bridge):
        def _rpc(self, payload, *, timeout, on_event=None):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: missing",
                request_stage="browser_native_bridge",
            )

    runtime = GoogleTranslateWebRuntime(bridge=MissingBridge())

    with pytest.raises(RequestError) as caught:
        runtime.translate("Hello", source_language="en", target_language="es")

    assert not isinstance(caught.value, GoogleTranslateOutcomeAmbiguousError)


def test_google_translate_module_does_not_import_chat_product_contracts() -> None:
    from chatgpt_web_adapter import google_translate_web

    source = inspect.getsource(google_translate_web)

    assert "from .product_" not in source
    assert "ChatResponse" not in source
    assert "ConversationRef" not in source
    assert "ChatConversation" not in source


def test_google_translate_worker_is_page_owned_without_chat_turn_registration() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    worker = (
        root
        / "src"
        / "chatgpt_web_adapter"
        / "browser_native_extension"
        / "service_worker_google_translate.js"
    ).read_text(encoding="utf-8")

    assert 'message?.type !== "translate_text"' in worker
    assert "registerProductProviderTurnHandler" not in worker
    assert "conversationId" not in worker
    assert "providerId" not in worker
    assert "control.click()" not in worker
    assert "fetch(" not in worker
    assert "Network." not in worker
    assert "Runtime.evaluate" in worker
    assert "translated=texts.join(' ')" in worker
    assert "texts[texts.length-1]" not in worker
    assert "PAGE_DOM_STABLE_RESULT" in worker
    assert "canonicalResultProven: false" in worker
    assert "automaticWriteRetry: false" in worker
    assert "conversationSemantics: false" in worker


def test_google_translate_native_operation_uses_existing_authority_lane() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    host = (root / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )
    router = (
        root
        / "src"
        / "chatgpt_web_adapter"
        / "browser_native_extension"
        / "service_worker_native_message_router.js"
    ).read_text(encoding="utf-8")

    assert '"translate_text",' in host
    assert '"translate_text": 45_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host

    translate = router.index("_cwaOnNativeMessageWithGoogleTranslate")
    ui = router.index("_cwaOnNativeMessageWithUiLiveness")
    assert translate < ui


def test_google_translate_runtime_is_not_root_public_surface() -> None:
    assert not hasattr(adapter, "GoogleTranslateWebRuntime")
    assert adapter.public_surface_tier("GoogleTranslateWebRuntime") is None
