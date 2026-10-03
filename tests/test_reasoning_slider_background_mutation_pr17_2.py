from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
MUTATION = EXT / "service_worker_reasoning_slider_mutation.js"
OBSERVABILITY = EXT / "service_worker_observability.js"
TOOL = ROOT / "tools" / "pr17_2_background_reasoning_slider_home_to_instant.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_2_background_mutation_is_separate_from_read_only_probe() -> None:
    observability = _source(OBSERVABILITY)

    characterization_import = (
        'importScripts("service_worker_reasoning_option_characterization.js");'
    )
    mutation_import = 'importScripts("service_worker_reasoning_slider_mutation.js");'
    assert characterization_import in observability
    assert mutation_import in observability
    assert observability.index(characterization_import) < observability.index(
        mutation_import
    )


def test_pr17_2_background_mutation_has_bounded_authority() -> None:
    source = _source(MUTATION)

    assert "characterizeBackgroundReasoningSliderHomeToInstant" in source
    assert "PR17_2_BACKGROUND_MUTATION_REQUIRES_INACTIVE_RUNTIME_TAB" in source
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
    assert "_pr172BackgroundDomTriggerClick(" in source


def test_pr17_2_background_mutation_is_exact_high_to_instant() -> None:
    source = _source(MUTATION)

    assert "slider?.now !== 2" in source
    assert '"focus",' in source
    assert '"HIGH"' in source
    assert '"selected_mode_control"' in source
    assert '"exact_slider_value"' in source
    assert '"picker_mode_control"' in source
    assert "pickerHighProven" in source
    assert "sliderHighAlreadyProven" in source
    assert "INITIAL_MODE_MISMATCH" in source
    assert 'key: "Home"' in source
    assert 'code: "Home"' in source
    assert "slider?.now === 0" in source
    assert 'slider?.currentMode === "INSTANT"' in source
    assert 'targetMode: "INSTANT"' in source
    assert "reasoningValueMutationAttempted: true" in source
    assert "reasoningValueMutationProven:" in source


def test_pr17_2_background_mutation_proves_no_conversation_write() -> None:
    source = _source(MUTATION)

    assert "_pr172MutationIsConversationWrite" in source
    assert '"Network.enable"' in source
    assert '"Network.requestWillBeSent"' in source
    assert "conversationWriteCount += 1" in source
    assert "conversationWriteCount !== 0" in source
    assert "conversationWriteAttempted: false" in source
    assert "conversationWriteObserved: false" in source


def test_pr17_2_background_mutation_proves_no_tab_activation() -> None:
    source = _source(MUTATION)

    assert "chrome.tabs.onActivated.addListener(onActivated)" in source
    assert "tabActivatedDuringGate = true" in source
    assert "tabAfter?.active === true" in source
    assert "PR17_2_BACKGROUND_MUTATION_TAB_ACTIVATION_OBSERVED" in source
    assert "tabActivated: false" in source


def test_pr17_2_background_mutation_restores_menu_by_retained_opener() -> None:
    source = _source(MUTATION)

    assert "openedByProbe" in source
    assert "uiTriggerRestoreAttempted" in source
    assert "uiTriggerRestoreProven" in source
    assert "_pr172BackgroundDomTriggerClick(" in source
    assert "retainedReferenceUsed" in source


def test_pr17_2_background_mutation_tool_contract() -> None:
    source = _source(TOOL)

    assert '"conversation_write_budget": 0' in source
    assert '"reasoning_value_mutation_budget": 1' in source
    assert '"target_mode": "INSTANT"' in source
    assert '"characterizeBackgroundReasoningSliderHomeToInstant": True' in source
    assert 'response.get("sliderNowBefore") != 2' in source
    assert 'response.get("sliderNowAfter") != 0' in source
    assert 'response.get("selectedModeAfter") != "INSTANT"' in source
    assert 'response.get("conversationWriteCount") != 0' in source
    assert 'response.get("debuggerAttachedAfter") is not False' in source
