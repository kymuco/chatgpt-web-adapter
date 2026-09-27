from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
from chatgpt_web_adapter.gemini_notebook_audio_artifact_action_probe import (
    GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION,
    probe_gemini_notebook_audio_artifact_action,
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
            "row": {
                "observedArtifactRef": ARTIFACT_REF,
                "labelsId": f"artifact-labels-{ARTIFACT_REF}",
                "icons": ["audio_spark", "play_arrow", "more_vert"],
                "controlCount": 2,
            },
            "controls": [],
            "moreVertCandidates": [],
            "rawDomExported": False,
            "writePerformed": False,
            "navigationPerformed": False,
            "downloadPerformed": False,
        }


def test_artifact_action_probe_is_temporary_module_only_surface() -> None:
    assert GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION == (
        "gemini_notebook_audio_artifact_action_probe"
    )
    assert not hasattr(adapter, "probe_gemini_notebook_audio_artifact_action")


def test_artifact_action_probe_contract_is_read_only() -> None:
    bridge = _FakeBridge()
    result = probe_gemini_notebook_audio_artifact_action(
        notebook=NOTEBOOK,
        expected_artifact_ref=ARTIFACT_REF,
        bridge=bridge,
    )

    assert result["observed_artifact_ref"] == ARTIFACT_REF
    assert result["row"]["labelsId"] == f"artifact-labels-{ARTIFACT_REF}"
    assert result["write_performed"] is False
    assert result["navigation_performed"] is False
    assert result["download_performed"] is False

    [request] = bridge.requests
    assert request["type"] == GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION
    assert request["expectedArtifactRef"] == ARTIFACT_REF


def test_artifact_action_probe_validates_ref_before_bridge() -> None:
    bridge = _FakeBridge()
    with pytest.raises(ValueError, match="expected_artifact_ref is invalid"):
        probe_gemini_notebook_audio_artifact_action(
            notebook=NOTEBOOK,
            expected_artifact_ref="bad ref",
            bridge=bridge,
        )
    assert bridge.requests == []


def test_worker_probe_is_exact_row_scoped_and_read_only() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    expression = worker.split(
        "function _cwaGeminiNotebookAudioArtifactActionProbeExpression(",
        1,
    )[1].split(
        "async function _cwaGeminiNotebookProbeAudioArtifactAction(message)",
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
    assert "observedArtifactRef === expectedArtifactRef" in expression
    assert "const expectedArtifactRef = ${encodedArtifactRef};" in expression
    assert "const expectedArtifactRef = \\${encodedArtifactRef};" not in expression
    assert "matches.length !== 1" in expression
    assert 'row.querySelectorAll("button,[role=\'button\']")' in expression
    assert 'control.icons.includes("more_vert")' in expression
    assert ".slice(0, 16)" in expression


def test_worker_probe_returns_safety_flags_without_download_authority() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )
    probe = worker.split(
        "async function _cwaGeminiNotebookProbeAudioArtifactAction(message)",
        1,
    )[1].split(
        "function _cwaGeminiNotebookAudioConfigReadinessExpression()",
        1,
    )[0]

    assert "rawDomExported: false" in probe
    assert "writePerformed: false" in probe
    assert "navigationPerformed: false" in probe
    assert "downloadPerformed: false" in probe
    assert "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH" in probe


def test_artifact_action_probe_uses_existing_authority_lane() -> None:
    host = (PACKAGE / "browser_native_host.py").read_text(encoding="utf-8")
    assert '"gemini_notebook_audio_artifact_action_probe",' in host
    assert '"gemini_notebook_audio_artifact_action_probe": 15_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host
