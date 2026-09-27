from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_web import (
    GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID,
    GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION,
    GEMINI_NOTEBOOK_WEB_FINALITY,
    GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
    GEMINI_NOTEBOOK_WEB_SUPPORT_TIER,
    GeminiNotebookOutcomeAmbiguousError,
    GeminiNotebookWebCapability,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
NOTEBOOK = (
    "https://notebook.google.com/notebook/"
    "564ab6b8-c253-4f1a-b104-6f8026d67c76"
)


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.rpc_options: list[dict[str, object]] = []

    def status(self) -> BrowserNativeBridgeStatus:
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
        )

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        self.rpc_options.append({"timeout": timeout, **kwargs})
        return {
            "protocol": 1,
            "type": "gemini_notebook_add_url_source_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
            "capabilityId": GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID,
            "notebookUrl": payload["notebookUrl"],
            "sourceUrl": payload["sourceUrl"],
            "sourceTitle": "IANA-managed Reserved Domains",
            "observedRowRef": "row-ref-1",
            "sourceRowCountBefore": 1,
            "sourceRowCountAfter": 2,
            "tabId": 17,
            "elapsedMs": 321,
            "finalityEvidence": GEMINI_NOTEBOOK_WEB_FINALITY,
            "canonicalCompletionProven": False,
            "automaticRetry": False,
        }


def test_gemini_notebook_url_source_is_module_only_persistent_capability() -> None:
    assert GEMINI_NOTEBOOK_WEB_SUPPORT_TIER == "EXPERIMENTAL"
    assert GEMINI_NOTEBOOK_WEB_PRODUCT_ID == "gemini-notebook-web"
    assert GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID == "add_url_source"
    assert GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION == (
        "gemini_notebook_add_url_source"
    )
    assert not hasattr(adapter, "GeminiNotebookWebCapability")


def test_gemini_notebook_add_url_source_contract() -> None:
    bridge = _FakeBridge()
    capability = GeminiNotebookWebCapability(bridge=bridge)

    result = capability.add_url_source(
        notebook=NOTEBOOK + "?addSource=true",
        source_url="https://www.iana.org/help/example-domains",
    )

    assert result.notebook_url == NOTEBOOK
    assert result.source_title == "IANA-managed Reserved Domains"
    assert result.observed_row_ref == "row-ref-1"
    assert result.source_row_count_before == 1
    assert result.source_row_count_after == 2
    assert result.finality_evidence == "PAGE_DOM_DURABLE_SOURCE_ADMISSION"
    assert result.canonical_completion_proven is False
    assert result.automatic_retry is False

    [request] = bridge.requests
    assert request["type"] == "gemini_notebook_add_url_source"
    assert request["productId"] == "gemini-notebook-web"
    assert request["capabilityId"] == "add_url_source"
    assert request["timeoutMs"] == 1
    [rpc_options] = bridge.rpc_options
    assert rpc_options["delegated_timeout_ms_key"] == "timeoutMs"
    assert rpc_options["delegated_response_margin"] == 2.0
    assert rpc_options["timeout"] == 60.0
    assert "conversationId" not in request
    assert "providerId" not in request


def test_gemini_notebook_add_url_source_validates_before_bridge() -> None:
    bridge = _FakeBridge()
    capability = GeminiNotebookWebCapability(bridge=bridge)

    with pytest.raises(ValueError, match="exactly one Gemini Notebook"):
        capability.add_url_source(
            notebook="https://notebook.google.com/",
            source_url="https://example.org/",
        )
    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        capability.add_url_source(
            notebook=NOTEBOOK,
            source_url="file:///tmp/source.txt",
        )

    assert bridge.requests == []


