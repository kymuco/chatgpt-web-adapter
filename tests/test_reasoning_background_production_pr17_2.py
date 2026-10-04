from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
INSTANT = EXT / "service_worker_instant_effort_selection.js"
PROFILE = EXT / "service_worker_model_profile_selection_pr8_10.js"
SUBMIT = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_2_shipping_selection_owners_never_activate_tabs() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)
    submit = _source(SUBMIT)

    for source in (instant, profile, submit):
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


def test_pr17_2_shipping_background_text_submit_never_activates_tab() -> None:
    submit = _source(SUBMIT)

    assert "_pr113RuntimeTabActive" in submit
    assert "if (tabActive !== true)" in submit
    assert "return _pr113SubmitTextWithEnterOnce(debuggee);" in submit
    assert "PR11_3_MOUSE_COMMIT_REQUIRES_ALREADY_ACTIVE_TAB" in submit
    assert "chrome.tabs.update" not in submit
    assert "chrome.windows.update" not in submit


def test_pr17_2_shipping_settle_accepts_exact_slider_proof() -> None:
    instant = _source(INSTANT)
    profile = _source(PROFILE)

    assert "context.selectedModeAfterSelectionProven !== true" in instant
    assert 'context.selectedModeAfterSelection !== "INSTANT"' in instant
    assert (
        'after?.selectedModeProven !== true || after?.selectedMode !== "INSTANT"'
        not in instant
    )

    assert "context.selectedModeAfterProven !== true" in profile
    assert "context.selectedModeAfter !== targetMode" in profile
    assert (
        "after?.selectedModeProven !== true || after?.selectedMode !== targetMode"
        not in profile
    )
    assert '"unique_exact_slider_value"' in profile
    assert "'unique_exact_slider_value'" in instant


def test_pr17_2_shipping_support_exposes_loaded_runtime_revision() -> None:
    profile = _source(PROFILE)

    assert 'PR172_BACKGROUND_PRODUCTION_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R4"' in profile
    assert "backgroundProductionRuntimeRevision" in profile
