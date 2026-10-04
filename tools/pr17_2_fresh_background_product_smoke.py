from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from chatgpt_web_adapter import assemble_product_runtime
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.product_model_profile_pr8_10 import (
    PRODUCT_MODE_TO_SLIDER_INDEX,
    PROFILE_TO_PRODUCT_MODE,
    ProductModelProfileProvider,
)

PROFILE = "FAST"
EXPECTED = "CWA_PR17_2_FRESH_BACKGROUND_PRODUCT_OK"
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


def _validate_observation(observation: dict[str, Any]) -> None:
    if observation.get("runtime_tab_preexisting") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:RUNTIME_TAB_PREEXISTING")
    if observation.get("runtime_tab_created_for_turn") is not True:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:RUNTIME_TAB_NOT_CREATED_FOR_TURN")
    if observation.get("write_event_observed") is not True:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:WRITE_EVENT_NOT_OBSERVED")
    if observation.get("tab_was_active_at_write_start") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:TAB_ACTIVE_AT_WRITE_START")
    if observation.get("tab_activated_during_turn") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:TAB_ACTIVATED_DURING_TURN")
    if observation.get("foreground_activation_observed") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:FOREGROUND_ACTIVATION_OBSERVED")
    if observation.get("tab_active_after_write") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:TAB_ACTIVE_AFTER_WRITE")


def _validate_selection(
    lease_id: str,
    selection: dict[str, Any],
) -> bool:
    target_mode = PROFILE_TO_PRODUCT_MODE[PROFILE]
    target_index = PRODUCT_MODE_TO_SLIDER_INDEX[target_mode]

    if selection.get("browserAuthorityLeaseId") != lease_id:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:LEASE_MISMATCH")
    if selection.get("requestedModelMode") != target_mode:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:REQUESTED_MODE_MISMATCH")
    if selection.get("requestedSliderIndex") != target_index:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:REQUESTED_INDEX_MISMATCH")
    if selection.get("selectionComplete") is not True:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:SELECTION_NOT_COMPLETE")
    if selection.get("selectedModeAfterProven") is not True:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:SELECTED_MODE_NOT_PROVEN")
    if selection.get("selectedModeAfter") != target_mode:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:SELECTED_MODE_MISMATCH")
    if selection.get("conversationWriteBeforeSelection") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:WRITE_BEFORE_SELECTION")
    if selection.get("transientForegroundActivated") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:TRANSIENT_FOREGROUND_ACTIVATED")
    if selection.get("foregroundRestoreAttempted") is not False:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:FOREGROUND_RESTORE_ATTEMPTED")

    mutated = selection.get("selectionPerformed") is True
    if mutated:
        if selection.get("backgroundSelectionProven") is not True:
            raise RuntimeError("PR17_2_FRESH_PRODUCT:BACKGROUND_SELECTION_NOT_PROVEN")
        if selection.get("homeBaselineProven") is not True:
            raise RuntimeError("PR17_2_FRESH_PRODUCT:HOME_BASELINE_NOT_PROVEN")
        if selection.get("stepwiseSelectionProven") is not True:
            raise RuntimeError("PR17_2_FRESH_PRODUCT:STEPWISE_SELECTION_NOT_PROVEN")
        if selection.get("backgroundFocusEmulationProven") is not True:
            raise RuntimeError("PR17_2_FRESH_PRODUCT:FOCUS_EMULATION_NOT_PROVEN")
        if selection.get("backgroundFocusEmulationRestored") is not True:
            raise RuntimeError("PR17_2_FRESH_PRODUCT:FOCUS_EMULATION_NOT_RESTORED")

    return mutated


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_FRESH_BACKGROUND_PRODUCT_SMOKE_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "product_write_budget": 1,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductModelProfileProvider()
    support = provider.model_profile_support()
    runtime_revision = support.get("background_production_runtime_revision")
    report["runtime_revision"] = runtime_revision
    report["expected_runtime_revision"] = EXPECTED_RUNTIME_REVISION
    if runtime_revision != EXPECTED_RUNTIME_REVISION:
        report["error"] = (
            "PR17_2_FRESH_PRODUCT_RUNTIME_REVISION_MISMATCH:"
            f"expected={EXPECTED_RUNTIME_REVISION}:actual={runtime_revision or 'missing'}"
        )
        return report

    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    report["write_attempts"] = 1
    with provider.require_profile(PROFILE):
        execution = runtime.send_text_observed(
            f"Reply with exactly: {EXPECTED}",
            conversation=None,
            timeout=timeout,
            conversation_mode="normal",
        )
    report["write_completions"] = 1

    actual = execution.response.text.strip()
    if actual != EXPECTED:
        raise RuntimeError(
            "PR17_2_FRESH_PRODUCT:UNEXPECTED_RESPONSE "
            f"expected={EXPECTED!r} actual={actual!r}"
        )

    conversation_id = execution.response.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:CONVERSATION_ID_MISSING")

    observation = execution.observation.to_dict()
    _validate_observation(observation)

    lease_id = observation.get("browser_authority_lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        raise RuntimeError("PR17_2_FRESH_PRODUCT:LEASE_ID_MISSING")

    selection = provider.model_profile_selection_for_lease(lease_id)
    mutated = _validate_selection(lease_id, selection)

    report.update(
        {
            "ok": True,
            "profile": PROFILE,
            "target_product_mode": PROFILE_TO_PRODUCT_MODE[PROFILE],
            "target_slider_index": PRODUCT_MODE_TO_SLIDER_INDEX[
                PROFILE_TO_PRODUCT_MODE[PROFILE]
            ],
            "response": actual,
            "conversation_id": conversation_id,
            "background_mutation_performed": mutated,
            "observation": observation,
            "selection": selection,
            "summary": {
                "fresh_runtime_tab_proven": True,
                "background_submit_proven": True,
                "foreground_activation_observed": False,
                "tab_activation_observed": False,
                "strict_prewrite_selection_proven": True,
                "canonical_completion_proven": True,
            },
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR17.2 one-write fresh-background production smoke for selection "
            "and submit"
        )
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--acknowledge-live-write", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()

    if not args.acknowledge_live_write:
        parser.error(
            "--acknowledge-live-write is required; "
            "this gate performs exactly one ChatGPT product write"
        )

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
