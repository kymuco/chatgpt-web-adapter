from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .browser_native_install import browser_native_deployment_status
from .product_runtime import assemble_product_runtime
from .temporary_chat_production_live_gate_pr8_13 import (
    _prompt,
    _validate_temporary_execution,
)

A_SEED = "CWA_PR14_8_A_SEED_OK"
A_BIND = "CWA_PR14_8_A_BIND_OK"
B_SEED = "CWA_PR14_8_B_SEED_OK"
B_BIND = "CWA_PR14_8_B_BIND_OK"
A_REVISIT = "CWA_PR14_8_A_REVISIT_OK"
B_REVISIT = "CWA_PR14_8_B_REVISIT_OK"
TEMPORARY_EXPECTED = "CWA_PR14_8_TEMPORARY_CLOSE_OK"


def _require_deployment_identity() -> dict[str, Any]:
    status = browser_native_deployment_status()
    if status.get("healthy") is not True:
        raise RuntimeError("PR14_8_DEPLOYMENT_IDENTITY_NOT_HEALTHY")

    source_revision = status.get("source_revision")
    deployment = status.get("deployment")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise RuntimeError("PR14_8_SOURCE_REVISION_UNPROVEN")
    if not isinstance(deployment, dict):
        raise RuntimeError("PR14_8_DEPLOYMENT_MANIFEST_MISSING")
    if deployment.get("source_revision") != source_revision:
        raise RuntimeError("PR14_8_DEPLOYED_SOURCE_REVISION_MISMATCH")
    if status.get("extension_digest_matches") is not True:
        raise RuntimeError("PR14_8_EXTENSION_DIGEST_MISMATCH")
    if status.get("host_matches_current_environment") is not True:
        raise RuntimeError("PR14_8_NATIVE_HOST_ENVIRONMENT_MISMATCH")

    return {
        "healthy": True,
        "source_revision": source_revision,
        "extension_digest": status.get("installed_extension_digest"),
        "installed_extension_dir": status.get("installed_extension_dir"),
        "host_executable": status.get("current_host_executable"),
    }


def _normal_turn(
    runtime: Any,
    expected: str,
    *,
    conversation: str | None = None,
    timeout: float,
) -> dict[str, Any]:
    execution = runtime.send_text_observed(
        _prompt(expected),
        conversation=conversation,
        timeout=timeout,
    )
    response = execution.response
    actual = response.text.strip()
    if actual != expected:
        raise RuntimeError(
            f"PR14_8_RESPONSE_MISMATCH expected={expected!r} actual={actual!r}"
        )

    conversation_id = response.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise RuntimeError("PR14_8_CONVERSATION_ID_MISSING")
    conversation_id = conversation_id.strip()
    if conversation is not None and conversation_id != conversation:
        raise RuntimeError("PR14_8_CONTINUATION_CONVERSATION_ID_CHANGED")

    observation = execution.observation
    tab_id = getattr(observation, "runtime_tab_id", None)
    if isinstance(tab_id, bool) or not isinstance(tab_id, int):
        raise RuntimeError("PR14_8_RUNTIME_TAB_ID_MISSING")

    return {
        "response": actual,
        "conversation_id": conversation_id,
        "message_id": response.conversation.message_id,
        "runtime_tab_id": tab_id,
    }


