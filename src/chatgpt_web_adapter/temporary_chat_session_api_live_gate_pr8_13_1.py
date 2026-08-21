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
from .temporary_product_runtime_pr8_13 import TemporaryProductWriteRuntimeError

FIRST_EXPECTED = "CWA_PR8_13_1_SESSION_FIRST_OK"
SECOND_EXPECTED = "CWA_PR8_13_1_SESSION_CONTINUE_OK"
EXPLICIT_ID_MUST_NOT_WRITE = "CWA_PR8_13_1_EXPLICIT_ID_MUST_NOT_WRITE"


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
        "pr": "PR8.13.1",
        "product_write_budget": 2,
        "product_write_completions": 0,
        "automatic_write_retry": False,
        "durable_fallback": False,
        "public_continuation_model": "LIVE_RUNTIME_SESSION_ONLY",
        "explicit_conversation_argument_supported": False,
        "profile": profile,
        "target_product_mode": PROFILE_TO_PRODUCT_MODE[profile],
        "turns": [],
    }

    lifecycle_ended = False
    try:
        first = runtime.send_text_observed(
            _prompt(FIRST_EXPECTED),
            conversation_mode="temporary",
            timeout=timeout,
            model_profile=profile,
        )
        report["product_write_completions"] += 1
        first_summary = _validate_temporary_execution(
            first,
            expected_text=FIRST_EXPECTED,
            expected_continuation=False,
        )
        first_summary["model_profile_selection"] = _validate_model_profile_selection(
            provider,
            profile=profile,
            lease_id=first_summary["browser_authority_lease_id"],
        )
        conversation_id = first_summary["conversation_id"]
        report["turns"].append(first_summary)

        # Public continuation deliberately omits conversation=<id>. The transport
        # must recover the ephemeral routing id from its own LIVE lifecycle only.
        second = runtime.send_text_observed(
            _prompt(SECOND_EXPECTED),
            conversation_mode="temporary",
            timeout=timeout,
            model_profile=profile,
        )
        report["product_write_completions"] += 1
        second_summary = _validate_temporary_execution(
            second,
            expected_text=SECOND_EXPECTED,
            expected_continuation=True,
        )
        second_summary["model_profile_selection"] = _validate_model_profile_selection(
            provider,
            profile=profile,
            lease_id=second_summary["browser_authority_lease_id"],
        )
        if second_summary["conversation_id"] != conversation_id:
            raise RuntimeError("PR8_13_1_SESSION_ROUTING_ID_CHANGED_ACROSS_IMPLICIT_CONTINUATION")
        report["turns"].append(second_summary)

        live_snapshot = runtime.temporary_lifecycle_snapshot()
        if (
            live_snapshot.get("state") != "LIVE"
            or live_snapshot.get("conversation_id") != conversation_id
            or live_snapshot.get("token_present") is not True
            or live_snapshot.get("token_exported") is not False
        ):
            raise RuntimeError("PR8_13_1_LIVE_SESSION_SNAPSHOT_INVALID")
        report["live_lifecycle"] = live_snapshot

        try:
            runtime.send_text_observed(
                EXPLICIT_ID_MUST_NOT_WRITE,
                conversation=conversation_id,
                conversation_mode="temporary",
                timeout=timeout,
            )
        except TemporaryProductWriteRuntimeError as error:
            if "PR8_13_1_TEMPORARY_EXPLICIT_CONVERSATION_FORBIDDEN" not in str(error):
                raise RuntimeError(
                    f"PR8_13_1_UNEXPECTED_EXPLICIT_ID_ERROR:{error}"
                ) from error
            if error.write_may_have_been_submitted is not False:
                raise RuntimeError("PR8_13_1_EXPLICIT_ID_WRITE_MAY_HAVE_BEEN_SUBMITTED")
            if error.reconciliation_required is not False:
                raise RuntimeError("PR8_13_1_EXPLICIT_ID_RECONCILIATION_UNEXPECTED")
            report["explicit_id_attempt"] = {
                "blocked_before_product_write": True,
                "error": str(error),
                "write_may_have_been_submitted": False,
                "reconciliation_required": False,
            }
        else:
            raise RuntimeError("PR8_13_1_EXPLICIT_ID_WAS_NOT_BLOCKED")

        if report["product_write_completions"] != report["product_write_budget"]:
            raise RuntimeError("PR8_13_1_PRODUCT_WRITE_BUDGET_MISMATCH")

        if runtime.end_temporary_chat() is not True:
            raise RuntimeError("PR8_13_1_EXPLICIT_END_NOT_PROVEN")
        lifecycle_ended = True
        ended_snapshot = runtime.temporary_lifecycle_snapshot()
        if (
            ended_snapshot.get("state") != "NOT_ESTABLISHED"
            or ended_snapshot.get("conversation_id") is not None
            or ended_snapshot.get("token_present") is not False
            or ended_snapshot.get("token_exported") is not False
        ):
            raise RuntimeError("PR8_13_1_ENDED_SESSION_SNAPSHOT_INVALID")
        report["ended_lifecycle"] = ended_snapshot

        report["ok"] = True
        report["summary"] = {
            "fresh_temporary_session_proven": True,
            "implicit_same_runtime_continuation_proven": True,
            "stable_internal_routing_identity_proven": True,
            "explicit_conversation_argument_blocked_before_write": True,
            "explicit_lifecycle_end_proven": True,
            "conversation_id_is_not_public_authority": True,
            "automatic_write_retry": False,
            "durable_fallback": False,
        }
        return report
    finally:
        if not lifecycle_ended:
            try:
                runtime.end_temporary_chat()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR8.13.1 Temporary Chat session-only public API live gate"
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
                    "pr": "PR8.13.1",
                    "error": "LIVE_WRITE_ACKNOWLEDGEMENT_REQUIRED",
                    "product_write_budget": 2,
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
                    "pr": "PR8.13.1",
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
