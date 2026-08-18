from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_activation_hardening_contract():
    worker = (ROOT / "service_worker_instant_effort_activation_hardening_pr8_8.js").read_text(encoding="utf-8")
    for token in (
        "_pr88InstantEffortOpenPickerWithFallback",
        "_pr88InstantEffortResolvedSliderSnapshot",
        "_pr88InstantEffortWaitForResolvedSlider",
        "_pr88InstantEffortWaitForResolvedSelected",
        "_pr88InstantEffortDispatchEnter",
        "key:'Enter'",
        "performance.now()-startedAt<3000",
    ):
        assert token in worker
    for forbidden in (
        "_pr88SelectionRawClick =",
        "_pr88InstantEffortSliderSnapshot =",
        "Input.insertText",
        "tabs.remove",
        "tabs.update",
        "conversation/write",
    ):
        assert forbidden not in worker


def test_shipping_selector_calls_explicit_helpers():
    worker = (ROOT / "service_worker_instant_effort_slider_selection_pr8_8.js").read_text(encoding="utf-8")
    assert "_pr88InstantEffortOpenPickerWithFallback" in worker
    assert "_pr88InstantEffortResolvedSliderSnapshot" in worker
    assert "_pr88InstantEffortWaitForResolvedSlider" in worker
    assert "_pr88InstantEffortWaitForResolvedSelected" in worker