def run_live_gate(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    timeout: float = 150.0,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR14.8",
        "product_write_budget": 7,
        "product_write_completions": 0,
        "automatic_write_retry": False,
        "consumer_dependency": None,
        "turns": [],
    }
    report["deployment"] = _require_deployment_identity()

    runtime = assemble_product_runtime(auth_file=auth_file)
    lifecycle_live = False
    try:
        a_seed = _normal_turn(runtime, A_SEED, timeout=timeout)
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "a_seed", **a_seed})

        a_bind = _normal_turn(
            runtime,
            A_BIND,
            conversation=a_seed["conversation_id"],
            timeout=timeout,
        )
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "a_bind", **a_bind})
        tab_a = a_bind["runtime_tab_id"]

        b_seed = _normal_turn(runtime, B_SEED, timeout=timeout)
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "b_seed", **b_seed})
        if b_seed["conversation_id"] == a_seed["conversation_id"]:
            raise RuntimeError("PR14_8_FRESH_CONVERSATION_ID_REUSED")

        b_bind = _normal_turn(
            runtime,
            B_BIND,
            conversation=b_seed["conversation_id"],
            timeout=timeout,
        )
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "b_bind", **b_bind})
        tab_b = b_bind["runtime_tab_id"]
        if tab_b == tab_a:
            raise RuntimeError("PR14_8_DISTINCT_CONVERSATIONS_SHARE_RETAINED_TAB")

        a_revisit = _normal_turn(
            runtime,
            A_REVISIT,
            conversation=a_seed["conversation_id"],
            timeout=timeout,
        )
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "a_revisit", **a_revisit})
        if a_revisit["runtime_tab_id"] != tab_a:
            raise RuntimeError("PR14_8_CONVERSATION_A_TAB_NOT_RETAINED")

        b_revisit = _normal_turn(
            runtime,
            B_REVISIT,
            conversation=b_seed["conversation_id"],
            timeout=timeout,
        )
        report["product_write_completions"] += 1
        report["turns"].append({"phase": "b_revisit", **b_revisit})
        if b_revisit["runtime_tab_id"] != tab_b:
            raise RuntimeError("PR14_8_CONVERSATION_B_TAB_NOT_RETAINED")

        temporary = runtime.send_text_observed(
            _prompt(TEMPORARY_EXPECTED),
            conversation_mode="temporary",
            timeout=timeout,
        )
        lifecycle_live = True
        report["product_write_completions"] += 1
        temporary_summary = _validate_temporary_execution(
            temporary,
            expected_text=TEMPORARY_EXPECTED,
            expected_continuation=False,
        )
        temporary_observation = temporary.observation.to_dict()
        temporary_tab = temporary_observation.get("runtime_tab_id")
        if isinstance(temporary_tab, bool) or not isinstance(temporary_tab, int):
            raise RuntimeError("PR14_8_TEMPORARY_TAB_ID_MISSING")
        if temporary_tab in {tab_a, tab_b}:
            raise RuntimeError("PR14_8_TEMPORARY_TAB_REUSED_RETAINED_SAVED_TAB")
        temporary_summary["runtime_tab_id"] = temporary_tab
        report["turns"].append({"phase": "temporary", **temporary_summary})

        # This call is the live regression for the broker self-deadlock fixed by
        # PR14.8. A proven Temporary turn must not leave the canonical-read lane
        # reserved, so explicit close must enter immediately. The exact deployed
        # extension only returns ENDED after observing the owned tab absent.
        if runtime.end_temporary_chat() is not True:
            raise RuntimeError("PR14_8_TEMPORARY_EXPLICIT_END_NOT_PROVEN")
        lifecycle_live = False

        ended = runtime.temporary_lifecycle_snapshot()
        if (
            ended.get("state") != "NOT_ESTABLISHED"
            or ended.get("conversation_id") is not None
            or ended.get("token_present") is not False
            or ended.get("token_exported") is not False
        ):
            raise RuntimeError("PR14_8_TEMPORARY_ENDED_SNAPSHOT_INVALID")
        report["temporary_ended_lifecycle"] = ended

        if report["product_write_completions"] != report["product_write_budget"]:
            raise RuntimeError("PR14_8_PRODUCT_WRITE_BUDGET_MISMATCH")

        report["ok"] = True
        report["summary"] = {
            "distinct_retained_tabs_proven": True,
            "conversation_a_exact_tab_reuse_proven": True,
            "conversation_b_exact_tab_reuse_proven": True,
            "temporary_uses_distinct_owned_tab": True,
            "temporary_page_owned_finality_proven": True,
            "temporary_close_entered_after_proven_turn": True,
            "temporary_owned_tab_absence_required_for_ended": True,
            "automatic_write_retry": False,
            "consumer_dependency": False,
        }
        return report
    finally:
        if lifecycle_live:
            try:
                runtime.end_temporary_chat()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR14.8 retained-tabs and Temporary-cleanup CWA-only live gate"
    )
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required because this gate performs exactly seven real product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR14.8",
                    "error": "LIVE_WRITE_ACKNOWLEDGEMENT_REQUIRED",
                    "product_write_budget": 7,
                },
                indent=2,
            )
        )
        return 2

    try:
        report = run_live_gate(auth_file=args.auth_file, timeout=args.timeout)
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR14.8",
                    "error": type(error).__name__,
                    "message": str(error),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
