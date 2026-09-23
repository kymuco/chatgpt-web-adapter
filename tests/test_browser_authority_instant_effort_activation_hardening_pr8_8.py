from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
OWNER = ROOT / "service_worker_instant_effort_selection.js"


def test_activation_hardening_contract() -> None:
    source = OWNER.read_text(encoding="utf-8")

    for token in (
        "_pr88InstantEffortOpenPickerWithFallback",
        "_pr88InstantEffortResolvedSliderSnapshot",
        "_pr88InstantEffortWaitForResolvedSlider",
        "_pr88InstantEffortWaitForResolvedSelected",
        "_pr88InstantEffortDispatchEnter",
        "key:'Enter'",
        "performance.now()-startedAt<3000",
    ):
        assert token in source

    for forbidden in (
        "_pr88SelectionRawClick =",
        "_pr88InstantEffortSliderSnapshot =",
        "_pr88InstantEffortOpenPickerWithFallback =",
        "Input.insertText",
        "tabs.remove",
        "conversation/write",
    ):
        assert forbidden not in source


def test_shipping_selector_calls_explicit_helpers() -> None:
    source = OWNER.read_text(encoding="utf-8")

    assert "_pr88InstantEffortOpenPickerWithFallback" in source
    assert "_pr88InstantEffortResolvedSliderSnapshot" in source
    assert "_pr88InstantEffortWaitForResolvedSlider" in source
    assert "_pr88InstantEffortWaitForResolvedSelected" in source
