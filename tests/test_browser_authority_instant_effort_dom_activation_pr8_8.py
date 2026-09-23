from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
OWNER = ROOT / "service_worker_instant_effort_selection.js"


def test_dom_activation_contract() -> None:
    source = OWNER.read_text(encoding="utf-8")

    for token in (
        "target.click();",
        "PR8_8_INSTANT_EFFORT_DOM_TRIGGER_IDENTITY_NOT_PROVEN",
        "PR8_8_INSTANT_EFFORT_DOM_TRIGGER_CLICK_NOT_PROVEN",
        "_pr88InstantEffortResolvedSliderSnapshot",
        "_pr88InstantEffortDispatchEnter",
        "point?.mode!==expectedMode",
    ):
        assert token in source

    for forbidden in (
        "Input.insertText",
        "tabs.remove",
        "conversation/write",
        "_pr88SelectionRawClick(",
        "_pr88InstantEffortOpenPickerWithFallback =",
    ):
        assert forbidden not in source
