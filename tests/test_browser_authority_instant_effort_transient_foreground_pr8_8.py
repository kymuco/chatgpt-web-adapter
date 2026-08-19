from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / 'src'
    / 'chatgpt_web_adapter'
    / 'browser_native_extension'
)


def test_transient_foreground_contract():
    worker = (ROOT / 'service_worker_instant_effort_transient_foreground_pr8_8.js').read_text(encoding='utf-8')
    for token in (
        'const _pr88InstantEffortForegroundPriorEnsureInstant = _pr88SelectionEnsureInstant',
        "chrome.tabs.update(tabId, {active: true})",
        "document.visibilityState==='visible'",
        '_pr88InstantEffortRestorePriorTab',
        'finally',
        "chrome.tabs.update(state.priorActiveTabId, {active: true})",
        "before?.selectedMode === 'INSTANT'",
    ):
        assert token in worker
    for forbidden in (
        '_pr88SelectionRawClick =',
        '_pr88InstantEffortSliderSnapshot =',
        'Input.insertText',
        'conversation/write',
        'tabs.remove',
    ):
        assert forbidden not in worker