def test_gemini_notebook_bridge_response_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: socket closed",
                request_stage="browser_native_bridge",
            )

    capability = GeminiNotebookWebCapability(bridge=_LostBridge())

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as caught:
        capability.add_url_source(
            notebook=NOTEBOOK,
            source_url="https://example.org/",
        )

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_gemini_notebook_predelegation_failure_remains_ordinary() -> None:
    class _UnavailableBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_UNAVAILABLE: no running bridge",
                request_stage="browser_native_bridge",
            )

    capability = GeminiNotebookWebCapability(bridge=_UnavailableBridge())

    with pytest.raises(RequestError) as caught:
        capability.add_url_source(
            notebook=NOTEBOOK,
            source_url="https://example.org/",
        )

    assert not isinstance(caught.value, GeminiNotebookOutcomeAmbiguousError)


def test_gemini_notebook_postcommit_error_requires_reconciliation() -> None:
    class _AmbiguousBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            return {
                "protocol": 1,
                "type": "gemini_notebook_add_url_source_result",
                "request_id": payload["request_id"],
                "ok": False,
                "error": (
                    "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
                    "DURABLE_SOURCE_ROW_TIMEOUT:rows=1"
                ),
            }

    capability = GeminiNotebookWebCapability(bridge=_AmbiguousBridge())

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as caught:
        capability.add_url_source(
            notebook=NOTEBOOK,
            source_url="https://example.org/",
        )

    assert caught.value.reconciliation_required is True
    assert caught.value.automatic_retry_allowed is False


def test_gemini_notebook_mutation_worker_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is unavailable")

    worker = EXT / "service_worker_gemini_notebook_capability.js"
    subprocess.run(
        [node, "--check", str(worker)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_gemini_notebook_worker_freezes_commit_and_reconciliation() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    assert "gemini_notebook_add_url_source" in worker
    assert "PAGE_DOM_DURABLE_SOURCE_ADMISSION" in worker
    assert "_cwaGeminiNotebookFindExactOpenTab" in worker
    assert "_cwaGeminiNotebookCanonicalNotebookUrl" in worker
    assert 'document.querySelector("section.source-panel")' in worker
    assert 'querySelectorAll(".single-source-container")' in worker
    assert "source-item-more-button-" in worker
    assert "preRefs" in worker
    assert "commitMayHaveExecuted = true" in worker
    assert "commitMayHaveExecuted = false" in worker
    assert "_cwaGeminiNotebookAmbiguousError(error)" in worker
    assert "MULTIPLE_NEW_SOURCE_ROWS" in worker
    assert "POSTCOMMIT_ROW_IDENTITY_UNRESOLVED" in worker
    assert "DURABLE_SOURCE_ROW_TIMEOUT:rows=" in worker
    assert "InputEvent(" in worker
    assert ".click()" in worker
    assert "automaticRetry: false" in worker
    assert "canonicalCompletionProven: false" in worker

    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "Network.enable" not in worker
    assert "Network.request" not in worker
    assert "batchexecute" not in worker


def test_gemini_notebook_mutation_is_explicit_runtime_layer() -> None:
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    router = (EXT / "service_worker_native_message_router.js").read_text(
        encoding="utf-8"
    )

    characterization = 'importScripts("service_worker_gemini_notebook_capability.js");'
    mutation = 'importScripts("service_worker_gemini_notebook_capability.js");'
    translate = 'importScripts("service_worker_google_translate_capability.js");'

    assert characterization in runtime
    assert mutation in runtime
    assert translate in runtime
    assert runtime.index(characterization) < runtime.index(mutation)
    assert runtime.index(mutation) < runtime.index(translate)
    assert "_cwaOnNativeMessageWithGeminiNotebookUrlSource(" in router


def test_gemini_notebook_native_host_admits_mutation_on_shared_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"gemini_notebook_add_url_source",' in host
    assert '"gemini_notebook_add_url_source": 60_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host


def test_gemini_notebook_temporary_acceptance_surfaces_are_absent_after_closure() -> (
    None
):
    package = ROOT / "src" / "chatgpt_web_adapter"
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    host = (package / "browser_native_host.py").read_text(encoding="utf-8")

    assert "characterize_gemini_notebook" not in worker
    assert "characterize_gemini_notebook" not in host
    assert not (package / "gemini_notebook_web_characterization.py").exists()
    assert not (package / "gemini_notebook_web_live_gate.py").exists()
    assert not (EXT / "service_worker_gemini_notebook_url_source.js").exists()
