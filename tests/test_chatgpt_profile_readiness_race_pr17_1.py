from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SOURCE = EXT / "service_worker_model_profile_selection_pr8_10.js"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def _ensure_target_mode_block(source: str) -> str:
    start = source.index("async function _pr810EnsureTargetMode")
    end = source.index("\nasync function _pr810PrepareComposer(", start)
    return source[start:end]


def test_pr17_1_profile_waits_for_canonical_composer_before_mode_proof() -> None:
    block = _ensure_target_mode_block(_source())

    composer_wait = block.index("await waitForComposerReady(")
    mode_wait = block.index("await _pr88InstantWaitForSelectedMode(")
    write_boundary = block.index("_pr810InstallWriteBoundary(debuggee, context);")

    assert composer_wait < mode_wait < write_boundary
    assert "PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS" in block


def test_pr17_1_profile_acquisition_uses_one_total_prewrite_budget() -> None:
    source = _source()
    block = _ensure_target_mode_block(source)

    assert (
        "PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS = PR88_INSTANT_PROBE_TIMEOUT_MS"
        in source
    )
    assert "initialModeRemainingMs = Math.max(" in block
    assert "PR810_INITIAL_MODE_ACQUISITION_TIMEOUT_MS -" in block
    assert "initialModeRemainingMs" in block
    assert "initialModeComposerReadyElapsedMs" in block


def test_pr17_1_profile_readiness_repair_stays_before_write_boundary() -> None:
    block = _ensure_target_mode_block(_source())

    readiness = block.index("await waitForComposerReady(")
    not_proven = block.index("throw new Error(_pr810InitialModeFailure(before));")
    write_boundary = block.index("_pr810InstallWriteBoundary(debuggee, context);")

    assert readiness < not_proven < write_boundary
