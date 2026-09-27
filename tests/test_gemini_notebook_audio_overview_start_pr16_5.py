from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.gemini_notebook_audio_overview_start_probe import (
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_START_PROBE_OPERATION,
    probe_gemini_notebook_audio_overview_start,
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
            "type": "gemini_notebook_audio_overview_start_probe_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": "gemini-notebook-web",
            "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
            "notebookUrl": payload["notebookUrl"],
            "transitionKind": "CONFIGURATION_SURFACE_OBSERVED",
            "preArtifactState": {"emptyMarker": True},
            "postArtifactState": {"emptyMarker": True},
            "configState": {"dialogCount": 1, "dialogs": []},
            "potentialEffectMayHaveExecuted": True,
            "generationStartedProven": False,
            "canonicalCompletionProven": False,
            "automaticRetry": False,
        }


def test_audio_overview_start_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_START_PROBE_OPERATION == (
        "gemini_notebook_audio_overview_start_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_overview_start")


def test_audio_overview_start_probe_contract() -> None:
    bridge = _FakeBridge()

    result = probe_gemini_notebook_audio_overview_start(
        notebook=NOTEBOOK,
        bridge=bridge,
    )

    assert result["transition_kind"] == "CONFIGURATION_SURFACE_OBSERVED"
    assert result["potential_effect_may_have_executed"] is True
    assert result["generation_started_proven"] is False
    assert result["canonical_completion_proven"] is False
    assert result["automatic_retry"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_OVERVIEW_START_PROBE_OPERATION
    assert request["productId"] == "gemini-notebook-web"
    assert request["probeId"] == "audio_overview"


def test_audio_overview_start_response_loss_is_ambiguous() -> None:
    class _LostBridge(_FakeBridge):
        def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
            raise RequestError(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: closed",
                request_stage="browser_native_bridge",
            )

    with pytest.raises(GeminiNotebookOutcomeAmbiguousError) as captured:
        probe_gemini_notebook_audio_overview_start(
            notebook=NOTEBOOK,
            bridge=_LostBridge(),
        )

    assert captured.value.reconciliation_required is True
    assert captured.value.automatic_retry_allowed is False


def test_audio_overview_start_worker_freezes_effect_boundary_before_click() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    start_function = worker.split(
        "async function _cwaGeminiNotebookProbeAudioOverviewStart(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickAddSourceExpression()",
        1,
    )[0]

    assert "let audioGenerationMayHaveStarted = false;" in start_function
    effect_boundary = start_function.index("audioGenerationMayHaveStarted = true;")
    click_delegation = start_function.index(
        "_cwaGeminiNotebookClickAudioOverviewExpression()"
    )
    assert effect_boundary < click_delegation
    assert start_function.count("audioGenerationMayHaveStarted = false") == 1
    assert "if (audioGenerationMayHaveStarted)" in start_function
    assert "_cwaGeminiNotebookAmbiguousError(error)" in start_function
    assert "automaticRetry: false" in start_function
    assert "canonicalCompletionProven: false" in start_function
    assert "generationStartedProven: false" in start_function
    assert "artifact-library-container" in start_function
    assert "artifact-library-container-empty" in start_function
    assert 'container?.querySelector("artifact-library")' in start_function


def test_audio_overview_start_click_is_exact_and_single() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    click_expression = worker.split(
        "function _cwaGeminiNotebookClickAudioOverviewExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioOverviewStart(message)",
        1,
    )[0]

    assert 'document.querySelector("section.studio-panel")' in click_expression
    assert 'studio.querySelectorAll("basic-create-artifact-button")' in click_expression
    assert 'entry.icons.includes("audio_spark")' in click_expression
    assert "candidates.length !== 1" in click_expression
    assert click_expression.count(".click()") == 1
    assert "fetch(" not in click_expression
    assert "XMLHttpRequest" not in click_expression


def test_audio_overview_start_host_uses_existing_authority_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"gemini_notebook_audio_overview_start_probe",' in host
    assert '"gemini_notebook_audio_overview_start_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
