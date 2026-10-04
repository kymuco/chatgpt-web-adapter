from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
INSTANT = EXT / "service_worker_instant_effort_selection.js"
PROFILE = EXT / "service_worker_model_profile_selection_pr8_10.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_2_shipping_selection_owners_never_activate_tabs() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)

    for source in (instant, profile):
        assert "chrome.tabs.update" not in source
        assert "chrome.windows.update" not in source

    assert "_pr88InstantEffortBeginTransientForeground" not in instant
    assert "_pr88InstantEffortRestorePriorTab" not in instant
    assert "_pr88InstantEffortBeginTransientForeground" not in profile
    assert "_pr88InstantEffortRestorePriorTab" not in profile


def test_pr17_2_shipping_slider_contract_matches_live_background_proof() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)

    assert "_pr88InstantEffortExactSliderExpression" in instant
    assert "_pr88InstantEffortExactSliderSnapshot" in instant
    assert "unique_exact_slider_value" in instant
    assert "min===0&&max===2&&now>=0&&now<=2" in instant
    assert "now===0?'INSTANT':now===1?'MEDIUM':now===2?'HIGH':null" in instant
    assert "_pr88InstantEffortResolvedSliderSnapshot" in instant

    assert "Object.freeze({INSTANT: 0, MEDIUM: 1, HIGH: 2})" in profile
    assert "_pr88InstantEffortDispatchHome(debuggee)" in profile
    assert '_pr810DispatchKey(debuggee, "ArrowRight", "ArrowRight", 39)' in profile


def test_pr17_2_shipping_trigger_supports_semantic_composer_without_mouse_dispatch() -> (
    None
):
    instant = _source(INSTANT)

    assert '[contenteditable="true"][role="textbox"][aria-multiline="true"]' in instant
    assert "candidate.closest('main')" in instant
    assert "candidate.closest('form')" in instant
    assert "target.click();" in instant
    assert "Input.dispatchMouseEvent" not in instant


def test_pr17_2_shipping_paths_preserve_prewrite_proof() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)

    assert "unexpectedConversationWriteBeforeSelectionComplete" in instant
    assert "PR8_8_INSTANT_EFFORT_CONVERSATION_WRITE_BEFORE_SELECTION" in instant
    assert "_pr810InstallWriteBoundary(debuggee, context)" in profile
    assert "PR8_10_MODEL_PROFILE_CONVERSATION_WRITE_BEFORE_SELECTION" in profile

    assert "instantEffortBackgroundSelectionAttempted = true" in instant
    assert "instantEffortBackgroundSelectionProven" in instant
    assert "backgroundSelectionAttempted = true" in profile
    assert "backgroundSelectionProven = true" in profile


def test_pr17_2_shipping_support_surfaces_declare_no_foreground_requirement() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)

    for source in (instant, profile):
        assert "backgroundSelectionSupported: true" in source
        assert "transientForegroundRequired: false" in source
