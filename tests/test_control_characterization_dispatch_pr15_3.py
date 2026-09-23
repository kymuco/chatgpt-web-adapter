from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

FILES = {
    "instant": EXT / "service_worker_instant_effort_selection.js",
}


def _source(name: str) -> str:
    return FILES[name].read_text(encoding="utf-8")


def test_control_characterization_modules_do_not_own_ordinary_turn_dispatch() -> None:
    for name in FILES:
        source = _source(name)
        assert "executeNativeTurn = async function" not in source
        assert "PriorExecuteNativeTurn" not in source


def test_each_control_characterization_concept_has_explicit_owner() -> None:
    instant = _source("instant")

    assert '"instant-effort-support"' in instant
    assert "registerNativeTurnDiagnosticHandler(" in instant
    assert "_pr88InstantEffortSupportDiagnosticMatches" in instant
    assert "_pr88HandleInstantEffortSupportDiagnostic" in instant


def test_zero_product_write_and_retry_boundaries_remain_explicit() -> None:
    instant = _source("instant")

    assert "advancedPickerClickForbidden: true" in instant
    assert "modelControlClickForbidden: true" in instant
    assert "automaticRetry: false" in instant
