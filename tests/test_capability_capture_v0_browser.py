from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from tools.capability_capture_v0_browser import (
    capture_demo,
    validate_capture_trace,
)

ROOT = Path(__file__).resolve().parents[1]
JS = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_capability_capture_v0.js"
)


def _result() -> dict:
    return {
        "type": "research_capture_translate_demo_v0_result",
        "ok": True,
        "schema": "CWA_CAPTURE_V0_STRUCTURAL_TRACE",
        "productId": "google-translate-web",
        "captureMode": "EXPLICIT_OBSERVE_ONLY",
        "observedTabId": 27,
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "events": [
            {"phase": "source_ready", "t_ms": 0, "role": "textbox"},
            {"phase": "source_input_event", "t_ms": 201},
            {"phase": "result_candidate_seen", "t_ms": 400},
            {"phase": "result_candidate_presence_stable", "t_ms": 1620},
        ],
        "inputEventCount": 3,
        "routeVerified": True,
        "candidatePresenceStable": True,
        "candidateIdentityResolved": True,
        "canonicalCompletionProven": False,
        "semanticFinalityProven": False,
        "effectBoundary": "MANUAL_REFERENCE_ONLY_SOURCE_INPUT",
        "automaticRetry": False,
        "replayExecutable": False,
        "rawContentRetained": False,
    }


class _FakeBridge:
    def __init__(self, response=None, error=None):
        self.response = _result() if response is None else response
        self.error = error
        self.requests: list[dict] = []
        self.options: list[dict] = []

    def _rpc(self, request, **kwargs):
        self.requests.append(dict(request))
        self.options.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.response)


def test_explicit_capture_uses_only_observational_operation() -> None:
    bridge = _FakeBridge()
    result = capture_demo(
        bridge, tab_id=27, source_language="en", target_language="es",
        seconds=8, explicit_consent=True,
    )
    assert result == _result()
    [request] = bridge.requests
    assert request["type"] == "research_capture_translate_demo_v0"
    assert request["consent"] == "EXPLICIT_OBSERVE_ONLY"
    assert request["captureSeconds"] == 8
    assert request["timeoutMs"] == 12000
    assert not {"text", "sourceText", "translatedText", "conversationId"} & set(request)
    [options] = bridge.options
    assert options["timeout"] == 15.0
    assert options["delegated_timeout_ms_key"] == "timeoutMs"
    assert options["delegated_response_margin"] == 2.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"explicit_consent": False},
        {"tab_id": 0},
        {"tab_id": True},
        {"seconds": 2},
        {"seconds": 21},
        {"source_language": "invalid language"},
        {"target_language": "es?token=foo"},
    ],
)
def test_preflight_rejects_unsafe_requests_without_rpc(kwargs: dict) -> None:
    bridge = _FakeBridge()
    values = {
        "tab_id": 27, "source_language": "en", "target_language": "es",
        "seconds": 8, "explicit_consent": True,
    }
    values.update(kwargs)
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        capture_demo(bridge, **values)
    assert not bridge.requests


def test_bridge_response_loss_is_not_retried() -> None:
    bridge = _FakeBridge(
        error=RequestError(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION",
            request_stage="browser_native_bridge",
        )
    )
    with pytest.raises(RequestError, match="RESPONSE_LOST_AFTER_DELEGATION"):
        capture_demo(
            bridge, tab_id=27, source_language="en",
            target_language="es", explicit_consent=True,
        )
    assert len(bridge.requests) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"canonicalCompletionProven": True},
        {"semanticFinalityProven": True},
        {"automaticRetry": True},
        {"replayExecutable": True},
        {"rawContentRetained": True},
        {"productId": "chatgpt-web"},
        {"routeVerified": False},
        {"sourceLanguage": "de"},
        {"observedTabId": 26},
        {"captureMode": "AUTO"},
        {"inputEventCount": 65},
        {"candidatePresenceStable": False},
        {"candidateIdentityResolved": False},
    ],
)
def test_trace_fails_closed_on_identity_or_authority_mismatch(change: dict) -> None:
    response = _result()
    response.update(change)
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        validate_capture_trace(
            response, tab_id=27, source_language="en", target_language="es"
        )


def test_trace_never_exports_extra_browser_or_page_data() -> None:
    response = _result()
    response["rawDom"] = "secret"
    response["translatedText"] = "sensitive text"
    response["networkBody"] = "private"
    result = validate_capture_trace(
        response, tab_id=27, source_language="en", target_language="es"
    )
    assert not {"rawDom", "translatedText", "networkBody"} & set(result)
    response["events"][1]["typedText"] = "secret"
    with pytest.raises(ValueError, match="CAPTURE_V0_UNBOUNDED_EVENT"):
        validate_capture_trace(
            response, tab_id=27, source_language="en", target_language="es"
        )


def test_incomplete_capture_is_valid_observation_not_successful_replay() -> None:
    response = _result()
    response["events"] = [{"phase": "source_ready", "t_ms": 0, "role": "textbox"}]
    response["inputEventCount"] = 0
    response["candidatePresenceStable"] = False
    response["candidateIdentityResolved"] = False
    result = validate_capture_trace(
        response, tab_id=27, source_language="en", target_language="es"
    )
    assert result["replayExecutable"] is False
    assert result["semanticFinalityProven"] is False


@pytest.mark.parametrize(
    "events",
    [
        [{"phase": "source_input_event", "t_ms": 1}],
        [{"phase": "source_ready", "t_ms": 0, "role": "textbox"},
         {"phase": "result_candidate_seen", "t_ms": 2}],
        [{"phase": "source_ready", "t_ms": 0, "role": "textbox"},
         {"phase": "source_input_event", "t_ms": -1}],
        [{"phase": "source_ready", "t_ms": 0, "role": "textbox"},
         {"phase": "source_input_event", "t_ms": 35000}],
    ],
)
def test_trace_rejects_misordered_or_unbounded_timeline(events: list) -> None:
    response = _result()
    response["events"] = events
    with pytest.raises(ValueError, match="CAPTURE_V0"):
        validate_capture_trace(
            response, tab_id=27, source_language="en", target_language="es"
        )


def test_browser_capture_wiring_stays_research_only() -> None:
    extension = JS.parent
    worker = JS.read_text(encoding="utf-8")
    runtime = (extension / "service_worker_runtime.js").read_text(encoding="utf-8")
    router = (extension / "service_worker_native_message_router.js").read_text(
        encoding="utf-8"
    )
    host = (
        ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py"
    ).read_text(encoding="utf-8")

    assert "research_capture_translate_demo_v0" in worker
    assert 'importScripts("service_worker_capability_capture_v0.js")' in runtime
    assert "_cwaOnNativeMessageWithCaptureV0(" in router
    assert '"research_capture_translate_demo_v0": 30_000' in host
    assert "chrome.tabs.create" not in worker
    assert "chrome.tabs.update" not in worker
    assert "Input.dispatchKeyEvent" not in worker
    assert "Input.insertText" not in worker
    assert ".click()" not in worker
    assert "fetch(" not in worker
    assert "Network.enable" not in worker
    assert "Network.getResponseBody" not in worker
    assert "window.open" not in worker
    assert "document.addEventListener('input'" in worker
    assert "document.removeEventListener('input'" in worker
    assert "chrome.debugger.detach" in worker
    assert 'replayExecutable: false' in worker


def test_browser_capture_worker_js_syntax_and_dom_fixture() -> None:
    subprocess.run(
        ["node", "--check", str(JS)], check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["node", str(ROOT / "tools" / "capability_capture_v0_dom_fixture.js")],
        check=True, capture_output=True, text=True,
    )
