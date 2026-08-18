from pathlib import Path

ROOT = Path(__file__).parents[1] / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_semantic_slider_home_shipping_path():
    contract = _read("service_worker_instant_effort_slider_contract_pr8_8.js")
    key = _read("service_worker_instant_effort_slider_key_pr8_8.js")
    selection = _read("service_worker_instant_effort_slider_selection_pr8_8.js")
    support = _read("service_worker_instant_effort_slider_support_pr8_8.js")
    assert '[role="slider"],input[type="range"]' in contract
    assert "min === 0 && max === 2" in contract
    assert 'key:"Home"' in key
    assert '_pr88SelectionEnsureInstant = async function' in selection
    assert 'REASONING_EFFORT_SLIDER_HOME' in selection
    assert '_pr88SelectionPoint(debuggee, "instant_option")' not in selection
    assert 'advancedPickerClickForbidden: true' in support
    assert 'modelControlClickForbidden: true' in support
    assert 'automaticRetry: false' in support


def test_shipping_worker_has_no_direct_product_write_or_advanced_navigation():
    text = "\n".join(_read(name) for name in (
        "service_worker_instant_effort_slider_contract_pr8_8.js",
        "service_worker_instant_effort_slider_key_pr8_8.js",
        "service_worker_instant_effort_slider_selection_pr8_8.js",
        "service_worker_instant_effort_slider_support_pr8_8.js",
    ))
    for forbidden in (
        "/backend-api/f/conversation", "Page.navigate", "chrome.tabs.remove",
        "Network.getResponseBody", "chrome.cookies",
    ):
        assert forbidden not in text
