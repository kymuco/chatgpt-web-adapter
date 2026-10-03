from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
STEP = EXT / "service_worker_reasoning_slider_step_mutation.js"
OBSERVABILITY = EXT / "service_worker_observability.js"
TOOL = ROOT / "tools" / "pr17_2_background_reasoning_slider_instant_to_medium.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_2_step_mutation_loads_after_proven_home_mutation() -> None:
    source = _source(OBSERVABILITY)

    home_import = 'importScripts("service_worker_reasoning_slider_mutation.js");'
    step_import = 'importScripts("service_worker_reasoning_slider_step_mutation.js");'
    assert home_import in source
    assert step_import in source
    assert source.index(home_import) < source.index(step_import)


def test_pr17_2_step_mutation_is_exact_instant_to_medium() -> None:
    source = _source(STEP)

    assert "characterizeBackgroundReasoningSliderInstantToMedium" in source
    assert 'beforeMode !== "INSTANT"' in source
    assert "pickerInstantProven" in source
    assert "sliderInstantAlreadyProven" in source
    assert '"selected_mode_control"' in source
    assert '"exact_slider_value"' in source
    assert '"picker_mode_control"' in source
    assert 'slider?.now !== 0' in source
    assert 'slider?.currentMode !== "INSTANT"' in source
    assert 'key: "Home"' not in source
    assert '"Home", "Home", 36' in source
    assert '"ArrowRight", "ArrowRight", 39' in source
    assert "arrowRightDispatchCount: 1" in source
    assert 'targetMode: "MEDIUM"' in source
    assert "targetSliderValue: 1" in source
    assert "settled.slider?.now === 1" in source


def test_pr17_2_step_mutation_has_bounded_keyboard_authority() -> None:
    source = _source(STEP)

    assert "Input.dispatchKeyEvent" in source
    assert source.count('"Input.dispatchKeyEvent"') == 2

    for forbidden in (
        "Input.insertText",
        "Input.dispatchMouseEvent",
        ".requestSubmit(",
        ".submit(",
        "chrome.tabs.update",
        "chrome.tabs.create",
        "chrome.windows.update",
    ):
        assert forbidden not in source

    assert source.count(".click(") == 0


def test_pr17_2_step_mutation_proves_home_baseline_before_arrow() -> None:
    source = _source(STEP)

    home = source.index('_pr172StepDispatchKey(debuggee, "Home", "Home", 36)')
    baseline = source.index("PR17_2_BACKGROUND_STEP_HOME_BASELINE_NOT_PROVEN")
    arrow = source.index(
        '_pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39)'
    )

    assert home < baseline < arrow
    assert "afterHome?.now !== 0" in source
    assert 'afterHome?.currentMode !== "INSTANT"' in source
    assert "homeBaselineProven: afterHome?.now === 0" in source


def test_pr17_2_step_mutation_proves_no_write_or_activation() -> None:
    source = _source(STEP)

    assert "_pr172MutationIsConversationWrite" in source
    assert '"Network.requestWillBeSent"' in source
    assert "conversationWriteCount += 1" in source
    assert "conversationWriteCount !== 0" in source
    assert "conversationWriteAttempted: false" in source
    assert "conversationWriteObserved: false" in source
    assert "chrome.tabs.onActivated.addListener(onActivated)" in source
    assert "tabActivatedDuringGate = true" in source
    assert "tabAfter?.active === true" in source
    assert "tabActivated: false" in source


def test_pr17_2_step_mutation_restores_menu_by_retained_opener() -> None:
    source = _source(STEP)

    assert "openedByProbe" in source
    assert "uiTriggerRestoreAttempted" in source
    assert "uiTriggerRestoreProven" in source
    assert "_pr172BackgroundDomTriggerClick(" in source
    assert "retainedReferenceUsed" in source


def test_pr17_2_step_mutation_tool_contract() -> None:
    source = _source(TOOL)

    assert '"conversation_write_budget": 0' in source
    assert '"reasoning_value_mutation_budget": 1' in source
    assert '"target_mode": "MEDIUM"' in source
    assert '"characterizeBackgroundReasoningSliderInstantToMedium": True' in source
    assert 'response.get("selectedModeBefore") != "INSTANT"' in source
    assert 'response.get("sliderNowBefore") != 0' in source
    assert 'response.get("targetSliderValue") != 1' in source
    assert 'response.get("arrowRightDispatchCount") != 1' in source
    assert 'response.get("sliderNowAfter") != 1' in source
    assert 'response.get("selectedModeAfter") != "MEDIUM"' in source
    assert 'response.get("conversationWriteCount") != 0' in source
    assert 'response.get("debuggerAttachedAfter") is not False' in source
