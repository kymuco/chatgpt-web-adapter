from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BASE = EXT / "service_worker.js"
RECOVERY = EXT / "service_worker_recovery.js"
SCHEMA16 = EXT / "service_worker_rich_input_schema16_repair_pr9_2.js"
SCHEMA17 = EXT / "service_worker_rich_input_schema17_repair_pr9_2.js"
HARDENING = EXT / "service_worker_text_submit_commit_hardening_pr11_3.js"
UI_COMPAT = EXT / "service_worker_ui_compat_pr11_7.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr17_1_submit_timeout_reports_exact_owner_selector_and_tab_activity() -> None:
    owners = (
        (BASE, "base"),
        (RECOVERY, "recovery"),
        (SCHEMA16, "schema16"),
        (SCHEMA17, "schema17"),
    )
    for path, owner in owners:
        source = _source(path)

        assert "CHATGPT_SUBMIT_NOT_OBSERVED:${submit.strategy}" in source
        assert f":owner={owner}" in source
        assert ':selector=${submit.selector || "none"}' in source
        assert (
            ':tab_active=${diagnostics.tabWasActive === true ? "true" : "false"}'
            in source
        )
        assert (
            ':commit_tab_activated=${submit.tabActivatedForCommit === true ? "true" : "false"}'
            in source
        )
        assert (
            ':point_refreshed=${submit.submitPointRefreshedAfterActivation === true ? "true" : "false"}'
            in source
        )
        assert (
            ':point_delta_px=${Number.isFinite(submit.submitPointDeltaPx) ? submit.submitPointDeltaPx : "na"}'
            in source
        )
        assert (
            ':event_probe=${submit.eventProbeInstalled === true ? "true" : "false"}'
            in source
        )
        assert ':probe_reason=${submit.eventProbeInstallReason || "unknown"}' in source
        assert ':probe_hit=${submit.eventProbeHitTag || "none"}' in source
        assert ':probe_error=${submit.eventProbeErrorName || "none"}' in source
        assert ':events=${submit.eventProbeSummary || "unavailable"}' in source


def test_pr17_1_foreground_repair_changes_tab_selection_not_window_focus() -> None:
    hardening = _source(HARDENING)

    assert "chrome.tabs.update(tabId, { active: true })" in hardening
    assert (
        "chrome.tabs.update(state.previousActiveTabId, { active: true })" in hardening
    )
    assert "chrome.windows.update" not in hardening
    assert "focused: true" not in hardening


def test_pr17_1_submit_point_is_refreshed_after_foreground_activation() -> None:
    hardening = _source(HARDENING)

    prepare_index = hardening.index("await _pr113PrepareMouseCommitTab(debuggee)")
    refresh_index = hardening.index(
        "commitPoint = await _pr113WaitForSubmitPoint("
    )
    probe_index = hardening.index("await _pr113InstallSubmitEventProbe(")
    moved_index = hardening.index('type: "mouseMoved"')

    assert prepare_index < refresh_index < probe_index < moved_index
    assert "submitPointDeltaPx" in hardening


def test_pr17_1_submit_event_probe_is_bounded_and_text_free() -> None:
    hardening = _source(HARDENING)

    assert "__cwaPr171SubmitEventProbeV1" in hardening
    assert '"pointerdown"' in hardening
    assert '"mousedown"' in hardening
    assert '"pointerup"' in hardening
    assert '"mouseup"' in hardening
    assert '"click"' in hardening
    assert '"submit"' in hardening
    assert "isTrusted" in hardening
    assert "defaultPrevented" in hardening
    assert "submitterIsButton" in hardening
    assert "innerText" not in hardening
    assert "textContent" not in hardening


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
