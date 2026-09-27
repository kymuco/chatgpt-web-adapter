from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_overview_artifact_probe import (
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_OPERATION,
    GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
    probe_gemini_notebook_audio_overview_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
NOTEBOOK = "https://notebook.google.com/notebook/564ab6b8-c253-4f1a-b104-6f8026d67c76"
ARTIFACT_REF = "261a5005-1c03-44d7-9aa9-ecfb5bcef8f2"


class _FakeBridge:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def _rpc(self, payload, *, timeout, on_event=None, **kwargs):
        self.requests.append(dict(payload))
        return {
            "protocol": 1,
            "type": "gemini_notebook_audio_overview_artifact_probe_result",
            "request_id": payload["request_id"],
            "ok": True,
            "productId": "gemini-notebook-web",
            "probeId": GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
            "notebookUrl": payload["notebookUrl"],
            "artifactObservationStable": True,
            "observedArtifactRef": ARTIFACT_REF,
            "artifact": {
                "observedArtifactRef": ARTIFACT_REF,
                "statusCandidate": "PENDING_CANDIDATE",
                "icons": ["progress_activity"],
                "actionDisabled": True,
            },
            "emptyMarker": False,
            "completionProven": False,
            "canonicalCompletionProven": False,
            "automaticRetry": False,
            "writePerformed": False,
            "navigationPerformed": False,
        }


def test_audio_overview_artifact_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_OPERATION == (
        "gemini_notebook_audio_overview_artifact_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_overview_artifact")


def test_audio_overview_artifact_probe_contract_is_read_only() -> None:
    bridge = _FakeBridge()

    result = probe_gemini_notebook_audio_overview_artifact(
        notebook=NOTEBOOK,
        expected_artifact_ref=ARTIFACT_REF,
        bridge=bridge,
    )

    assert result["observed_artifact_ref"] == ARTIFACT_REF
    assert result["artifact"]["statusCandidate"] == "PENDING_CANDIDATE"
    assert result["artifact_observation_stable"] is True
    assert result["completion_proven"] is False
    assert result["canonical_completion_proven"] is False
    assert result["automatic_retry"] is False
    assert result["write_performed"] is False
    assert result["navigation_performed"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_OVERVIEW_ARTIFACT_PROBE_OPERATION
    assert request["expectedArtifactRef"] == ARTIFACT_REF


def test_audio_overview_artifact_probe_validates_expected_ref_before_bridge() -> None:
    bridge = _FakeBridge()

    with pytest.raises(ValueError, match="expected_artifact_ref is invalid"):
        probe_gemini_notebook_audio_overview_artifact(
            notebook=NOTEBOOK,
            expected_artifact_ref="bad ref",
            bridge=bridge,
        )

    assert bridge.requests == []


def test_audio_overview_artifact_worker_observation_is_bounded_and_read_only() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    expression = worker.split(
        "function _cwaGeminiNotebookAudioArtifactItemsExpression()",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioOverviewArtifact(message)",
        1,
    )[0]
    assert ".click()" not in expression
    assert "dispatchEvent(" not in expression
    assert "InputEvent(" not in expression
    assert "fetch(" not in expression
    assert "XMLHttpRequest" not in expression
    assert "innerHTML" not in expression
    assert "outerHTML" not in expression
    assert 'library.querySelectorAll(".artifact-item-button")' in expression
    assert '"artifact-labels-"' in expression
    assert '"progress_activity"' in expression
    assert '"PENDING_CANDIDATE"' in expression
    assert '"NON_PENDING_CANDIDATE"' in expression
    assert "rows.length >= 20" in expression


def test_audio_overview_artifact_worker_requires_stable_exact_identity() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioOverviewArtifact(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookClickAddSourceExpression()",
        1,
    )[0]
    assert "rows.length !== 1" in probe
    assert "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_UNRESOLVED" in probe
    assert "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH" in probe
    assert "CWA_GEMINI_NOTEBOOK_AUDIO_OBSERVATION_STABLE_MS" in probe
    assert "completionProven: false" in probe
    assert "canonicalCompletionProven: false" in probe
    assert "automaticRetry: false" in probe
    assert "writePerformed: false" in probe
    assert "navigationPerformed: false" in probe


def test_audio_overview_artifact_host_uses_existing_authority_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"gemini_notebook_audio_overview_artifact_probe",' in host
    assert '"gemini_notebook_audio_overview_artifact_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
