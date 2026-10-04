from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
INSTANT = EXT / "service_worker_instant_effort_selection.js"
PROFILE = EXT / "service_worker_model_profile_selection_pr8_10.js"
SUBMIT = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"
INSTANT_REPAIR = EXT / "service_worker_instant_selection_repair_pr8_8.js"


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

    assert (
        'PR172_BACKGROUND_PRODUCTION_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R11"'
        in profile
    )
    assert "backgroundProductionRuntimeRevision" in profile


def test_pr17_2_fast_profile_has_single_selection_owner() -> None:
    repair = _source(INSTANT_REPAIR)

    assert "_pr88SelectionAdoptModelProfileSelection" in repair
    assert 'owner?.requestedModelMode !== "INSTANT"' in repair
    assert "owner?.selectionComplete !== true" in repair
    assert "owner?.selectedModeAfterProven !== true" in repair
    assert 'owner?.selectedModeAfter !== "INSTANT"' in repair
    assert 'typeof _pr810ModelProfileContext !== "undefined"' in repair
    assert (
        "_pr88SelectionAdoptModelProfileSelection(context, modelProfileContext)"
        in repair
    )
    assert repair.index(
        "_pr88SelectionAdoptModelProfileSelection(context, modelProfileContext)"
    ) < repair.index("await _pr88SelectionEnsureInstant(debuggee, context);")


def test_pr17_2_shipping_high_selection_uses_proven_stepwise_settle() -> None:
    profile = _source(PROFILE)

    home = profile.index("await _pr88InstantEffortDispatchHome(debuggee);")
    baseline = profile.index(
        'settled = await _pr810WaitForTarget(debuggee, "INSTANT", 0, 3000);'
    )
    loop = profile.index("for (let index = 1; index <= targetIndex; index += 1)")
    arrow = profile.index(
        'await _pr810DispatchKey(debuggee, "ArrowRight", "ArrowRight", 39);',
        loop,
    )
    step_wait = profile.index(
        "settled = await _pr810WaitForTarget(debuggee, stepMode, index, 3000);",
        arrow,
    )

    assert home < baseline < loop < arrow < step_wait
    assert "PR8_10_MODEL_PROFILE_HOME_BASELINE_NOT_PROVEN" in profile
    assert "PR8_10_MODEL_PROFILE_INTERMEDIATE_STEP_NOT_PROVEN" in profile
    assert "homeBaselineProven: context.homeBaselineProven === true" in profile
    assert "stepwiseSelectionProven:" in profile


def test_pr17_2_post_key_proof_is_locale_independent_exact_slider() -> None:
    profile = _source(PROFILE)
    instant = _source(INSTANT)

    wait_start = profile.index("async function _pr810WaitForTarget")
    wait_end = profile.index("function _pr810InstallWriteBoundary", wait_start)
    wait_block = profile[wait_start:wait_end]

    assert '_pr88InstantEffortExactSliderSnapshot(debuggee, "snapshot")' in wait_block
    assert "slider?.now === targetIndex" in wait_block
    assert "slider?.currentMode === targetMode" not in wait_block
    assert "selectedModeLagObserved" in wait_block

    assert "has('medium')||has('средний')" in instant
    assert "has('high')||has('высокий')" in instant
    assert "/(^|\\b)(medium|средний)" not in instant
    assert "/(^|\\b)(high|высокий)" not in instant


def test_pr17_2_fresh_background_keyboard_paths_use_focus_emulation() -> None:
    profile = _source(PROFILE)
    submit = _source(SUBMIT)

    assert "Emulation.setFocusEmulationEnabled" in profile
    assert "_pr810EnableBackgroundFocusEmulation" in profile
    assert "_pr810DisableBackgroundFocusEmulation" in profile
    assert "PR17_2_BACKGROUND_FOCUS_EMULATION_NOT_PROVEN" in profile
    assert "PR17_2_BACKGROUND_FOCUS_EMULATION_ACTIVATED_TAB" in profile
    assert "backgroundFocusEmulationAttempted" in profile
    assert "backgroundFocusEmulationProven" in profile
    assert "backgroundFocusEmulationRestored" in profile
    assert "Page.bringToFront" not in profile
    assert "chrome.tabs.update" not in profile

    assert "Emulation.setFocusEmulationEnabled" in submit
    assert "_pr113EnableBackgroundKeyboardFocus" in submit
    assert "_pr113DisableBackgroundKeyboardFocus" in submit
    assert "PR11_3_BACKGROUND_FOCUS_EMULATION_NOT_PROVEN" in submit
    assert "PR11_3_BACKGROUND_FOCUS_EMULATION_ACTIVATED_TAB" in submit
    assert "Page.bringToFront" not in submit
    assert "chrome.tabs.update" not in submit


def test_pr17_2_fresh_background_slider_uses_cdp_dom_focus() -> None:
    profile = _source(PROFILE)

    assert "async function _pr810FocusExactSlider" in profile
    assert '"DOM.focus", {objectId}' in profile
    assert '"Runtime.releaseObjectGroup"' in profile
    assert '"pr17_2_exact_slider_focus"' in profile
    assert 'focusMechanism: "DOM.focus"' in profile
    assert "context.sliderFocusMechanism = focused?.focusMechanism || null" in profile
    assert "const focused = await _pr810FocusExactSlider(debuggee);" in profile
    assert (
        'const focused = await _pr88InstantEffortResolvedSliderSnapshot(debuggee, "focus");'
        not in profile
    )


def test_pr17_2_fresh_background_keyboard_probe_is_zero_write_and_scoped() -> None:
    profile = _source(PROFILE)

    assert "async function _pr172FreshBackgroundKeyboardProbe" in profile
    assert "characterizeFreshBackgroundReasoningKeyboard" in profile
    assert "ensureRuntimeTab(null)" in profile
    assert "_pr810FocusReasoningSlider(debuggee)" in profile
    assert '_pr810WaitForTarget(debuggee, "INSTANT", 0, 3000)' in profile
    assert "conversationWriteCount !== 0" in profile
    assert "PR17_2_FRESH_KEYBOARD_PROBE_TAB_ACTIVATED" in profile
    assert "await chrome.tabs.remove(tabId)" in profile
