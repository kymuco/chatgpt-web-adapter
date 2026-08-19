from __future__ import annotations

import json
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_worker_order_and_mutation_boundary():
    root = browser_native_extension_dir()
    assert json.loads((root / "manifest.json").read_text(encoding="utf-8"))["version"] == "0.1.13"
    obs = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    names = [
        "service_worker_instant_popup_subtree_forensics_pr8_8.js",
        "service_worker_picker_trigger_identity_pr8_8.js",
        "service_worker_picker_trigger_poll_timeline_pr8_8.js",
        "service_worker_picker_trigger_persistence_pr8_8.js",
    ]
    assert [obs.index(f'importScripts("{n}")') for n in names] == sorted(obs.index(f'importScripts("{n}")') for n in names)
    code = "\n".join((root / n).read_text(encoding="utf-8") for n in names[1:])
    for token in ("pickerTriggerIdentitySupported", "perPollMenuMaterializationTimelineSupported", "PRE_CLICK", "POST_CLICK_IMMEDIATE", "OPTION_POLL", "throw error"):
        assert token in code
    for token in ("Input.insertText", "submitOfficialPageTurn(", "chrome.tabs.create(", "chrome.tabs.remove(", "chrome.debugger.attach(", "Network.getResponseBody", "document.cookie"):
        assert token not in code

