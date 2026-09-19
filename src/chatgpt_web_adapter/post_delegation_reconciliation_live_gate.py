from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .auth import DEFAULT_AUTH_FILE
from .browser_native_install import browser_native_deployment_status
from .browser_owned_write_runtime import (
    BrowserOwnedWriteRuntimeError,
    WRITE_SUBMITTED_GENERATION_INCOMPLETE,
    WRITE_SUBMITTED_TERMINAL_ASSISTANT,
)
from .product_runtime import assemble_product_runtime
from .temporary_chat_production_live_gate_pr8_13 import _prompt

SEED_EXPECTED = "CWA_PR14_9_SEED_OK"
PROBE_EXPECTED = "CWA_PR14_9_ABORT_PROBE_SHOULD_NOT_RETURN"


def _require_deployment_identity() -> dict[str, Any]:
    status = browser_native_deployment_status()
    if status.get("healthy") is not True:
        raise RuntimeError("PR14_9_DEPLOYMENT_IDENTITY_NOT_HEALTHY")

    source_revision = status.get("source_revision")
    deployment = status.get("deployment")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise RuntimeError("PR14_9_SOURCE_REVISION_UNPROVEN")
    if not isinstance(deployment, dict):
        raise RuntimeError("PR14_9_DEPLOYMENT_MANIFEST_MISSING")
    if deployment.get("source_revision") != source_revision:
        raise RuntimeError("PR14_9_DEPLOYED_SOURCE_REVISION_MISMATCH")
    if status.get("extension_digest_matches") is not True:
        raise RuntimeError("PR14_9_EXTENSION_DIGEST_MISMATCH")
    if status.get("host_matches_current_environment") is not True:
        raise RuntimeError("PR14_9_NATIVE_HOST_ENVIRONMENT_MISMATCH")

    return {
        "healthy": True,
        "source_revision": source_revision,
        "extension_digest": status.get("installed_extension_digest"),
        "installed_extension_dir": status.get("installed_extension_dir"),
        "host_executable": status.get("current_host_executable"),
    }


