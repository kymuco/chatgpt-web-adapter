from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
)
OWNER = ROOT / "service_worker_instant_effort_selection.js"
RETIRED = (
    "service_worker_instant_effort_slider_contract_pr8_8.js",
    "service_worker_instant_effort_slider_key_pr8_8.js",
    "service_worker_instant_effort_slider_selection_pr8_8.js",
    "service_worker_instant_effort_activation_hardening_pr8_8.js",
    "service_worker_instant_effort_dom_activation_pr8_8.js",
    "service_worker_instant_effort_transient_foreground_pr8_8.js",
    "service_worker_instant_effort_slider_support_pr8_8.js",
)


def _source() -> str:
    return OWNER.read_text(encoding="utf-8")


def test_semantic_slider_home_shipping_path() -> None:
    source = _source()

    assert '[role="slider"],input[type="range"]' in source
    assert "min === 0 && max === 2" in source
    assert 'key:"Home"' in source
    assert "async function _pr88SelectionEnsureInstantCore(" in source
    assert "async function _pr88SelectionEnsureInstant(" in source
    assert "_pr88SelectionEnsureInstant =" not in source
    assert "REASONING_EFFORT_SLIDER_HOME" in source
    assert '_pr88SelectionPoint(debuggee, "instant_option")' not in source
    assert "advancedPickerClickForbidden: true" in source
    assert "modelControlClickForbidden: true" in source
    assert "automaticRetry: false" in source


def test_single_owner_has_no_direct_product_write_or_advanced_navigation() -> None:
    source = _source()

    for forbidden in (
        "/backend-api/f/conversation",
        "Page.navigate",
        "chrome.tabs.remove",
        "Network.getResponseBody",
        "chrome.cookies",
        "_pr88SelectionRecord =",
    ):
        assert forbidden not in source


def test_historical_instant_effort_fragments_are_retired() -> None:
    assert OWNER.exists()
    for name in RETIRED:
        assert not (ROOT / name).exists()
