from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)

EXPECTED_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R12"


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _validate(response: dict[str, Any]) -> None:
    required_true = (
        "diagnosticOnly",
        "freshBackgroundKeyboardProbe",
        "runtimeTabCreated",
        "focusEmulationAttempted",
        "focusEmulationProven",
        "sliderFocusProven",
        "homeDispatched",
        "homeBaselineProven",
        "initialModeRestored",
        "focusEmulationRestoreAttempted",
        "focusEmulationRestored",
        "runtimeTabClosed",
    )
    for key in required_true:
        if response.get(key) is not True:
            raise RuntimeError(f"PR17_2_FRESH_KEYBOARD_NOT_PROVEN:{key}")

    required_false = (
        "tabWasActive",
        "conversationWriteAttempted",
        "conversationWriteObserved",
        "tabActivated",
        "debuggerAttachedAfter",
    )
    for key in required_false:
        if response.get(key) is not False:
            raise RuntimeError(f"PR17_2_FRESH_KEYBOARD_CONTRACT_INVALID:{key}")

    if response.get("runtimeRevision") != EXPECTED_RUNTIME_REVISION:
        raise RuntimeError(
            "PR17_2_FRESH_KEYBOARD_RUNTIME_REVISION_MISMATCH:"
            f"expected={EXPECTED_RUNTIME_REVISION}:"
            f"actual={response.get('runtimeRevision') or 'missing'}"
        )
    if response.get("conversationWriteCount") != 0:
        raise RuntimeError("PR17_2_FRESH_KEYBOARD_CONVERSATION_WRITE_COUNT_NONZERO")
    if response.get("sliderNowAfterHome") != 0:
        raise RuntimeError("PR17_2_FRESH_KEYBOARD_HOME_VALUE_NOT_ZERO")
    focus_mechanism = response.get("sliderFocusMechanism")
    if focus_mechanism not in {"DOM.focus_primary", "DOM.focus_relaxed", "DOM.focus_exact"}:
        raise RuntimeError("PR17_2_FRESH_KEYBOARD_FOCUS_MECHANISM_MISMATCH")


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_FRESH_BACKGROUND_REASONING_KEYBOARD_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "product_write_budget": 0,
        "conversation_write_budget": 0,
        "reasoning_value_mutation_budget": 1,
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = BrowserAuthorityCharacterizationProvider()
    response = provider._characterization_rpc(
        {"characterizeFreshBackgroundReasoningKeyboard": True},
        timeout=timeout,
    )
    _validate(response)

    report.update(
        {
            "ok": True,
            "runtime_revision": response.get("runtimeRevision"),
            "initial_mode": response.get("initialMode"),
            "initial_index": response.get("initialIndex"),
            "slider_focus_mechanism": response.get("sliderFocusMechanism"),
            "home_baseline_proven": response.get("homeBaselineProven"),
            "initial_mode_restored": response.get("initialModeRestored"),
            "conversation_write_count": response.get("conversationWriteCount"),
            "tab_activated": response.get("tabActivated"),
            "runtime_tab_closed": response.get("runtimeTabClosed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR17.2 fresh active:false reasoning-keyboard probe with zero "
            "conversation writes"
        )
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
