from pathlib import Path

ROOT = (
    Path(__file__).resolve().parents[1]
    / 'src'
    / 'chatgpt_web_adapter'
    / 'browser_native_extension'
)


def test_activation_hardening_contract():
    worker = (ROOT / 'service_worker_instant_effort_activation_hardening_pr8_8.js').read_text(encoding='utf-8')
    for token in (
        'visible_exact_slider',
        '_pr88InstantEffortDispatchEnter',
        "key:'Enter'",
        "trigger?.focusProven===true",
        'performance.now()-startedAt<3000',
        '_pr88InstantEffortPriorRawClick',
    ):
        assert token in worker
    for forbidden in ('Input.insertText', 'tabs.remove', 'tabs.update', 'conversation/write'):
        assert forbidden not in worker
