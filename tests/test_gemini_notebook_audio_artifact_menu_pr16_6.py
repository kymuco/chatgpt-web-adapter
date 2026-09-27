from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_artifact_menu_probe import (
    GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION,
    probe_gemini_notebook_audio_artifact_menu,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
ARTIFACT_REF = "261a5005-1c03-44d7-9aa9-ecfb5bcef8f2"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "observedArtifactRef": payload["expectedArtifactRef"],
            "menuTriggerAriaControls": "mat-menu-panel-1",
            "menuTriggerAriaExpanded": "true",
            "menu": {
                "role": "menu",
                "items": [
                    {
                        "tag": "button",
                        "role": "menuitem",
                        "text": "Download",
                        "disabled": False,
                        "icons": ["download"],
                    }
                ],
            },
            "menuClickPerformed": True,
            "productWritePerformed": False,
            "navigationPerformed": False,
            "downloadPerformed": False,
            "rawDomExported": False,
        }


def test_artifact_menu_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION == (
        "gemini_notebook_audio_artifact_menu_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_artifact_menu")


def test_artifact_menu_probe_contract_stops_before_item_activation() -> None:
    bridge = _FakeBridge()
    result = probe_gemini_notebook_audio_artifact_menu(
        notebook=NOTEBOOK,
        expected_artifact_ref=ARTIFACT_REF,
        bridge=bridge,
    )

    assert result["observed_artifact_ref"] == ARTIFACT_REF
    assert result["menu_click_performed"] is True
    assert result["product_write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["download_performed"] is False
    assert result["raw_dom_exported"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION
    assert request["expectedArtifactRef"] == ARTIFACT_REF


def test_artifact_menu_probe_validates_ref_before_bridge() -> None:
    bridge = _FakeBridge()
    with pytest.raises(ValueError, match="expected_artifact_ref is invalid"):
        probe_gemini_notebook_audio_artifact_menu(
            notebook=NOTEBOOK,
            expected_artifact_ref="bad ref",
            bridge=bridge,
        )
    assert bridge.requests == []


def test_menu_click_is_exact_row_scoped_and_single() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    click = worker.split(
        "function _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactMenu(message)",
        1,
    )[0]

    assert "encodedArtifactRef" in click
    assert "observedArtifactRef === expectedArtifactRef" in click
    assert 'control.classList.contains("mat-mdc-menu-trigger")' in click
    assert 'control.closest("nb-icon-button.artifact-more-button")' in click
    assert 'icons.includes("more_vert")' in click
    assert "candidates.length !== 1" in click
    assert click.count(".click()") == 1
    assert "fetch(" not in click
    assert "XMLHttpRequest" not in click


def test_menu_observation_is_bounded_and_does_not_activate_items() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    expression = worker.split(
        "function _cwaGeminiNotebookVisibleArtifactMenusExpression()",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(",
        1,
    )[0]

    assert ".click()" not in expression
    assert "dispatchEvent(" not in expression
    assert "InputEvent(" not in expression
    assert "fetch(" not in expression
    assert "XMLHttpRequest" not in expression
    assert "innerHTML" not in expression
    assert "outerHTML" not in expression
    assert ".mat-mdc-menu-panel" in expression
    assert ".slice(0, 8)" in expression
    assert ".slice(0, 24)" in expression


def test_menu_probe_requires_clean_prestate_and_one_visible_menu() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactMenu(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "beforePanels.length !== 0" in probe
    assert "panels.length > 1" in probe
    assert "menuClickPerformed = true;" in probe
    assert "productWritePerformed: false" in probe
    assert "navigationPerformed: false" in probe
    assert "downloadPerformed: false" in probe


def test_artifact_menu_probe_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_audio_artifact_menu_probe",' in host
    assert '"gemini_notebook_audio_artifact_menu_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
