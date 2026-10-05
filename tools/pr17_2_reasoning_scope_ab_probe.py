from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from chatgpt_web_adapter import assemble_product_runtime
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.product_model_profile_pr8_10 import ProductModelProfileProvider

EXPECTED_RUNTIME_REVISION = "PR17_2_BACKGROUND_PRODUCTION_R12"
WRITE_PLAN = (
    ("A_SETUP_HIGH", "DEEP", "CWA_PR17_2_SCOPE_A_HIGH_OK"),
    ("B_SETUP_MEDIUM", "BALANCED", "CWA_PR17_2_SCOPE_B_MEDIUM_OK"),
    ("A_MUTATE_INSTANT", "FAST", "CWA_PR17_2_SCOPE_A_INSTANT_OK"),
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


def _validate_observation(
    response: dict[str, Any],
    *,
    conversation_id: str | None,
    fresh_renderer: bool,
) -> dict[str, Any]:
    if response.get("reasoningScopeObservation") is not True:
        raise RuntimeError("PR17_2_SCOPE:OBSERVATION_FLAG_MISSING")
    if response.get("runtimeRevision") != EXPECTED_RUNTIME_REVISION:
        raise RuntimeError(
            "PR17_2_SCOPE:RUNTIME_REVISION_MISMATCH:"
            f"expected={EXPECTED_RUNTIME_REVISION}:"
            f"actual={response.get('runtimeRevision') or 'missing'}"
        )
    if response.get("selectedModeProven") is not True:
        raise RuntimeError("PR17_2_SCOPE:MODE_NOT_PROVEN")
    mode = response.get("selectedMode")
    if mode not in {"INSTANT", "MEDIUM", "HIGH"}:
        raise RuntimeError(f"PR17_2_SCOPE:MODE_UNSUPPORTED:{mode}")
    if response.get("stableSampleCount", 0) < 3:
        raise RuntimeError("PR17_2_SCOPE:MODE_NOT_STABLE")
    if response.get("conversationWriteCount") != 0:
        raise RuntimeError("PR17_2_SCOPE:READ_ONLY_OBSERVATION_WROTE")
    if response.get("tabActivated") is not False:
        raise RuntimeError("PR17_2_SCOPE:OBSERVATION_ACTIVATED_TAB")
    if response.get("tabWasActive") is not False:
        raise RuntimeError("PR17_2_SCOPE:OBSERVATION_TAB_WAS_ACTIVE")
    if response.get("debuggerAttachedAfter") is not False:
        raise RuntimeError("PR17_2_SCOPE:DEBUGGER_NOT_DETACHED")
    if response.get("freshRenderer") is not fresh_renderer:
        raise RuntimeError("PR17_2_SCOPE:FRESH_RENDERER_FLAG_MISMATCH")

    expected_kind = "conversation" if conversation_id is not None else "new_chat"
    if response.get("targetKind") != expected_kind:
        raise RuntimeError("PR17_2_SCOPE:TARGET_KIND_MISMATCH")
    if response.get("requestedConversationId") != conversation_id:
        raise RuntimeError("PR17_2_SCOPE:REQUESTED_CONVERSATION_MISMATCH")
    if response.get("observedConversationId") != conversation_id:
        raise RuntimeError("PR17_2_SCOPE:OBSERVED_CONVERSATION_MISMATCH")

    if fresh_renderer:
        if response.get("temporaryTabCreated") is not True:
            raise RuntimeError("PR17_2_SCOPE:TEMP_TAB_NOT_CREATED")
        if response.get("temporaryTabClosed") is not True:
            raise RuntimeError("PR17_2_SCOPE:TEMP_TAB_NOT_CLOSED")
    else:
        if response.get("temporaryTabCreated") is not False:
            raise RuntimeError("PR17_2_SCOPE:UNEXPECTED_TEMP_TAB")

    return dict(response)


def _observe(
    provider: ProductModelProfileProvider,
    *,
    conversation_id: str | None,
    fresh_renderer: bool,
    timeout: float,
) -> dict[str, Any]:
    response = provider._characterization_rpc(
        {
            "characterizeReasoningScopeObservation": True,
            "scopeConversationId": conversation_id,
            "scopeFreshRenderer": fresh_renderer,
        },
        timeout=timeout,
    )
    return _validate_observation(
        response,
        conversation_id=conversation_id,
        fresh_renderer=fresh_renderer,
    )


def _write(
    *,
    runtime: Any,
    provider: ProductModelProfileProvider,
    phase: str,
    profile: str,
    expected: str,
    conversation: str | None,
    timeout: float,
) -> dict[str, Any]:
    with provider.require_profile(profile):
        execution = runtime.send_text_observed(
            f"Reply with exactly: {expected}",
            conversation=conversation,
            timeout=timeout,
            conversation_mode="normal",
        )

    actual = execution.response.text.strip()
    if actual != expected:
        raise RuntimeError(
            f"PR17_2_SCOPE_{phase}:UNEXPECTED_RESPONSE:"
            f"expected={expected!r}:actual={actual!r}"
        )

    conversation_id = execution.response.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:CONVERSATION_ID_MISSING")
    if conversation is not None and conversation_id != conversation:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:CONVERSATION_ID_CHANGED")

    observation = execution.observation.to_dict()
    lease_id = observation.get("browser_authority_lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:LEASE_ID_MISSING")
    selection = provider.model_profile_selection_for_lease(lease_id)
    if selection.get("selectionComplete") is not True:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:SELECTION_NOT_COMPLETE")
    if selection.get("selectedModeAfterProven") is not True:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:SELECTION_NOT_PROVEN")
    if selection.get("conversationWriteBeforeSelection") is not False:
        raise RuntimeError(f"PR17_2_SCOPE_{phase}:WRITE_BEFORE_SELECTION")

    return {
        "phase": phase,
        "profile": profile,
        "response": actual,
        "conversation_id": conversation_id,
        "browser_authority_lease_id": lease_id,
        "selection": selection,
        "observation": observation,
    }


def _classify(
    *,
    persistent: dict[str, dict[str, Any]],
    fresh: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    p = {key: value["selectedMode"] for key, value in persistent.items()}
    f = {key: value["selectedMode"] for key, value in fresh.items()}

    setup_isolation = (
        p["a_after_b_setup"] == "HIGH"
        and p["b_after_setup"] == "MEDIUM"
    )
    mutation_isolation = (
        p["a_after_mutation"] == "INSTANT"
        and p["b_after_a_mutation"] == "MEDIUM"
    )
    fresh_isolation = f["a_after_mutation"] == "INSTANT" and f[
        "b_after_a_mutation"
    ] == "MEDIUM"

    if setup_isolation and mutation_isolation and fresh_isolation:
        verdict = "CONVERSATION_LOCAL_DURABLE"
    elif setup_isolation and mutation_isolation and not fresh_isolation:
        verdict = "RUNTIME_NAVIGATION_ISOLATED_BUT_FRESH_RENDERER_NOT_DURABLE"
    elif (
        p["a_after_b_setup"] == "MEDIUM"
        and p["b_after_setup"] == "MEDIUM"
        and p["a_after_mutation"] == "INSTANT"
        and p["b_after_a_mutation"] == "INSTANT"
    ):
        verdict = "SHARED_ACROSS_CONVERSATIONS_IN_PERSISTENT_RUNTIME"
    else:
        verdict = "MIXED_OR_INCONCLUSIVE"

    return {
        "verdict": verdict,
        "setup_isolation_same_renderer": setup_isolation,
        "mutation_isolation_same_renderer": mutation_isolation,
        "durable_isolation_fresh_renderers": fresh_isolation,
        "new_chat_mode_same_renderer": p["new_chat_after_a_mutation"],
        "new_chat_mode_fresh_renderer": f["new_chat_after_a_mutation"],
        "new_chat_matches_last_mutation_same_renderer": (
            p["new_chat_after_a_mutation"] == "INSTANT"
        ),
        "new_chat_matches_last_mutation_fresh_renderer": (
            f["new_chat_after_a_mutation"] == "INSTANT"
        ),
        "raw_modes": {
            "persistent": p,
            "fresh": f,
        },
    }


def run_gate(*, expected_head: str | None, timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    report: dict[str, Any] = {
        "schema": "CWA_PR17_2_REASONING_SCOPE_AB_V1",
        "head": head,
        "expected_head": expected_head,
        "head_matches": expected_head is None or head == expected_head,
        "tracked_clean": _tracked_clean(),
        "product_write_budget": 3,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "read_only_observation_count": 7,
        "ok": False,
    }
    if not report["head_matches"] or not report["tracked_clean"]:
        report["error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductModelProfileProvider()
    status = provider.characterization_status(timeout=5.0)
    if status.runtime_tab_id is not None:
        report["error"] = "PR17_2_SCOPE_INITIAL_RUNTIME_TAB_MUST_BE_ABSENT"
        report["initial_runtime_tab_id"] = status.runtime_tab_id
        return report

    support = provider.model_profile_support(timeout=5.0)
    revision = support.get("background_production_runtime_revision")
    report["runtime_revision"] = revision
    if revision != EXPECTED_RUNTIME_REVISION:
        report["error"] = (
            "PR17_2_SCOPE_RUNTIME_REVISION_MISMATCH:"
            f"expected={EXPECTED_RUNTIME_REVISION}:actual={revision or 'missing'}"
        )
        return report

    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    writes: list[dict[str, Any]] = []

    report["write_attempts"] += 1
    a_setup = _write(
        runtime=runtime,
        provider=provider,
        phase=WRITE_PLAN[0][0],
        profile=WRITE_PLAN[0][1],
        expected=WRITE_PLAN[0][2],
        conversation=None,
        timeout=timeout,
    )
    report["write_completions"] += 1
    writes.append(a_setup)
    conversation_a = a_setup["conversation_id"]

    report["write_attempts"] += 1
    b_setup = _write(
        runtime=runtime,
        provider=provider,
        phase=WRITE_PLAN[1][0],
        profile=WRITE_PLAN[1][1],
        expected=WRITE_PLAN[1][2],
        conversation=None,
        timeout=timeout,
    )
    report["write_completions"] += 1
    writes.append(b_setup)
    conversation_b = b_setup["conversation_id"]
    if conversation_a == conversation_b:
        raise RuntimeError("PR17_2_SCOPE:A_B_CONVERSATIONS_NOT_DISTINCT")

    persistent: dict[str, dict[str, Any]] = {
        "a_after_b_setup": _observe(
            provider,
            conversation_id=conversation_a,
            fresh_renderer=False,
            timeout=20.0,
        ),
        "b_after_setup": _observe(
            provider,
            conversation_id=conversation_b,
            fresh_renderer=False,
            timeout=20.0,
        ),
    }

    report["write_attempts"] += 1
    a_mutation = _write(
        runtime=runtime,
        provider=provider,
        phase=WRITE_PLAN[2][0],
        profile=WRITE_PLAN[2][1],
        expected=WRITE_PLAN[2][2],
        conversation=conversation_a,
        timeout=timeout,
    )
    report["write_completions"] += 1
    writes.append(a_mutation)

    persistent.update(
        {
            "a_after_mutation": _observe(
                provider,
                conversation_id=conversation_a,
                fresh_renderer=False,
                timeout=20.0,
            ),
            "b_after_a_mutation": _observe(
                provider,
                conversation_id=conversation_b,
                fresh_renderer=False,
                timeout=20.0,
            ),
            "new_chat_after_a_mutation": _observe(
                provider,
                conversation_id=None,
                fresh_renderer=False,
                timeout=20.0,
            ),
        }
    )

    fresh: dict[str, dict[str, Any]] = {
        "a_after_mutation": _observe(
            provider,
            conversation_id=conversation_a,
            fresh_renderer=True,
            timeout=20.0,
        ),
        "b_after_a_mutation": _observe(
            provider,
            conversation_id=conversation_b,
            fresh_renderer=True,
            timeout=20.0,
        ),
        "new_chat_after_a_mutation": _observe(
            provider,
            conversation_id=None,
            fresh_renderer=True,
            timeout=20.0,
        ),
    }

    report.update(
        {
            "ok": True,
            "conversation_a": conversation_a,
            "conversation_b": conversation_b,
            "writes": writes,
            "observations": {
                "persistent_runtime_navigation": persistent,
                "fresh_renderers": fresh,
            },
            "scope": _classify(persistent=persistent, fresh=fresh),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR17.2 Phase C A/B/new-chat reasoning state scope characterization"
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
