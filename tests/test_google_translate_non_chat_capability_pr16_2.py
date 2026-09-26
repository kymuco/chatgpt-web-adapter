from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.google_translate_web import (
    GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
    GOOGLE_TRANSLATE_WEB_FINALITY,
    GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
    GOOGLE_TRANSLATE_WEB_SUPPORT_TIER,
    GoogleTranslateOutcomeAmbiguousError,
    GoogleTranslateWebCapability,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def status(self) -> BrowserNativeBridgeStatus:
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
        )

    def _rpc(self, payload, *, timeout, on_event=None):
        self.requests.append(dict(payload))
        return {
            "protocol": 1,
            "type": "translate_text_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
            "capabilityId": GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
            "translatedText": "Hola",
            "sourceLanguage": payload["sourceLanguage"],
            "targetLanguage": payload["targetLanguage"],
            "finalUrl": (
                "https://translate.google.com/?sl=en&tl=es&op=translate"
            ),
            "tabId": 17,
            "elapsedMs": 321,
            "finalityEvidence": GOOGLE_TRANSLATE_WEB_FINALITY,
            "canonicalCompletionProven": False,
            "automaticRetry": False,
        }


def test_google_translate_capability_is_non_chat_module_only() -> None:
    assert GOOGLE_TRANSLATE_WEB_SUPPORT_TIER == "EXPERIMENTAL"
    assert GOOGLE_TRANSLATE_WEB_PRODUCT_ID == "google-translate-web"
    assert GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID == "translate_text"
    assert not hasattr(adapter, "GoogleTranslateWebCapability")


def test_google_translate_text_contract_has_no_conversation_identity() -> None:
    bridge = _FakeBridge()
    capability = GoogleTranslateWebCapability(bridge=bridge)

    result = capability.translate_text(
        "hello",
        source_language="en",
        target_language="es",
    )

    assert result.translated_text == "Hola"
    assert result.source_language == "en"
    assert result.target_language == "es"
    assert result.finality_evidence == "PAGE_DOM_STABLE_TRANSLATION"
    assert result.canonical_completion_proven is False
    assert result.automatic_retry is False

    [request] = bridge.requests
    assert request["type"] == "translate_text"
    assert request["productId"] == "google-translate-web"
    assert request["text"] == "hello"
    assert request["sourceLanguage"] == "en"
    assert request["targetLanguage"] == "es"
    assert "conversationId" not in request
    assert "providerId" not in request


def test_google_translate_language_validation_fails_before_bridge_write() -> None:
    bridge = _FakeBridge()
    capability = GoogleTranslateWebCapability(bridge=bridge)

    with pytest.raises(ValueError, match="target_language cannot be auto"):
        capability.translate_text(
            "hello",
            source_language="en",
            target_language="auto",
        )

    with pytest.raises(ValueError, match="bounded language code"):
        capability.translate_text(
            "hello",
            source_language="not a language",
            target_language="es",
        )

    assert bridge.requests == []


def test_google_translate_bridge_response_loss_requires_reconciliation() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: socket closed",
                request_stage="browser_native_bridge",
            )

    capability = GoogleTranslateWebCapability(bridge=_LostBridge())

    with pytest.raises(GoogleTranslateOutcomeAmbiguousError) as caught:
        capability.translate_text(
            "hello",
            source_language="en",
            target_language="es",
        )

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_google_translate_predelegation_bridge_failure_remains_ordinary() -> None:
    class _UnavailableBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: no running bridge",
                request_stage="browser_native_bridge",
            )

    capability = GoogleTranslateWebCapability(bridge=_UnavailableBridge())

    with pytest.raises(RequestError) as caught:
        capability.translate_text(
            "hello",
            source_language="en",
            target_language="es",
        )

    assert not isinstance(caught.value, GoogleTranslateOutcomeAmbiguousError)


def test_google_translate_page_outcome_ambiguity_requires_reconciliation() -> None:
    class _AmbiguousBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None):
            return {
                "protocol": 1,
                "type": "translate_text_result",
                "request_id": payload["request_id"],
                "ok": False,
                "error": (
                    "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
                    "PAGE_RESULT_TIMEOUT"
                ),
            }

    capability = GoogleTranslateWebCapability(bridge=_AmbiguousBridge())

    with pytest.raises(GoogleTranslateOutcomeAmbiguousError) as caught:
        capability.translate_text(
            "hello",
            source_language="en",
            target_language="es",
        )

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_google_translate_extension_is_explicit_non_chat_route() -> None:
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    router = (EXT / "service_worker_native_message_router.js").read_text(
        encoding="utf-8"
    )
    worker = (
        EXT / "service_worker_google_translate_capability.js"
    ).read_text(encoding="utf-8")

    assert "https://translate.google.com/*" in manifest
    assert (
        'importScripts("service_worker_google_translate_capability.js");'
        in runtime
    )
    assert runtime.index("service_worker_gemini_provider.js") < runtime.index(
        "service_worker_google_translate_capability.js"
    )
    assert runtime.index(
        "service_worker_google_translate_capability.js"
    ) < runtime.index("service_worker_native_message_router.js")

    assert "_cwaOnNativeMessageWithGoogleTranslate(" in router
    assert 'message?.type !== "translate_text"' in worker
    assert "registerProductProviderTurnHandler(" not in worker
    assert "dispatchProductProviderTurn(" not in worker
    assert "conversationId" not in worker


def test_google_translate_worker_uses_page_owned_dom_not_private_http() -> None:
    worker = (
        EXT / "service_worker_google_translate_capability.js"
    ).read_text(encoding="utf-8")

    assert "https://translate.google.com" in worker
    assert "textarea" in worker
    assert 'jsname=\\\"W297wb\\\"' in worker
    assert "InputEvent('input'" in worker
    assert "PAGE_DOM_STABLE_TRANSLATION" in worker
    assert "canonicalCompletionProven: false" in worker
    assert "automaticRetry: false" in worker
    assert "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED" in worker

    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "translate_a/" not in worker
    assert "Network.enable" not in worker
    assert "Network.request" not in worker
    assert ".click()" not in worker


def test_google_translate_authority_lane_is_shared_without_canonical_reservation() -> None:
    host = (
        ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py"
    ).read_text(encoding="utf-8")

    assert '"translate_text",' in host
    assert '"translate_text": 30_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
    assert 'operation == "translate_text"' not in host.split(
        "if lease_id is not None and (", 1
    )[1].split("return message", 1)[0]


def test_google_translate_live_gate_is_acceptance_only() -> None:
    gate = (
        ROOT / "src" / "chatgpt_web_adapter" / "google_translate_web_live_gate.py"
    ).read_text(encoding="utf-8")

    assert 'source_language="en"' in gate
    assert 'target_language="es"' in gate
    assert '"hola"' in gate
    assert '"conversation_semantics": False' in gate
