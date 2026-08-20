from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SOURCE = EXTENSION / "service_worker_model_profile_selection_pr8_10.js"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def _ensure_target_mode_block(source: str) -> str:
    start = source.index("async function _pr810EnsureTargetMode")
    end = source.index("\nlocateAndFocusComposer =", start)
    return source[start:end]


def test_fresh_new_chat_initial_mode_uses_bounded_existing_pr88_acquisition() -> None:
    source = _source()
    block = _ensure_target_mode_block(source)

    assert "const PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS = 8000;" in source
    assert "await _pr88InstantWaitForSelectedMode(" in block
    assert "PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS" in block

    # The PR8.10 initial-state decision must no longer be a one-shot snapshot.
    acquisition_prefix = block[: block.index("if (before.selectedMode === targetMode)")]
    assert "await _pr88InstantSelectedModeSnapshot(debuggee)" not in acquisition_prefix


def test_initial_mode_acquisition_remains_strict_and_prewrite() -> None:
    source = _source()
    block = _ensure_target_mode_block(source)

    wait_index = block.index("await _pr88InstantWaitForSelectedMode(")
    not_proven_index = block.index("throw new Error(_pr810InitialModeFailure(before));")
    unsupported_index = block.index("PR8_10_MODEL_PROFILE_INITIAL_MODE_UNSUPPORTED")
    write_boundary_index = block.index("_pr810InstallWriteBoundary(debuggee, context);")

    assert wait_index < not_proven_index < write_boundary_index
    assert wait_index < unsupported_index < write_boundary_index
    assert "if (_pr810Mode(before.selectedMode) === null)" in block


def test_initial_mode_failure_preserves_bounded_diagnostics() -> None:
    source = _source()

    assert "PR8_10_MODEL_PROFILE_INITIAL_MODE_NOT_PROVEN:${proofKind}" in source
    assert "composer_ready=${composerReady}" in source
    assert "candidate_count=${candidateCount}" in source
    assert "context.initialModeComposerReady = before?.composerReady === true;" in source
    assert "context.selectedModeBeforeProofKind = before?.proofKind || \"unknown\";" in source
    assert "context.selectedModeBeforeCandidateCount" in source
    assert "context.selectedModeBeforeNearestDistancePx" in source


def test_success_record_exposes_initial_mode_acquisition_evidence() -> None:
    source = _source()

    assert "initialModeAcquisitionTimeoutMs: PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS" in source
    assert "initialModeAcquisitionElapsedMs:" in source
    assert "initialModeComposerReady:" in source
    assert "selectedModeBeforeProofKind:" in source
    assert "selectedModeBeforeCandidateCount:" in source
    assert "selectedModeBeforeNearestDistancePx:" in source
    assert "boundedInitialModeAcquisition: true" in source


def test_pr8102_does_not_widen_the_proven_three_state_target_mapping() -> None:
    source = _source()

    assert "Object.freeze({INSTANT: 0, MEDIUM: 1, HIGH: 2})" in source
    assert 'supportedProductModes: ["INSTANT", "MEDIUM", "HIGH"]' in source
    assert "EXTRA_HIGH: 3" not in source
    assert "PRO_STANDARD:" not in source
