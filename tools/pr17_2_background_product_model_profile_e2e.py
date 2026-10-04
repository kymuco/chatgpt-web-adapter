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

SEQUENCE: tuple[str, ...] = ("FAST", "DEEP", "BALANCED")


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _prompt(profile: str) -> str:
    return f"Reply with exactly: CWA_PR17_2_BACKGROUND_{profile}_OK"


def _validate_observation(profile: str, observation: dict[str, Any]) -> None:
    if observation.get("write_event_observed") is not True:
        raise RuntimeError(f"PR17_2_{profile}:WRITE_EVENT_NOT_OBSERVED")
    if observation.get("tab_was_active_at_write_start") is not False:
        raise RuntimeError(f"PR17_2_{profile}:RUNTIME_TAB_ACTIVE_AT_WRITE_START")
    if observation.get("tab_activated_during_turn") is not False:
        raise RuntimeError(f"PR17_2_{profile}:TAB_ACTIVATED_DURING_TURN")
    if observation.get("foreground_activation_observed") is not False:
        raise RuntimeError(f"PR17_2_{profile}:FOREGROUND_ACTIVATION_OBSERVED")
    if observation.get("tab_active_after_write") is not False:
        raise RuntimeError(f"PR17_2_{profile}:RUNTIME_TAB_ACTIVE_AFTER_WRITE")


def _validate_selection(
    profile: str,
    lease_id: str,
    selection: dict[str, Any],
    *,
    require_mutation: bool,
) -> None:
    target_mode = PROFILE_TO_PRODUCT_MODE[profile]
    target_index = PRODUCT_MODE_TO_SLIDER_INDEX[target_mode]

    if selection.get("browserAuthorityLeaseId") != lease_id:
        raise RuntimeError(f"PR17_2_{profile}:LEASE_MISMATCH")
    if selection.get("requestedModelMode") != target_mode:
        raise RuntimeError(f"PR17_2_{profile}:REQUESTED_MODE_MISMATCH")
    if selection.get("requestedSliderIndex") != target_index:
        raise RuntimeError(f"PR17_2_{profile}:REQUESTED_SLIDER_INDEX_MISMATCH")
    if selection.get("selectionComplete") is not True:
        raise RuntimeError(f"PR17_2_{profile}:SELECTION_NOT_COMPLETE")
    if selection.get("selectedModeAfterProven") is not True:
        raise RuntimeError(f"PR17_2_{profile}:SELECTED_MODE_AFTER_NOT_PROVEN")
    if selection.get("selectedModeAfter") != target_mode:
        raise RuntimeError(f"PR17_2_{profile}:SELECTED_MODE_AFTER_MISMATCH")
    if selection.get("conversationWriteBeforeSelection") is not False:
        raise RuntimeError(f"PR17_2_{profile}:WRITE_BEFORE_SELECTION")
    if selection.get("transientForegroundActivated") is not False:
        raise RuntimeError(f"PR17_2_{profile}:TRANSIENT_FOREGROUND_ACTIVATED")
    if selection.get("transientForegroundProven") is not False:
        raise RuntimeError(f"PR17_2_{profile}:TRANSIENT_FOREGROUND_PROVEN")
    if selection.get("foregroundRestoreAttempted") is not False:
        raise RuntimeError(f"PR17_2_{profile}:FOREGROUND_RESTORE_ATTEMPTED")
    if selection.get("foregroundRestoreProven") is not True:
        raise RuntimeError(f"PR17_2_{profile}:FOREGROUND_RESTORE_CONTRACT_INVALID")

    if require_mutation:
        if selection.get("selectionPerformed") is not True:
            raise RuntimeError(f"PR17_2_{profile}:MUTATION_NOT_PERFORMED")
        if selection.get("backgroundSelectionAttempted") is not True:
            raise RuntimeError(f"PR17_2_{profile}:BACKGROUND_SELECTION_NOT_ATTEMPTED")
        if selection.get("backgroundSelectionProven") is not True:
            raise RuntimeError(f"PR17_2_{profile}:BACKGROUND_SELECTION_NOT_PROVEN")
        if selection.get("selectionMechanism") != (
            "REASONING_EFFORT_SLIDER_HOME_PLUS_RIGHT"
        ):
            raise RuntimeError(f"PR17_2_{profile}:UNEXPECTED_SELECTION_MECHANISM")


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_BACKGROUND_PRODUCT_MODEL_PROFILE_E2E_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "product_write_budget": len(SEQUENCE),
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "ok": False,
        "turns": [],
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductModelProfileProvider()
    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    conversation: str | None = None
    for index, profile in enumerate(SEQUENCE):
        expected = f"CWA_PR17_2_BACKGROUND_{profile}_OK"
        report["write_attempts"] += 1

        with provider.require_profile(profile):
            execution = runtime.send_text_observed(
                _prompt(profile),
                conversation=conversation,
                timeout=timeout,
                conversation_mode="normal",
            )

        report["write_completions"] += 1
        actual = execution.response.text.strip()
        if actual != expected:
            raise RuntimeError(
                f"PR17_2_{profile}:UNEXPECTED_RESPONSE "
                f"expected={expected!r} actual={actual!r}"
            )

        response_conversation = execution.response.conversation.conversation_id
        if not isinstance(response_conversation, str) or not response_conversation:
            raise RuntimeError(f"PR17_2_{profile}:CONVERSATION_ID_MISSING")
        if conversation is None:
            conversation = response_conversation
        elif response_conversation != conversation:
            raise RuntimeError(f"PR17_2_{profile}:CONVERSATION_ID_CHANGED")

        observation = execution.observation.to_dict()
        _validate_observation(profile, observation)

        lease_id = observation.get("browser_authority_lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise RuntimeError(f"PR17_2_{profile}:LEASE_ID_MISSING")

        selection = provider.model_profile_selection_for_lease(lease_id)
        _validate_selection(
            profile,
            lease_id,
            selection,
            require_mutation=index > 0,
        )

        report["turns"].append(
            {
                "profile": profile,
                "target_product_mode": PROFILE_TO_PRODUCT_MODE[profile],
                "target_slider_index": PRODUCT_MODE_TO_SLIDER_INDEX[
                    PROFILE_TO_PRODUCT_MODE[profile]
                ],
                "response": actual,
                "conversation_id": conversation,
                "observation": observation,
                "selection": selection,
            }
        )

    report["ok"] = True
    report["conversation"] = conversation
    report["summary"] = {
        "profiles_proven": list(SEQUENCE),
        "background_mutations_required": ["DEEP", "BALANCED"],
        "background_mutations_proven": True,
        "foreground_activation_observed": False,
        "tab_activation_observed": False,
        "strict_prewrite_selection_proven": True,
        "canonical_completion_proven": True,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR17.2 shipping model-profile background-selection end-to-end gate"
        )
    )
    parser.add_argument("--expected-head")
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required; "
            "this gate performs exactly three ChatGPT product writes"
        )

    report = run_gate(expected_head=args.expected_head, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
