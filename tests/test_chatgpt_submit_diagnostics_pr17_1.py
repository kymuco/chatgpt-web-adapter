from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BASE = EXT / "service_worker.js"
HARDENING = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"
UI_COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_1_submit_timeout_reports_selector_and_initial_tab_activity() -> None:
    source = _source(BASE)

    assert "CHATGPT_SUBMIT_NOT_OBSERVED:${submit.strategy}" in source
    assert ':selector=${submit.selector || "none"}' in source
    assert ':tab_active=${diagnostics.tabWasActive === true ? "true" : "false"}' in source


def test_pr17_1_submit_diagnostics_do_not_add_post_commit_retry() -> None:
    hardening = _source(HARDENING)

    assert "PR11_3_TEXT_MOUSE_RELEASE_OUTCOME_UNCONFIRMED" in hardening
    assert "return _pr113SubmitTextWithEnterOnce(debuggee);" in hardening
    assert hardening.count("return _pr113SubmitTextWithEnterOnce(debuggee);") == 2

    release_index = hardening.index('type: "mouseReleased"')
    ambiguity_index = hardening.index(
        "throw new Error(PR113_MOUSE_RELEASE_UNCONFIRMED)"
    )
    assert release_index < ambiguity_index


def test_pr17_1_current_send_shape_is_already_covered_structurally() -> None:
    source = _source(UI_COMPAT)

    assert 'button[type="submit"]' in source
    assert "candidates.length !== 1" in source
    assert "pr11_7_structural_submit_control" in source
