from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .product_model_profile_pr8_10 import (
    PROFILE_TO_PRODUCT_MODE,
    ProductModelProfileProvider,
)
from .product_runtime import assemble_product_runtime
from .standalone_send import (
    DEFAULT_STANDALONE_MODEL_PROFILE,
    STANDALONE_MODEL_PROFILES,
    normalize_standalone_model_profile,
)
from .temporary_chat_production_live_gate_pr8_13 import (
    _prompt,
    _validate_model_profile_selection,
    _validate_temporary_execution,
)

FIRST_EXPECTED = "CWA_PR8_13_2_FRESH_START_ONE_OK"
SECOND_EXPECTED = "CWA_PR8_13_2_FRESH_START_TWO_OK"


def _require_live_snapshot(runtime: Any, conversation_id: str) -> dict[str, Any]:
    snapshot = runtime.temporary_lifecycle_snapshot()
    if (
        snapshot.get("state") != "LIVE"
        or snapshot.get("conversation_id") != conversation_id
        or snapshot.get("token_present") is not True
        or snapshot.get("token_exported") is not False
    ):
        raise RuntimeError("PR8_13_2_LIVE_LIFECYCLE_SNAPSHOT_INVALID")
    return snapshot


def _end_and_require_closed(runtime: Any) -> dict[str, Any]:
    if runtime.end_temporary_chat() is not True:
        raise RuntimeError("PR8_13_2_EXPLICIT_END_NOT_PROVEN")
    snapshot = runtime.temporary_lifecycle_snapshot()
    if (
        snapshot.get("state") != "NOT_ESTABLISHED"
        or snapshot.get("conversation_id") is not None
        or snapshot.get("token_present") is not False
        or snapshot.get("token_exported") is not False
    ):
        raise RuntimeError("PR8_13_2_ENDED_LIFECYCLE_SNAPSHOT_INVALID")
    return snapshot


def run_live_gate(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    profile: str = DEFAULT_STANDALONE_MODEL_PROFILE,
    timeout: float = 150.0,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    profile = normalize_standalone_model_profile(profile)

    provider = ProductModelProfileProvider()
    runtime = assemble_product_runtime(
        auth_file=auth_file,
        provider=provider,
    )

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR8.13.2",
        "product_write_budget": 2,
        "product_write_completions": 0,
        "fresh_lifecycle_budget": 2,
        "fresh_lifecycle_completions": 0,
        "automatic_write_retry": False,
        "durable_fallback": False,
        "profile": profile,
        "target_product_mode": PROFILE_TO_PRODUCT_MODE[profile],
        "turns": [],
    }

    lifecycle_live = False
    conversation_ids: list[str] = []
    lease_ids: list[str] = []

    try:
        for index, expected in enumerate((FIRST_EXPECTED, SECOND_EXPECTED), start=1):
            execution = runtime.send_text_observed(
                _prompt(expected),
                conversation_mode="temporary",
                timeout=timeout,
                model_profile=profile,
            )
            lifecycle_live = True
            report["product_write_completions"] += 1
            report["fresh_lifecycle_completions"] += 1

            summary = _validate_temporary_execution(
                execution,
                expected_text=expected,
                expected_continuation=False,
            )
            summary["fresh_lifecycle_index"] = index
            summary["model_profile_selection"] = _validate_model_profile_selection(
                provider,
                profile=profile,
                lease_id=summary["browser_authority_lease_id"],
            )
            if summary["temporary_paused_conversation_write_count"] != 1:
                raise RuntimeError("PR8_13_2_EXPECTED_EXACTLY_ONE_PRODUCT_WRITE_PER_FRESH_LIFECYCLE")

            conversation_id = summary["conversation_id"]
            conversation_ids.append(conversation_id)
            lease_ids.append(summary["browser_authority_lease_id"])
            summary["live_lifecycle"] = _require_live_snapshot(runtime, conversation_id)
            summary["ended_lifecycle"] = _end_and_require_closed(runtime)
            lifecycle_live = False
            report["turns"].append(summary)

        if report["product_write_completions"] != report["product_write_budget"]:
            raise RuntimeError("PR8_13_2_PRODUCT_WRITE_BUDGET_MISMATCH")
        if report["fresh_lifecycle_completions"] != report["fresh_lifecycle_budget"]:
            raise RuntimeError("PR8_13_2_FRESH_LIFECYCLE_BUDGET_MISMATCH")
        if len(set(conversation_ids)) != 2:
            raise RuntimeError("PR8_13_2_FRESH_LIFECYCLES_REUSED_ROUTING_IDENTITY")
        if len(set(lease_ids)) != 2:
            raise RuntimeError("PR8_13_2_BROWSER_AUTHORITY_LEASE_REUSED")

        report["ok"] = True
        report["summary"] = {
            "two_independent_fresh_temporary_lifecycles_proven": True,
            "fresh_routing_identity_rotated": True,
            "fresh_browser_authority_lease_rotated": True,
            "each_fresh_turn_prewrite_proven": True,
            "each_fresh_turn_exactly_one_product_write": True,
            "explicit_end_between_fresh_lifecycles_proven": True,
            "automatic_write_retry": False,
            "durable_fallback": False,
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
        description="PR8.13.2 Temporary fresh-session startup-readiness live gate"
    )
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument(
        "--profile",
        type=normalize_standalone_model_profile,
        choices=STANDALONE_MODEL_PROFILES,
        default=DEFAULT_STANDALONE_MODEL_PROFILE,
    )
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required because this gate performs exactly two real Temporary product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR8.13.2",
                    "error": "LIVE_WRITE_ACKNOWLEDGEMENT_REQUIRED",
                    "product_write_budget": 2,
                    "fresh_lifecycle_budget": 2,
                },
                indent=2,
            )
        )
        return 2

    try:
        report = run_live_gate(
            auth_file=args.auth_file,
            profile=args.profile,
            timeout=args.timeout,
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR8.13.2",
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