@contextmanager
def _one_shot_abort_probe(
    provider: Any,
    *,
    conversation_id: str,
) -> Iterator[Callable[[], int]]:
    original_rpc = getattr(provider, "_rpc", None)
    if not callable(original_rpc):
        raise RuntimeError("PR14_9_PROVIDER_RPC_UNAVAILABLE")

    had_instance_override = "_rpc" in getattr(provider, "__dict__", {})
    prior_instance_override = getattr(provider, "__dict__", {}).get("_rpc")
    turn_rpc_count = 0

    def probe_rpc(
        payload: dict[str, Any],
        *,
        timeout: float,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        nonlocal turn_rpc_count
        forwarded = payload
        if payload.get("type") == "turn":
            if turn_rpc_count != 0:
                raise RuntimeError("PR14_9_LIVE_GATE_SECOND_TURN_FORBIDDEN")
            if payload.get("conversationId") != conversation_id:
                raise RuntimeError("PR14_9_LIVE_GATE_CONVERSATION_ID_MISMATCH")
            turn_rpc_count += 1
            forwarded = {
                **payload,
                "postDelegationAbortProbe": True,
            }
        return original_rpc(
            forwarded,
            timeout=timeout,
            on_event=on_event,
        )

    provider._rpc = probe_rpc
    try:
        yield lambda: turn_rpc_count
    finally:
        if had_instance_override:
            provider.__dict__["_rpc"] = prior_instance_override
        else:
            provider.__dict__.pop("_rpc", None)


def run_live_gate(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    timeout: float = 150.0,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR14.9",
        "product_write_budget": 2,
        "product_write_attempts": 0,
        "automatic_write_retry": False,
        "consumer_dependency": False,
    }
    report["deployment"] = _require_deployment_identity()

    runtime = assemble_product_runtime(auth_file=auth_file)
    seed = runtime.send_text_observed(
        _prompt(SEED_EXPECTED),
        timeout=timeout,
    )
    report["product_write_attempts"] += 1

    response = seed.response
    actual = response.text.strip()
    if actual != SEED_EXPECTED:
        raise RuntimeError(
            f"PR14_9_SEED_RESPONSE_MISMATCH expected={SEED_EXPECTED!r} actual={actual!r}"
        )
    conversation_id = response.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise RuntimeError("PR14_9_SEED_CONVERSATION_ID_MISSING")
    conversation_id = conversation_id.strip()
    report["seed"] = {
        "response": actual,
        "conversation_id": conversation_id,
        "message_id": response.conversation.message_id,
        "runtime_tab_id": getattr(seed.observation, "runtime_tab_id", None),
    }

    write_transport = getattr(runtime, "write_transport", None)
    provider = getattr(write_transport, "provider", None)
    if provider is None:
        raise RuntimeError("PR14_9_BROWSER_PROVIDER_UNAVAILABLE")

    probe_error: BrowserOwnedWriteRuntimeError | None = None
    with _one_shot_abort_probe(
        provider,
        conversation_id=conversation_id,
    ) as probe_turn_count:
        try:
            runtime.send_text_observed(
                _prompt(PROBE_EXPECTED),
                conversation=conversation_id,
                timeout=timeout,
            )
        except BrowserOwnedWriteRuntimeError as error:
            probe_error = error
        else:
            raise RuntimeError("PR14_9_ABORT_PROBE_UNEXPECTEDLY_RETURNED_SUCCESS")
        finally:
            report["product_write_attempts"] += probe_turn_count()

    if probe_error is None:
        raise RuntimeError("PR14_9_ABORT_PROBE_ERROR_MISSING")
    if report["product_write_attempts"] != report["product_write_budget"]:
        raise RuntimeError("PR14_9_PRODUCT_WRITE_BUDGET_MISMATCH")
    if probe_error.post_delegation_abort_probe_triggered is not True:
        raise RuntimeError("PR14_9_ABORT_PROBE_TRIGGER_NOT_PROVEN")
    if probe_error.failure_kind not in {
        WRITE_SUBMITTED_GENERATION_INCOMPLETE,
        WRITE_SUBMITTED_TERMINAL_ASSISTANT,
    }:
        raise RuntimeError(
            "PR14_9_PRECISE_SUBMITTED_OUTCOME_NOT_PROVEN:"
            f"{probe_error.failure_kind}"
        )
    if probe_error.automatic_retry_allowed is not False:
        raise RuntimeError("PR14_9_AUTOMATIC_RETRY_MUST_BE_FALSE")
    if probe_error.manual_retry_safe_after_repair is not False:
        raise RuntimeError("PR14_9_MANUAL_RETRY_AUTHORITY_MUST_BE_FALSE")
    if probe_error.write_may_have_been_submitted is not True:
        raise RuntimeError("PR14_9_SUBMISSION_EVIDENCE_MISSING")

    reconciliation = probe_error.post_delegation_reconciliation
    if not isinstance(reconciliation, dict):
        raise RuntimeError("PR14_9_RECONCILIATION_EVIDENCE_MISSING")
    if reconciliation.get("conversation_id") != conversation_id:
        raise RuntimeError("PR14_9_RECONCILIATION_CONVERSATION_MISMATCH")
    if reconciliation.get("canonical_read_complete") is not True:
        raise RuntimeError("PR14_9_CANONICAL_READ_NOT_COMPLETE")
    if reconciliation.get("user_turn_persisted") is not True:
        raise RuntimeError("PR14_9_EXACT_USER_TURN_PERSISTENCE_NOT_PROVEN")

    report["probe"] = {
        "failure_kind": probe_error.failure_kind,
        "post_delegation_outcome": probe_error.post_delegation_outcome,
        "automatic_retry_allowed": probe_error.automatic_retry_allowed,
        "manual_retry_safe_after_repair": probe_error.manual_retry_safe_after_repair,
        "write_may_have_been_submitted": probe_error.write_may_have_been_submitted,
        "reconciliation_required": probe_error.reconciliation_required,
        "runtime_tab_id": probe_error.post_delegation_runtime_tab_id,
        "abort_probe_triggered": probe_error.post_delegation_abort_probe_triggered,
        "turn_lifecycle": (
            probe_error.turn_lifecycle.to_dict()
            if probe_error.turn_lifecycle is not None
            else None
        ),
        "reconciliation": reconciliation,
    }
    report["summary"] = {
        "one_seed_write": True,
        "one_probe_write": True,
        "second_probe_turn_forbidden_before_send": True,
        "response_stage_abort_probe_triggered": True,
        "exact_request_bound_user_persisted": True,
        "precise_submitted_outcome_proven": True,
        "automatic_write_retry": False,
        "consumer_dependency": False,
    }
    report["ok"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CWA-only live gate for post-delegation reconciliation"
    )
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required because this gate performs exactly two real product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR14.9",
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
            timeout=args.timeout,
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "pr": "PR14.9",
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
