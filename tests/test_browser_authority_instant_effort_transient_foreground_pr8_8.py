from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
OWNER = ROOT / "service_worker_instant_effort_selection.js"


def test_transient_foreground_is_retired_from_instant_selection() -> None:
    source = OWNER.read_text(encoding="utf-8")

    for token in (
        "async function _pr88SelectionEnsureInstant(",
        "_pr88SelectionEnsureInstantCore(",
        "instantEffortTransientForegroundRequested = false",
        "instantEffortTransientForegroundActivated = false",
        "instantEffortTransientForegroundProven = false",
        "instantEffortForegroundRestoreAttempted = false",
        "instantEffortForegroundRestoreProven = true",
        "instantEffortBackgroundSelectionAttempted = true",
        "instantEffortBackgroundSelectionProven",
        "backgroundSelectionSupported: true",
        "transientForegroundRequired: false",
    ):
        assert token in source

    for forbidden in (
        "_pr88InstantEffortBeginTransientForeground",
        "_pr88InstantEffortWaitForeground",
        "_pr88InstantEffortRestorePriorTab",
        "chrome.tabs.update",
        "chrome.windows.update",
        "Input.insertText",
        "conversation/write",
        "tabs.remove",
    ):
        assert forbidden not in source


def test_background_selector_uses_proven_semantic_and_exact_slider_fallbacks() -> None:
    source = OWNER.read_text(encoding="utf-8")

    assert "_pr88InstantEffortExactSliderExpression" in source
    assert "_pr88InstantEffortExactSliderSnapshot" in source
    assert "unique_exact_slider_value" in source
    assert "current_effort_control_missing" in source
    assert "composer_missing" in source
    assert '[contenteditable="true"][role="textbox"][aria-multiline="true"]' in source
    assert "candidate.closest('main')" in source
    assert "candidate.closest('form')" in source
