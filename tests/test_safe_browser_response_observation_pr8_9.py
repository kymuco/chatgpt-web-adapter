from __future__ import annotations

import pytest

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir
from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)
from chatgpt_web_adapter.safe_browser_response_observation_pr8_9 import (
    SafeBrowserResponseObservationProvider,
    summarize_safe_browser_stream,
)


def test_worker_is_loaded_after_pr8_8_selection_stack() -> None:
    root = browser_native_extension_dir()
    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    prior = 'importScripts("service_worker_instant_effort_slider_support_pr8_8.js")'
    current = 'importScripts("service_worker_safe_browser_response_stream_pr8_9.js")'
    assert prior in observability
    assert current in observability
    assert observability.index(prior) < observability.index(current)


def test_worker_uses_bounded_non_intercepting_cdp_stream_observation() -> None:
    root = browser_native_extension_dir()
    source = (
        root / "service_worker_safe_browser_response_stream_pr8_9.js"
    ).read_text(encoding="utf-8")

    for token in (
        "Network.streamResourceContent",
        "Network.dataReceived",
        "Network.responseReceived",
        "Network.loadingFinished",
        "isConversationWrite(",
        "characterizeSafeBrowserResponseStreaming",
        "preNetworkCompleteTextObserved",
        "observationsTruncated",
        "SHA-256",
    ):
        assert token in source

    for forbidden in (
        "Network.getResponseBody",
        "Network.getRequestPostData",
        "Fetch.enable",
        "Fetch.fulfillRequest",
        "Fetch.failRequest",
        "Fetch.continueRequest",
        "document.cookie",
        "request.headers",
        "Authorization",
        "set-cookie",
    ):
        assert forbidden not in source


def test_provider_injects_characterization_only_into_one_armed_product_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_rpc(self, payload, *, timeout):
        calls.append(dict(payload))
        return {
            "ok": True,
            "safeBrowserResponseStreaming": {
                "schemaVersion": 1,
                "source": "CDP_NETWORK_STREAM_RESOURCE_CONTENT",
            },
        }

    monkeypatch.setattr(BrowserAuthorityCharacterizationProvider, "_rpc", fake_rpc)

    provider = SafeBrowserResponseObservationProvider()
    provider.arm_stream_probe()
    response = provider._rpc(
        {"type": "turn", "text": "hello", "conversationId": "c1"},
        timeout=1.0,
    )
    provider.disarm_stream_probe()

    assert response["ok"] is True
    assert calls == [
        {
            "type": "turn",
            "text": "hello",
            "conversationId": "c1",
            "characterizeSafeBrowserResponseStreaming": True,
        }
    ]
    assert provider.last_safe_browser_stream == {
        "schemaVersion": 1,
        "source": "CDP_NETWORK_STREAM_RESOURCE_CONTENT",
    }

    calls.clear()
    provider._rpc(
        {"type": "turn", "text": "normal", "conversationId": "c1"},
        timeout=1.0,
    )
    assert calls[0].get("characterizeSafeBrowserResponseStreaming") is None


def test_provider_enforces_single_product_write_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_rpc(self, payload, *, timeout):
        return {"ok": True, "safeBrowserResponseStreaming": {}}

    monkeypatch.setattr(BrowserAuthorityCharacterizationProvider, "_rpc", fake_rpc)

    provider = SafeBrowserResponseObservationProvider()
    provider.arm_stream_probe()
    provider._rpc({"type": "turn", "text": "one"}, timeout=1.0)
    with pytest.raises(
        RuntimeError,
        match="PR8_9_BROWSER_STREAM_PRODUCT_WRITE_BUDGET_EXCEEDED",
    ):
        provider._rpc({"type": "turn", "text": "two"}, timeout=1.0)


def test_summary_proves_early_browser_text_and_exact_final_reconciliation() -> None:
    final_text = "alpha beta gamma"
    from hashlib import sha256

    digest = sha256(final_text.encode("utf-8")).hexdigest()
    stream = {
        "source": "CDP_NETWORK_STREAM_RESOURCE_CONTENT",
        "experimentalCdpMethod": True,
        "conversationRequestObserved": True,
        "responseStatus": 200,
        "responseMimeType": "text/event-stream",
        "streamResourceContentAttempted": True,
        "streamResourceContentSupported": True,
        "bufferedByteLength": 10,
        "dataEventCount": 3,
        "dataByteLength": 40,
        "sseEventCount": 3,
        "jsonEventCount": 3,
        "assistantTextEventCount": 2,
        "firstTextObservedMs": 100,
        "lastTextObservedMs": 250,
        "loadingFinishedMs": 900,
        "firstTextLeadBeforeNetworkCompleteMs": 800,
        "preNetworkCompleteTextObserved": True,
        "observations": [
            {
                "kind": "SNAPSHOT",
                "textLength": 5,
                "textSha256": sha256(b"alpha").hexdigest(),
            },
            {
                "kind": "DELTA",
                "textLength": len(final_text),
                "textSha256": digest,
            },
        ],
    }

    summary = summarize_safe_browser_stream(stream, final_text=final_text)

    assert summary["useful_safe_browser_response_observation_supported"] is True
    assert summary["stream_canonical_reconciliation"] == "EXACT_MATCH"
    assert summary["first_text_lead_before_network_complete_ms"] == 800
    assert summary["delta_count"] == 1
    assert summary["revision_count"] == 0


def test_summary_does_not_promote_empty_or_post_final_observation() -> None:
    stream = {
        "streamResourceContentSupported": True,
        "firstTextObservedMs": 1000,
        "loadingFinishedMs": 900,
        "preNetworkCompleteTextObserved": False,
        "observations": [],
    }
    summary = summarize_safe_browser_stream(stream, final_text="final")
    assert summary["useful_safe_browser_response_observation_supported"] is False
    assert summary["stream_canonical_reconciliation"] == "UNAVAILABLE"