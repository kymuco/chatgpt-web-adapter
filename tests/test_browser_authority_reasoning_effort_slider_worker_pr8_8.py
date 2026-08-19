import json

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_reasoning_effort_workers_are_additive_and_do_not_select_or_submit():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    topology_import = 'importScripts("service_worker_reasoning_effort_slider_topology_pr8_8.js")'
    governance_import = 'importScripts("service_worker_reasoning_effort_slider_governance_pr8_8.js")'
    assert topology_import in observability and governance_import in observability
    assert observability.index(topology_import) < observability.index(governance_import)

    topology = (root / "service_worker_reasoning_effort_slider_topology_pr8_8.js").read_text(encoding="utf-8")
    governance = (root / "service_worker_reasoning_effort_slider_governance_pr8_8.js").read_text(encoding="utf-8")
    for token in (
        "discreteStepMapping", "completeThreeStepMapping", "ariaValueNow",
        "advancedButtonCount", "dimensionsSeparated", "visibleModelValues", "visibleEffortValues",
    ):
        assert token in topology
    for token in (
        "reasoningEffortSliderSupported", "selectionControlClickForbidden",
        "conversationWriteGuardSupported", "selectionControlClickPerformed: false",
        "quickOpenClickPerformed", "advancedClickPerformed",
    ):
        assert token in governance
    for forbidden in (
        "Input.insertText", "submitOfficialPageTurn(", "chrome.tabs.create(",
        "chrome.tabs.update(", "chrome.tabs.remove(", "Network.getResponseBody", "document.cookie",
    ):
        assert forbidden not in topology
        assert forbidden not in governance
