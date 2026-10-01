from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_video_artifact_menu_probe import (
    GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_PROBE_OPERATION,
    probe_gemini_notebook_video_artifact_menu,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
VIDEO_REF = "b2c41cbb-470f-46fb-8b39-578303b50c25"


class _FakeBridge:
    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "notebookUrl": payload["notebookUrl"],
            "tabId": 7,
            "elapsedMs": 18,
            "observedArtifactRef": payload["expectedArtifactRef"],
            "artifactTitle": "Video title",
            "artifactDetails": "1:21",
            "artifactIcons": ["videocam", "play_arrow", "more_vert"],
            "menuTriggerAriaControls": "",
            "menuTriggerAriaExpanded": "false",
            "menu": {
                "items": [
                    {
                        "tag": "button",
                        "role": "menuitem",
                        "disabled": False,
                        "className": "mat-mdc-menu-item",
                        "icons": ["save_alt"],
                    }
                ]
            },
            "downloadCandidateCount": 1,
            "downloadActionStructurallyProven": True,
            "menuClickPerformed": True,
            "productWritePerformed": False,
            "navigationPerformed": False,
            "downloadPerformed": False,
            "rawDomExported": False,
        }


def test_video_menu_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_VIDEO_ARTIFACT_MENU_PROBE_OPERATION == (
        "gemini_notebook_video_artifact_menu_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_video_artifact_menu")


def test_video_menu_probe_contract_is_non_download_characterization() -> None:
    result = probe_gemini_notebook_video_artifact_menu(
        notebook=NOTEBOOK,
        expected_artifact_ref=VIDEO_REF,
        bridge=_FakeBridge(),
    )

    assert result["observed_artifact_ref"] == VIDEO_REF
    assert result["artifact_icons"] == ["videocam", "play_arrow", "more_vert"]
    assert result["download_candidate_count"] == 1
    assert result["download_action_structurally_proven"] is True
    assert result["menu_click_performed"] is True
    assert result["product_write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["download_performed"] is False


def test_video_menu_probe_reuses_exact_ref_menu_primitives() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeVideoArtifactMenu(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickVisibleArtifactDownloadExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookWaitForStableExactArtifact(" in probe
    assert "_cwaGeminiNotebookClickExactArtifactMoreMenuExpression(" in probe
    assert "_cwaGeminiNotebookVisibleArtifactMenusExpression()" in probe
    assert 'exact?.row?.statusCandidate !== "NON_PENDING_CANDIDATE"' in probe
    assert 'item.icons.includes("save_alt")' in probe
    assert "downloadCandidates.length === 1" in probe
    assert "_cwaGeminiNotebookClickVisibleArtifactDownloadExpression()" not in probe
    assert "downloadPerformed: false" in probe
    assert "productWritePerformed: false" in probe


def test_video_menu_probe_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_video_artifact_menu_probe",' in host
    assert '"gemini_notebook_video_artifact_menu_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
