from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_web import (
    GEMINI_NOTEBOOK_AUDIO_ACCEPTED_EVIDENCE,
    GEMINI_NOTEBOOK_AUDIO_COMPLETION_FINALITY,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
    GEMINI_NOTEBOOK_AUDIO_PENDING_EVIDENCE,
    GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION,
    GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION,
    GeminiNotebookOutcomeAmbiguousError,
    GeminiNotebookWebCapability,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"
EXT = PACKAGE / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
ARTIFACT_REF = "261a5005-1c03-44d7-9aa9-ecfb5bcef8f2"


class _FakeBridge:
    def __init__(self, status: str = "PENDING") -> None:
        self.requests = []
        self.status = status

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        if payload["type"] == GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION:
            return {
                "ok": True,
                "productId": "gemini-notebook-web",
                "capabilityId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
                "notebookUrl": payload["notebookUrl"],
                "generationCommitMayHaveExecuted": True,
                "generationAcceptedProven": True,
                "observedArtifactRef": ARTIFACT_REF,
                "artifactStatus": "PENDING",
                "artifactTitle": "Creating audio overview",
                "artifactDetails": "Come back in a few minutes.",
                "startEvidence": GEMINI_NOTEBOOK_AUDIO_ACCEPTED_EVIDENCE,
                "canonicalCompletionProven": False,
                "automaticRetry": False,
            }
        completed = self.status == "COMPLETED"
        return {
            "ok": True,
            "productId": "gemini-notebook-web",
            "capabilityId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
            "notebookUrl": payload["notebookUrl"],
            "observedArtifactRef": payload["observedArtifactRef"],
            "artifactStatus": self.status,
            "artifactTitle": "Audio overview",
            "artifactDetails": "2 sources",
            "completionProven": completed,
            "reloadVerified": completed,
            "finalityEvidence": (
                GEMINI_NOTEBOOK_AUDIO_COMPLETION_FINALITY
                if completed
                else GEMINI_NOTEBOOK_AUDIO_PENDING_EVIDENCE
            ),
            "canonicalCompletionProven": False,
            "automaticRetry": False,
            "writePerformed": False,
            "navigationPerformed": completed,
        }


def test_audio_overview_is_module_only_experimental_capability() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID == "generate_audio_overview"
    assert GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION == (
        "gemini_notebook_observe_audio_overview"
    )
    assert not hasattr(adapter, "GeminiNotebookWebCapability")


def test_generate_audio_overview_returns_background_acceptance() -> None:
    bridge = _FakeBridge()
    result = GeminiNotebookWebCapability(bridge=bridge).generate_audio_overview(
        notebook=NOTEBOOK
    )
    assert result.observed_artifact_ref == ARTIFACT_REF
    assert result.artifact_status == "PENDING"
    assert result.start_evidence == "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED"
    assert result.canonical_completion_proven is False
    assert result.automatic_retry is False


def test_generate_audio_overview_bridge_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        GeminiNotebookWebCapability(bridge=_LostBridge()).generate_audio_overview(
            notebook=NOTEBOOK
        )
    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_observe_audio_overview_pending_has_no_reload() -> None:
    result = GeminiNotebookWebCapability(
        bridge=_FakeBridge("PENDING")
    ).observe_audio_overview(
        notebook=NOTEBOOK,
        observed_artifact_ref=ARTIFACT_REF,
    )
    assert result.artifact_status == "PENDING"
    assert result.completion_proven is False
    assert result.reload_verified is False
    assert result.finality_evidence == "PAGE_DOM_BACKGROUND_ARTIFACT_PENDING"
    assert result.navigation_performed is False


def test_observe_audio_overview_completed_requires_reload_finality() -> None:
    result = GeminiNotebookWebCapability(
        bridge=_FakeBridge("COMPLETED")
    ).observe_audio_overview(
        notebook=NOTEBOOK,
        observed_artifact_ref=ARTIFACT_REF,
    )
    assert result.artifact_status == "COMPLETED"
    assert result.completion_proven is True
    assert result.reload_verified is True
    assert result.finality_evidence == (
        "PAGE_DOM_DURABLE_BACKGROUND_ARTIFACT_COMPLETION"
    )
    assert result.navigation_performed is True


def test_audio_overview_validates_ref_before_bridge() -> None:
    bridge = _FakeBridge()
    with pytest.raises(ValueError, match="observed_artifact_ref is invalid"):
        GeminiNotebookWebCapability(bridge=bridge).observe_audio_overview(
            notebook=NOTEBOOK,
            observed_artifact_ref="bad ref",
        )
    assert bridge.requests == []


def test_audio_overview_worker_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is unavailable")
    subprocess.run(
        ["node", "--check", str(EXT / "service_worker_gemini_notebook_capability.js")],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_generate_effect_boundary_is_final_action_only() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    generate = worker.split(
        "async function _cwaGeminiNotebookGenerateAudioOverview(message)", 1
    )[1].split("async function _cwaGeminiNotebookObserveAudioOverview(message)", 1)[0]
    assert "_cwaGeminiNotebookWaitForAudioConfig(debuggee, deadlineAt)" in generate
    boundary = generate.index("generationCommitMayHaveExecuted = true;")
    commit = generate.index("_cwaGeminiNotebookClickAudioGenerateNowExpression()")
    assert boundary < commit
    assert generate.count("generationCommitMayHaveExecuted = false") == 1
    assert "if (generationCommitMayHaveExecuted)" in generate
    assert "_cwaGeminiNotebookAmbiguousError(error)" in generate


def test_generate_identity_is_structural_and_nonlocalized() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    click = worker.split(
        "function _cwaGeminiNotebookClickAudioGenerateNowExpression()", 1
    )[1].split("async function _cwaGeminiNotebookWaitForAudioConfig", 1)[0]
    assert "audio_magic_eraser" in click
    assert ".mat-mdc-dialog-actions" in click
    assert 'button.classList.contains("mat-tonal-button")' in click
    assert click.count(".click()") == 1
    assert "Сгенерировать сейчас" not in click
    assert "Generate now" not in click


def test_observation_requires_same_ref_after_reload_for_completion() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    observe = worker.split(
        "async function _cwaGeminiNotebookObserveAudioOverview(message)", 1
    )[1].split("function _cwaGeminiNotebookClickAddSourceExpression()", 1)[0]
    assert "_cwaGeminiNotebookWaitForStableAudioArtifact(" in observe
    assert "_cwaGeminiNotebookReloadExactNotebookTab(" in observe
    assert "PENDING_CANDIDATE" in observe
    assert "NON_PENDING_CANDIDATE" in observe
    assert "reloadVerified: true" in observe
    assert "completionProven: true" in observe


def test_audio_uses_no_private_google_protocol() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "batchexecute" not in worker


def test_audio_temporary_probe_surfaces_are_removed() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert "audio_overview_probe" not in worker
    assert "audio_overview_probe" not in host
    for name in (
        "gemini_notebook_audio_overview_probe.py",
        "gemini_notebook_audio_overview_start_probe.py",
        "gemini_notebook_audio_overview_config_probe.py",
        "gemini_notebook_audio_overview_generate_probe.py",
        "gemini_notebook_audio_overview_artifact_probe.py",
    ):
        assert not (PACKAGE / name).exists()
