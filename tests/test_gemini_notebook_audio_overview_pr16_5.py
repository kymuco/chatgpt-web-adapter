from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_overview_probe import (
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION,
    probe_gemini_notebook_audio_overview,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.rpc_options: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        self.rpc_options.append({"timeout": timeout, **kwargs})
        return {
            "protocol": 1,
            "type": "gemini_notebook_audio_overview_probe_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": "gemini-notebook-web",
            "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
            "notebookUrl": payload["notebookUrl"],
            "tabId": 17,
            "elapsedMs": 25,
            "sourcePanelFound": True,
            "sourcePickerFound": True,
            "sourceRowCount": 2,
            "targetControls": [
                {
                    "tag": "button",
                    "className": "example",
                    "ariaLabel": "Audio Overview",
                    "text": "Audio Overview",
                    "icons": ["headphones"],
                    "ancestors": [],
                }
            ],
            "controlSample": [],
            "regionCandidates": [],
            "rawDomExported": False,
            "writePerformed": False,
            "navigationPerformed": False,
        }


def test_audio_overview_probe_is_temporary_module_only_surface() -> None:
    assert (
        GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION
        == "gemini_notebook_audio_overview_probe"
    )
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID == "audio_overview"
    assert not hasattr(adapter, "probe_gemini_notebook_audio_overview")


def test_audio_overview_probe_contract_is_read_only() -> None:
    bridge = _FakeBridge()

    result = probe_gemini_notebook_audio_overview(
        notebook=NOTEBOOK + "?ignored=true",
        bridge=bridge,
    )

    assert result["notebook_url"] == NOTEBOOK
    assert result["source_row_count"] == 2
    assert result["write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["raw_dom_exported"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION
    assert request["productId"] == "gemini-notebook-web"
    assert request["probeId"] == "audio_overview"
    assert request["notebookUrl"] == NOTEBOOK
    assert "conversationId" not in request
    assert "providerId" not in request

    [rpc_options] = bridge.rpc_options
    assert rpc_options["timeout"] == 15.0
    assert rpc_options["delegated_timeout_ms_key"] == "timeoutMs"
    assert rpc_options["delegated_response_margin"] == 1.0


def test_audio_overview_probe_validates_before_bridge() -> None:
    bridge = _FakeBridge()

    with pytest.raises(ValueError, match="exactly one Gemini Notebook"):
        probe_gemini_notebook_audio_overview(
            notebook="https://notebook.google.com/",
            bridge=bridge,
        )

    assert bridge.requests == []


def test_audio_overview_worker_probe_is_read_only_and_bounded() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    assert "gemini_notebook_audio_overview_probe" in worker
    assert "_cwaGeminiNotebookAudioOverviewProbeExpression" in worker
    assert "_cwaGeminiNotebookProbeAudioOverview" in worker

    probe_expression = worker.split(
        "function _cwaGeminiNotebookAudioOverviewProbeExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioOverview",
        1,
    )[0]
    assert ".click()" not in probe_expression
    assert "dispatchEvent(" not in probe_expression
    assert "InputEvent(" not in probe_expression
    assert "fetch(" not in probe_expression
    assert "XMLHttpRequest" not in probe_expression
    assert "innerHTML" not in probe_expression
    assert "outerHTML" not in probe_expression
    assert "targetControls.length >= 30" in probe_expression
    assert "controls.slice(0, 60)" in probe_expression
    assert "sourcePanel.contains(control)" in probe_expression
    assert '"button,[role=\'button\']"' in probe_expression
    assert "[aria-label],[title]" not in probe_expression
    assert ".slice(0, 40)" in probe_expression
    assert "rawDomExported: false" in probe_expression
    assert "writePerformed: false" in probe_expression
    assert "navigationPerformed: false" in probe_expression


def test_audio_overview_probe_reuses_existing_notebook_runtime_layer() -> None:
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    notebook_import = 'importScripts("service_worker_gemini_notebook_capability.js");'
    assert runtime.count(notebook_import) == 1
    assert '"gemini_notebook_audio_overview_probe",' in host
    assert '"gemini_notebook_audio_overview_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
