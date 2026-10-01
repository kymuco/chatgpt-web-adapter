from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_video_config_probe import (
    GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION,
    probe_gemini_notebook_video_config,
)
from chatgpt_web_adapter.gemini_notebook_web import (
    GeminiNotebookOutcomeAmbiguousError,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"


class _FakeBridge:
    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "tabId": 7,
            "elapsedMs": 12,
            "createControlIcon": "videocam",
            "configurationSurfaceObserved": True,
            "dialog": {
                "icons": ["videocam"],
                "controls": [],
            },
            "beforeArtifactRefs": ["audio-ref"],
            "afterArtifactRefs": ["audio-ref"],
            "artifactLibraryUnchanged": True,
            "configurationOpenClickPerformed": True,
            "generationStartedProven": False,
            "durableProductWriteProven": False,
            "navigationPerformed": False,
            "automaticRetry": False,
            "rawDomExported": False,
        }


def test_video_config_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION == (
        "gemini_notebook_video_config_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_video_config")


def test_video_config_probe_contract_requires_unchanged_artifact_library() -> None:
    result = probe_gemini_notebook_video_config(
        notebook=NOTEBOOK,
        bridge=_FakeBridge(),
    )

    assert result["create_control_icon"] == "videocam"
    assert result["configuration_surface_observed"] is True
    assert result["before_artifact_refs"] == ["audio-ref"]
    assert result["after_artifact_refs"] == ["audio-ref"]
    assert result["artifact_library_unchanged"] is True
    assert result["generation_started_proven"] is False
    assert result["durable_product_write_proven"] is False
    assert result["automatic_retry"] is False


def test_video_config_response_loss_after_delegation_is_ambiguous() -> None:
    class _LostBridge:
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        probe_gemini_notebook_video_config(
            notebook=NOTEBOOK,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_video_create_identity_is_unique_videocam_and_not_localized() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    click = worker.split(
        "function _cwaGeminiNotebookClickVideoOverviewExpression()",
        1,
    )[1].split(
        "function _cwaGeminiNotebookVisibleDialogInventoryExpression()",
        1,
    )[0]

    assert 'document.querySelector("section.studio-panel")' in click
    assert 'studio.querySelectorAll("basic-create-artifact-button")' in click
    assert 'entry.icons.includes("videocam")' in click
    assert "candidates.length !== 1" in click
    assert click.count(".click()") == 1
    assert "Видеопересказ" not in click
    assert "Video Overview" not in click


def test_video_dialog_inventory_is_bounded_and_read_only() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    inventory = worker.split(
        "function _cwaGeminiNotebookVisibleDialogInventoryExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeVideoConfig(message)",
        1,
    )[0]

    assert ".slice(0, 4)" in inventory
    assert ".slice(0, 20)" in inventory
    assert "text: clip(" in inventory
    assert "icons: iconTexts(" in inventory
    assert ".click()" not in inventory
    assert "fetch(" not in inventory
    assert "XMLHttpRequest" not in inventory
    assert "innerHTML" not in inventory
    assert "outerHTML" not in inventory


def test_video_config_effect_boundary_precedes_exact_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoConfig(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[0]

    boundary = probe.index("configurationOpenMayHaveExecuted = true;")
    click = probe.index("_cwaGeminiNotebookClickVideoOverviewExpression()")
    assert boundary < click
    assert probe.count("configurationOpenMayHaveExecuted = false") == 1
    assert "if (configurationOpenMayHaveExecuted)" in probe
    assert "_cwaGeminiNotebookAmbiguousError(error)" in probe
    assert "artifactLibraryUnchanged: true" in probe
    assert "generationStartedProven: false" in probe
    assert "durableProductWriteProven: false" in probe
    assert "automaticRetry: false" in probe


def test_video_config_probe_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_config_probe",' in host
    assert '"gemini_notebook_video_config_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
