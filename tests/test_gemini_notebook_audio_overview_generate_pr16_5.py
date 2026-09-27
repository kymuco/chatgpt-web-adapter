from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_audio_overview_generate_probe import (
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_OPERATION,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
    probe_gemini_notebook_audio_overview_generate,
)
from chatgpt_web_adapter.gemini_notebook_web import (
    GeminiNotebookOutcomeAmbiguousError,
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
            "type": "gemini_notebook_audio_overview_generate_probe_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": "gemini-notebook-web",
            "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
            "notebookUrl": payload["notebookUrl"],
            "generationCommitMayHaveExecuted": True,
            "generationAcceptedProven": True,
            "postArtifactState": {
                "emptyMarker": False,
                "directChildren": [{"tag": "div"}],
            },
            "startEvidence": "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED",
            "canonicalCompletionProven": False,
            "automaticRetry": False,
        }


def test_audio_overview_generate_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_OPERATION == (
        "gemini_notebook_audio_overview_generate_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_overview_generate")


def test_audio_overview_generate_probe_contract() -> None:
    bridge = _FakeBridge()

    result = probe_gemini_notebook_audio_overview_generate(
        notebook=NOTEBOOK,
        bridge=bridge,
    )

    assert result["generation_commit_may_have_executed"] is True
    assert result["generation_accepted_proven"] is True
    assert result["start_evidence"] == "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED"
    assert result["canonical_completion_proven"] is False
    assert result["automatic_retry"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_OVERVIEW_GENERATE_PROBE_OPERATION
    assert request["productId"] == "gemini-notebook-web"
    assert request["probeId"] == "audio_overview"


def test_audio_overview_generate_response_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        probe_gemini_notebook_audio_overview_generate(
            notebook=NOTEBOOK,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_audio_overview_generate_worker_freezes_commit_before_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    generate_function = worker.split(
        "async function _cwaGeminiNotebookProbeAudioOverviewGenerate(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickAddSourceExpression()",
        1,
    )[0]

    assert "let generationCommitMayHaveExecuted = false;" in generate_function
    boundary = generate_function.index("generationCommitMayHaveExecuted = true;")
    click = generate_function.index(
        "_cwaGeminiNotebookClickAudioGenerateNowExpression()"
    )
    assert boundary < click
    assert generate_function.count("generationCommitMayHaveExecuted = false") == 1
    assert "if (generationCommitMayHaveExecuted)" in generate_function
    assert "_cwaGeminiNotebookAmbiguousError(error)" in generate_function
    assert "generationAcceptedProven: true" in generate_function
    assert 'startEvidence: "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED"' in generate_function
    assert "canonicalCompletionProven: false" in generate_function
    assert "automaticRetry: false" in generate_function


def test_audio_overview_generate_click_identity_is_structural_and_single() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    click_expression = worker.split(
        "function _cwaGeminiNotebookClickAudioGenerateNowExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioOverviewGenerate(message)",
        1,
    )[0]

    assert "audio_magic_eraser" in click_expression
    assert ".mat-mdc-dialog-actions" in click_expression
    assert 'actionContainer.querySelectorAll("button")' in click_expression
    assert 'button.classList.contains("mat-tonal-button")' in click_expression
    assert "actualButtons.length !== 2" in click_expression
    assert "tonalCandidates.length !== 1" in click_expression
    assert click_expression.count(".click()") == 1
    assert "Сгенерировать сейчас" not in click_expression
    assert "Generate now" not in click_expression
    assert "fetch(" not in click_expression
    assert "XMLHttpRequest" not in click_expression


def test_audio_overview_generate_acceptance_uses_artifact_library_not_dialog_close() -> (
    None
):
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    generate_function = worker.split(
        "async function _cwaGeminiNotebookProbeAudioOverviewGenerate(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickAddSourceExpression()",
        1,
    )[0]

    assert "_cwaGeminiNotebookAudioArtifactStateExpression()" in generate_function
    assert "artifact?.emptyMarker === false" in generate_function
    assert "artifact.directChildren.length >= 1" in generate_function
    assert "CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_STABLE_MS" in generate_function
    assert "dialogCount" not in generate_function


def test_audio_overview_generate_host_uses_existing_authority_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"gemini_notebook_audio_overview_generate_probe",' in host
    assert '"gemini_notebook_audio_overview_generate_probe": 30_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
