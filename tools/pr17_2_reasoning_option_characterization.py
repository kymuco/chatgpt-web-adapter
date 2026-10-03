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


def _validate_no_write_contract(response: dict[str, Any]) -> None:
    for key in (
        "writePerformed",
        "textInsertionPerformed",
        "focusPerformed",
        "clickPerformed",
        "optionSelectionAttempted",
        "submitAttempted",
        "navigationPerformed",
        "tabCreated",
        "tabActivated",
        "automaticWriteRetry",
        "rawDomExported",
        "composerTextExported",
    ):
        if response.get(key) is not False:
            raise RuntimeError(f"PR17_2_NO_WRITE_CONTRACT_INVALID:{key}")
    if response.get("diagnosticOnly") is not True:
        raise RuntimeError("PR17_2_DIAGNOSTIC_ONLY_NOT_PROVEN")
    if response.get("fallbackTransport") is not None:
        raise RuntimeError("PR17_2_FALLBACK_TRANSPORT_MUST_BE_NULL")


def run_gate(*, expected_head: str | None, timeout: float, target: str) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    target_policy = target.strip().upper()
    if target_policy not in {"ACTIVE", "RUNTIME"}:
        raise ValueError("target must be active or runtime")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_REASONING_OPTION_CHARACTERIZATION_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "target": target_policy,
        "product_write_budget": 0,
        "write_attempted": False,
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = BrowserAuthorityCharacterizationProvider()
    response = provider._characterization_rpc(
        {
            "characterizeReasoningOptionSurface": True,
            "targetPolicy": target_policy,
        },
        timeout=timeout,
    )
    _validate_no_write_contract(response)

    report.update(
        {
            "ok": True,
            "diagnostic_tab_present": response.get("diagnosticTabPresent") is True,
            "diagnostic_tab_source": response.get("diagnosticTabSource"),
            "diagnostic_tab_selection_state": response.get(
                "diagnosticTabSelectionState"
            ),
            "chatgpt_tab_candidate_count": response.get("chatgptTabCandidateCount"),
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "tab_was_active": response.get("tabWasActive"),
            "document_visibility_state": response.get("documentVisibilityState"),
            "document_hidden": response.get("documentHidden"),
            "composer_present": response.get("composerPresent") is True,
            "picker_control": response.get("pickerControl"),
            "picker_control_candidate_count": response.get(
                "pickerControlCandidateCount"
            ),
            "option_candidate_count": response.get("optionCandidateCount"),
            "option_counts_by_mode": response.get("optionCountsByMode"),
            "options": response.get("options"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
            "write_performed": response.get("writePerformed"),
            "focus_performed": response.get("focusPerformed"),
            "click_performed": response.get("clickPerformed"),
            "option_selection_attempted": response.get("optionSelectionAttempted"),
            "tab_activated": response.get("tabActivated"),
            "automatic_write_retry": response.get("automaticWriteRetry"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR17.2 zero-write ChatGPT reasoning-option characterization"
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--target", choices=("active", "runtime"), default="active")
    args = parser.parse_args()

    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        target=args.target,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
