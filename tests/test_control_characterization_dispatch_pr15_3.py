from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

FILES = {
    "orphan": EXT / "service_worker_orphan_lease_reconciliation_pr8_8.js",
    "reasoning": EXT / "service_worker_reasoning_effort_slider_governance_pr8_8.js",
    "instant": EXT / "service_worker_instant_effort_slider_support_pr8_8.js",
}


def _source(name: str) -> str:
    return FILES[name].read_text(encoding="utf-8")


def test_control_characterization_modules_do_not_own_ordinary_turn_dispatch() -> None:
    for name in FILES:
        source = _source(name)
        assert "executeNativeTurn = async function" not in source
        assert "PriorExecuteNativeTurn" not in source


def test_each_control_characterization_concept_has_explicit_owner() -> None:
    orphan = _source("orphan")
    reasoning = _source("reasoning")
    instant = _source("instant")

    assert '"orphan-lease-reconciliation"' in orphan
    assert "registerNativeTurnDiagnosticHandler(" in orphan
    assert "_pr88OrphanDiagnosticMatches" in orphan
    assert "_pr88HandleOrphanLeaseDiagnostic" in orphan

    assert '"reasoning-effort-characterization"' in reasoning
    assert "registerNativeTurnDiagnosticHandler(" in reasoning
    assert "_pr88ReasoningEffortDiagnosticMatches" in reasoning
    assert "_pr88HandleReasoningEffortDiagnostic" in reasoning

    assert '"instant-effort-support"' in instant
    assert "registerNativeTurnDiagnosticHandler(" in instant
    assert "_pr88InstantEffortSupportDiagnosticMatches" in instant
    assert "_pr88HandleInstantEffortSupportDiagnostic" in instant


def test_zero_product_write_and_retry_boundaries_remain_explicit() -> None:
    orphan = _source("orphan")
    reasoning = _source("reasoning")
    instant = _source("instant")

    assert "zeroProductWrites: true" in orphan
    assert "automaticRetry: false" in orphan

    assert "zeroProductWrites: true" in reasoning
    assert "selectionControlClickForbidden: true" in reasoning
    assert "automaticRetry: false" in reasoning

    assert "advancedPickerClickForbidden: true" in instant
    assert "modelControlClickForbidden: true" in instant
    assert "automaticRetry: false" in instant
