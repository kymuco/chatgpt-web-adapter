from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_overview_config_probe import (
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CONFIG_PROBE_OPERATION,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
    probe_gemini_notebook_audio_overview_config,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        return {
            "protocol": 1,
            "type": "gemini_notebook_audio_overview_config_probe_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": "gemini-notebook-web",
            "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
            "notebookUrl": payload["notebookUrl"],
            "dialog": {
                "role": "dialog",
                "actionButtons": [
                    {"text": "Cancel", "disabled": False},
                    {"text": "Generate", "disabled": False},
                ],
            },
            "rawDomExported": False,
            "writePerformed": False,
            "navigationPerformed": False,
        }


def test_audio_overview_config_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CONFIG_PROBE_OPERATION == (
        "gemini_notebook_audio_overview_config_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_overview_config")


def test_audio_overview_config_probe_contract_is_read_only() -> None:
    bridge = _FakeBridge()

    result = probe_gemini_notebook_audio_overview_config(
        notebook=NOTEBOOK,
        bridge=bridge,
    )

    assert result["dialog"]["role"] == "dialog"
    assert result["write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["raw_dom_exported"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CONFIG_PROBE_OPERATION
    assert request["productId"] == "gemini-notebook-web"
    assert request["probeId"] == "audio_overview"


def test_audio_overview_config_worker_probe_is_read_only_and_dialog_scoped() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    expression = worker.split(
        "function _cwaGeminiNotebookAudioOverviewConfigProbeExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioOverviewConfig(message)",
        1,
    )[0]
    assert ".click()" not in expression
    assert "dispatchEvent(" not in expression
    assert "InputEvent(" not in expression
    assert "fetch(" not in expression
    assert "XMLHttpRequest" not in expression
    assert "innerHTML" not in expression
    assert "outerHTML" not in expression
    assert "dialogs.length !== 1" in expression
    assert ".mat-mdc-dialog-actions" in expression
    assert "actionButtons" in expression
    assert "control.value" not in expression
    assert "rawDomExported" not in expression


def test_audio_overview_config_host_uses_existing_authority_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"gemini_notebook_audio_overview_config_probe",' in host
    assert '"gemini_notebook_audio_overview_config_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
