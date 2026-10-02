from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _validate_no_write_contract(response: dict[str, Any]) -> None:
    expected_false = (
        "rawDomExported",
        "composerTextExported",
        "writePerformed",
        "textInsertionPerformed",
        "focusPerformed",
        "clickPerformed",
        "submitAttempted",
        "navigationPerformed",
        "tabCreated",
        "automaticWriteRetry",
    )
    if response.get("diagnosticOnly") is not True:
        raise RuntimeError("PR17_1_DIAGNOSTIC_ONLY_NOT_PROVEN")
    for key in expected_false:
        if response.get(key) is not False:
            raise RuntimeError(f"PR17_1_NO_WRITE_CONTRACT_INVALID:{key}")
    if response.get("fallbackTransport") is not None:
        raise RuntimeError("PR17_1_FALLBACK_TRANSPORT_MUST_BE_NULL")


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head

    report: dict[str, Any] = {
        "schema": "CWA_PR17_1_CHATGPT_COMPOSER_SUBMIT_CHARACTERIZATION_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "product_write_budget": 0,
        "write_attempted": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = BrowserAuthorityCharacterizationProvider()
    response = provider._characterization_rpc(
        {
            "characterizeChatGPTComposerSubmitSurface": True,
            "timeoutMs": int(timeout * 1000),
        },
        timeout=timeout,
    )
    _validate_no_write_contract(response)

    report.update(
        {
            "ok": True,
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "diagnostic_tab_present": response.get("diagnosticTabPresent") is True,
            "diagnostic_tab_source": response.get("diagnosticTabSource"),
            "diagnostic_tab_selection_state": response.get(
                "diagnosticTabSelectionState"
            ),
            "chatgpt_tab_candidate_count": response.get("chatgptTabCandidateCount"),
            "composer_candidate_count": response.get("composerCandidateCount"),
            "scoped_control_count": response.get("scopedControlCount"),
            "legacy_control_count": response.get("legacyControlCount"),
            "selected_composer": response.get("selectedComposer"),
            "derived_scope": response.get("derivedScope"),
            "composer_candidates": response.get("composerCandidates"),
            "scoped_controls": response.get("scopedControls"),
            "legacy_controls": response.get("legacyControls"),
            "old_resolver_selected": response.get("oldResolverSelected"),
            "raw_dom_exported": response.get("rawDomExported"),
            "composer_text_exported": response.get("composerTextExported"),
            "write_performed": response.get("writePerformed"),
            "text_insertion_performed": response.get("textInsertionPerformed"),
            "focus_performed": response.get("focusPerformed"),
            "click_performed": response.get("clickPerformed"),
            "submit_attempted": response.get("submitAttempted"),
            "navigation_performed": response.get("navigationPerformed"),
            "tab_created": response.get("tabCreated"),
            "automatic_write_retry": response.get("automaticWriteRetry"),
            "fallback_transport": response.get("fallbackTransport"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR17.1 zero-write ChatGPT composer/submit drift characterization"
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
