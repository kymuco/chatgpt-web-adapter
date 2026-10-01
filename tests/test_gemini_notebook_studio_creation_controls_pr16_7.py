from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_studio_creation_controls_probe import (
    GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION,
    probe_gemini_notebook_studio_creation_controls,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "tabId": 7,
            "elapsedMs": 4,
            "studioFound": True,
            "creationControls": [
                {
                    "index": 0,
                    "ownerTag": "basic-create-artifact-button",
                    "ownerClassName": "",
                    "controlTag": "div",
                    "controlClassName": "create-artifact-button-container",
                    "role": "button",
                    "ariaLabel": "characterization only",
                    "title": "",
                    "text": "characterization only",
                    "disabled": False,
                    "icons": ["audio_spark"],
                }
            ],
            "writePerformed": False,
            "navigationPerformed": False,
            "rawDomExported": False,
        }


def test_studio_creation_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION == (
        "gemini_notebook_studio_creation_controls_probe"
    )
    assert not hasattr(
        adapter,
        "probe_gemini_notebook_studio_creation_controls",
    )


def test_studio_creation_probe_contract_is_read_only() -> None:
    bridge = _FakeBridge()
    result = probe_gemini_notebook_studio_creation_controls(
        notebook=NOTEBOOK,
        bridge=bridge,
    )

    assert result["studio_found"] is True
    assert result["creation_controls"][0]["icons"] == ["audio_spark"]
    assert result["write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["raw_dom_exported"] is False
    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION


def test_worker_studio_inventory_is_bounded_and_read_only() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    expression = worker.split(
        "function _cwaGeminiNotebookStudioCreationControlsExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeStudioCreationControls(message)",
        1,
    )[0]

    assert 'document.querySelector("section.studio-panel")' in expression
    assert 'studio.querySelectorAll("basic-create-artifact-button")' in expression
    assert ".slice(0, 24)" in expression
    assert "owner.querySelector(\"[role='button']\")" in expression
    assert 'owner.querySelector("button")' in expression
    assert 'element?.querySelectorAll?.("mat-icon")' in expression
    assert "icons: iconTexts(control)" in expression
    assert ".click()" not in expression
    assert "dispatchEvent(" not in expression
    assert "InputEvent(" not in expression
    assert "fetch(" not in expression
    assert "XMLHttpRequest" not in expression
    assert "innerHTML" not in expression
    assert "outerHTML" not in expression


def test_worker_studio_probe_exports_only_bounded_characterization() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeStudioCreationControls(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[0]

    assert "creationControls: controls" in probe
    assert "writePerformed: false" in probe
    assert "navigationPerformed: false" in probe
    assert "rawDomExported: false" in probe


def test_studio_probe_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_studio_creation_controls_probe",' in host
    assert '"gemini_notebook_studio_creation_controls_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
