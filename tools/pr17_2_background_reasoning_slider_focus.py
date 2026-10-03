from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _validate_contract(response: dict[str, Any]) -> None:
    if response.get("diagnosticOnly") is not True:
        raise RuntimeError("PR17_2_BACKGROUND_FOCUS_DIAGNOSTIC_ONLY_NOT_PROVEN")
    for key in (
        "tabActivated",
        "reasoningValueMutationAttempted",
        "keyDispatchPerformed",
        "mouseDispatchPerformed",
        "conversationWriteAttempted",
    ):
        if response.get(key) is not False:
            raise RuntimeError(f"PR17_2_BACKGROUND_FOCUS_CONTRACT_INVALID:{key}")


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_BACKGROUND_REASONING_SLIDER_FOCUS_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "conversation_write_budget": 0,
        "reasoning_value_mutation_budget": 0,
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = BrowserAuthorityCharacterizationProvider()
    response = provider._characterization_rpc(
        {"characterizeBackgroundReasoningSliderFocus": True},
        timeout=timeout,
    )
    _validate_contract(response)

    report.update(
        {
            "ok": True,
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "tab_was_active": response.get("tabWasActive"),
            "document_visible_before": response.get("documentVisibleBefore"),
            "selected_mode_before": response.get("selectedModeBefore"),
            "selected_mode_before_proven": response.get("selectedModeBeforeProven"),
            "picker_found": response.get("pickerFound") is True,
            "picker_candidate_count": response.get("pickerCandidateCount"),
            "ui_trigger_click_performed": response.get("uiTriggerClickPerformed"),
            "slider_found": response.get("sliderFound") is True,
            "slider_candidate_count": response.get("sliderCandidateCount"),
            "slider_min": response.get("sliderMin"),
            "slider_max": response.get("sliderMax"),
            "slider_now_before": response.get("sliderNowBefore"),
            "slider_focus_attempted": response.get("sliderFocusAttempted"),
            "slider_focus_proven": response.get("sliderFocusProven"),
            "slider_now_after_focus": response.get("sliderNowAfterFocus"),
            "selected_mode_after_focus": response.get("selectedModeAfterFocus"),
            "selected_mode_after_focus_proven": response.get(
                "selectedModeAfterFocusProven"
            ),
            "selected_mode_unchanged": response.get("selectedModeUnchanged"),
            "ui_trigger_restore_attempted": response.get("uiTriggerRestoreAttempted"),
            "ui_trigger_restore_proven": response.get("uiTriggerRestoreProven"),
            "tab_activated": response.get("tabActivated"),
            "reasoning_value_mutation_attempted": response.get(
                "reasoningValueMutationAttempted"
            ),
            "key_dispatch_performed": response.get("keyDispatchPerformed"),
            "mouse_dispatch_performed": response.get("mouseDispatchPerformed"),
            "conversation_write_attempted": response.get("conversationWriteAttempted"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR17.2 background reasoning-slider focus characterization"
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
