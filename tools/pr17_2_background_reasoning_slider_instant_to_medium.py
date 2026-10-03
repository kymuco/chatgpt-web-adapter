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
    required_true = (
        "diagnosticOnly",
        "backgroundReasoningStepMutation",
        "runtimeTabPresent",
        "selectedModeBeforeProven",
        "sliderFound",
        "sliderFocusProven",
        "homeDispatched",
        "homeBaselineProven",
        "reasoningValueMutationAttempted",
        "reasoningValueMutationProven",
        "keyDispatchPerformed",
        "selectedModeAfterProven",
    )
    for key in required_true:
        if response.get(key) is not True:
            raise RuntimeError(f"PR17_2_BACKGROUND_STEP_NOT_PROVEN:{key}")

    required_false = (
        "tabActivated",
        "tabActivatedDuringGate",
        "mouseDispatchPerformed",
        "conversationWriteAttempted",
        "conversationWriteObserved",
    )
    for key in required_false:
        if response.get(key) is not False:
            raise RuntimeError(f"PR17_2_BACKGROUND_STEP_CONTRACT_INVALID:{key}")

    if response.get("selectedModeBefore") != "INSTANT":
        raise RuntimeError("PR17_2_BACKGROUND_STEP_INITIAL_MODE_NOT_INSTANT")
    if response.get("targetMode") != "MEDIUM":
        raise RuntimeError("PR17_2_BACKGROUND_STEP_TARGET_NOT_MEDIUM")
    if response.get("sliderMin") != 0 or response.get("sliderMax") != 2:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_SLIDER_RANGE_INVALID")
    if response.get("sliderNowBefore") != 0:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_INITIAL_VALUE_NOT_INSTANT")
    if response.get("targetSliderValue") != 1:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_TARGET_VALUE_NOT_MEDIUM")
    if response.get("arrowRightDispatchCount") != 1:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_ARROW_COUNT_INVALID")
    if response.get("sliderNowAfter") != 1:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_FINAL_VALUE_NOT_MEDIUM")
    if response.get("selectedModeAfter") != "MEDIUM":
        raise RuntimeError("PR17_2_BACKGROUND_STEP_FINAL_MODE_NOT_MEDIUM")
    if response.get("conversationWriteCount") != 0:
        raise RuntimeError(
            "PR17_2_BACKGROUND_STEP_CONVERSATION_WRITE_COUNT_NONZERO"
        )
    if response.get("uiTriggerRestoreAttempted") is True:
        if response.get("uiTriggerRestoreProven") is not True:
            raise RuntimeError("PR17_2_BACKGROUND_STEP_TRIGGER_RESTORE_NOT_PROVEN")
    if response.get("debuggerAttachedAfter") is not False:
        raise RuntimeError("PR17_2_BACKGROUND_STEP_DEBUGGER_STILL_ATTACHED")


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_BACKGROUND_REASONING_SLIDER_INSTANT_TO_MEDIUM_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "conversation_write_budget": 0,
        "reasoning_value_mutation_budget": 1,
        "target_mode": "MEDIUM",
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = BrowserAuthorityCharacterizationProvider()
    response = provider._characterization_rpc(
        {"characterizeBackgroundReasoningSliderInstantToMedium": True},
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
            "initial_mode_proof_kind": response.get("initialModeProofKind"),
            "slider_found": response.get("sliderFound") is True,
            "slider_min": response.get("sliderMin"),
            "slider_max": response.get("sliderMax"),
            "slider_now_before": response.get("sliderNowBefore"),
            "slider_focus_proven": response.get("sliderFocusProven"),
            "home_dispatched": response.get("homeDispatched"),
            "home_baseline_proven": response.get("homeBaselineProven"),
            "arrow_right_dispatch_count": response.get("arrowRightDispatchCount"),
            "selected_mode_after": response.get("selectedModeAfter"),
            "selected_mode_after_proven": response.get("selectedModeAfterProven"),
            "slider_now_after": response.get("sliderNowAfter"),
            "reasoning_value_mutation_attempted": response.get(
                "reasoningValueMutationAttempted"
            ),
            "reasoning_value_mutation_proven": response.get(
                "reasoningValueMutationProven"
            ),
            "key_dispatch_performed": response.get("keyDispatchPerformed"),
            "mouse_dispatch_performed": response.get("mouseDispatchPerformed"),
            "conversation_write_attempted": response.get("conversationWriteAttempted"),
            "conversation_write_observed": response.get("conversationWriteObserved"),
            "conversation_write_count": response.get("conversationWriteCount"),
            "network_request_count": response.get("networkRequestCount"),
            "tab_activated": response.get("tabActivated"),
            "tab_activated_during_gate": response.get("tabActivatedDuringGate"),
            "ui_trigger_restore_attempted": response.get("uiTriggerRestoreAttempted"),
            "ui_trigger_restore_proven": response.get("uiTriggerRestoreProven"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR17.2 background INSTANT-to-MEDIUM reasoning-slider mutation"
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
