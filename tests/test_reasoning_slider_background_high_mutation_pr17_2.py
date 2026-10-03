from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
HIGH = EXT / "service_worker_reasoning_slider_high_mutation.js"
OBSERVABILITY = EXT / "service_worker_observability.js"
TOOL = ROOT / "tools" / "pr17_2_background_reasoning_slider_medium_to_high.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_2_high_mutation_loads_after_step_mutation() -> None:
    source = _source(OBSERVABILITY)

    step_import = 'importScripts("service_worker_reasoning_slider_step_mutation.js");'
    high_import = 'importScripts("service_worker_reasoning_slider_high_mutation.js");'
    assert step_import in source
    assert high_import in source
    assert source.index(step_import) < source.index(high_import)


def test_pr17_2_high_mutation_is_exact_medium_to_high() -> None:
    source = _source(HIGH)

    assert "characterizeBackgroundReasoningSliderMediumToHigh" in source
    assert 'beforeMode !== "MEDIUM"' in source
    assert "pickerMediumProven" in source
    assert "sliderMediumAlreadyProven" in source
    assert '"selected_mode_control"' in source
    assert '"exact_slider_value"' in source
    assert '"picker_mode_control"' in source
    assert "slider?.now !== 1" in source
    assert 'slider?.currentMode !== "MEDIUM"' in source
    assert '"Home", "Home", 36' in source
    assert source.count('"ArrowRight", "ArrowRight", 39') == 2
    assert "arrowRightDispatchCount: 2" in source
    assert 'targetMode: "HIGH"' in source
    assert "targetSliderValue: 2" in source
    assert "settled.slider?.now === 2" in source


def test_pr17_2_high_mutation_proves_each_discrete_step() -> None:
    source = _source(HIGH)

    home = source.index('_pr172StepDispatchKey(debuggee, "Home", "Home", 36)')
    first_arrow = source.index(
        '_pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39)'
    )
    medium_proof = source.index(
        "PR17_2_BACKGROUND_HIGH_INTERMEDIATE_MEDIUM_NOT_PROVEN"
    )
    second_arrow = source.index(
        '_pr172StepDispatchKey(debuggee, "ArrowRight", "ArrowRight", 39)',
        first_arrow + 1,
    )
    high_proof = source.index("PR17_2_BACKGROUND_HIGH_DID_NOT_SETTLE_TO_HIGH")

    assert home < first_arrow < medium_proof < second_arrow < high_proof
    assert "afterHome?.now !== 0" in source
    assert 'afterHome?.currentMode !== "INSTANT"' in source
    assert "mediumSettled?.slider?.now !== 1" in source
    assert "intermediateMediumProven: mediumSettled?.slider?.now === 1" in source


def test_pr17_2_high_mutation_has_bounded_keyboard_authority() -> None:
    source = _source(HIGH)

    assert "Input.dispatchKeyEvent" not in source
    assert "_pr172StepDispatchKey(" in source

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


def test_pr17_2_high_mutation_proves_no_write_or_activation() -> None:
    source = _source(HIGH)

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


def test_pr17_2_high_mutation_restores_menu_by_retained_opener() -> None:
    source = _source(HIGH)

    assert "openedByProbe" in source
    assert "uiTriggerRestoreAttempted" in source
    assert "uiTriggerRestoreProven" in source
    assert "_pr172BackgroundDomTriggerClick(" in source
    assert "retainedReferenceUsed" in source


def test_pr17_2_high_mutation_tool_contract() -> None:
    source = _source(TOOL)

    assert '"conversation_write_budget": 0' in source
    assert '"reasoning_value_mutation_budget": 1' in source
    assert '"target_mode": "HIGH"' in source
    assert '"characterizeBackgroundReasoningSliderMediumToHigh": True' in source
    assert 'response.get("selectedModeBefore") != "MEDIUM"' in source
    assert 'response.get("sliderNowBefore") != 1' in source
    assert 'response.get("targetSliderValue") != 2' in source
    assert 'response.get("arrowRightDispatchCount") != 2' in source
    assert 'response.get("sliderNowAfter") != 2' in source
    assert 'response.get("selectedModeAfter") != "HIGH"' in source
    assert 'response.get("conversationWriteCount") != 0' in source
    assert 'response.get("debuggerAttachedAfter") is not False' in source
