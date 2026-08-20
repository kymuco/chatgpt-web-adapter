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
from .product_provenance import (
    CompletionSource,
    ConversationMode,
    ConversationModeEvidenceSource,
    TemporaryLifecycleEvidenceSource,
    TemporaryLifecycleState,
)
from .product_runtime import assemble_product_runtime
from .standalone_send import (
    DEFAULT_STANDALONE_MODEL_PROFILE,
    STANDALONE_MODEL_PROFILES,
    normalize_standalone_model_profile,
)
from .temporary_chat_canonical_read_probe import probe_temporary_canonical_read
from .temporary_product_runtime_pr8_13 import (
    TEMPORARY_PREWRITE_PROOF,
    TEMPORARY_READBACK_PLANE,
    TEMPORARY_SESSION_PLANE,
    TEMPORARY_WRITE_PLANE,
    TemporaryProductWriteRuntimeError,
)

FIRST_EXPECTED = "CWA_PR8_13_TEMPORARY_FIRST_OK"
SECOND_EXPECTED = "CWA_PR8_13_TEMPORARY_CONTINUE_OK"
THIRD_BLOCKED_TEXT = "CWA_PR8_13_MUST_NOT_WRITE_AFTER_END"


def _prompt(expected: str) -> str:
    return f"Reply with exactly: {expected}"


def _observation_payload(execution: Any) -> dict[str, Any]:
    observation = getattr(execution, "observation", None)
    to_dict = getattr(observation, "to_dict", None)
    if not callable(to_dict):
        raise RuntimeError("PR8_13_LIVE_GATE_OBSERVATION_MISSING")
    payload = to_dict()
    if not isinstance(payload, dict):
        raise RuntimeError("PR8_13_LIVE_GATE_OBSERVATION_INVALID")
    return dict(payload)


def _validate_temporary_execution(
    execution: Any,
    *,
    expected_text: str,
    expected_continuation: bool,
) -> dict[str, Any]:
    response = execution.response
    actual = response.text.strip()
    if actual != expected_text:
        raise RuntimeError(
            f"PR8_13_LIVE_GATE_RESPONSE_MISMATCH expected={expected_text!r} actual={actual!r}"
        )

    conversation_id = response.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise RuntimeError("PR8_13_LIVE_GATE_CONVERSATION_ID_MISSING")
    conversation_id = conversation_id.strip()

    if response.request.temporary is not True:
        raise RuntimeError("PR8_13_LIVE_GATE_REQUEST_NOT_MARKED_TEMPORARY")
    if response.request.is_continuation is not expected_continuation:
        raise RuntimeError("PR8_13_LIVE_GATE_CONTINUATION_FLAG_MISMATCH")

    observation = _observation_payload(execution)
    if observation.get("temporary_mode_proven") is not True:
        raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_MODE_NOT_PROVEN")
    if observation.get("temporary_prewrite_proof") != TEMPORARY_PREWRITE_PROOF:
        raise RuntimeError("PR8_13_LIVE_GATE_PREWRITE_PROOF_MISMATCH")
    if observation.get("temporary_lifecycle_state") != "LIVE":
        raise RuntimeError("PR8_13_LIVE_GATE_LIFECYCLE_NOT_LIVE")
    if observation.get("temporary_live_write_authority_proven") is not True:
        raise RuntimeError("PR8_13_LIVE_GATE_LIVE_AUTHORITY_NOT_PROVEN")
    if observation.get("temporary_paused_conversation_write_count") != 1:
        raise RuntimeError("PR8_13_LIVE_GATE_EXPECTED_EXACTLY_ONE_PAUSED_PRODUCT_WRITE")
    if observation.get("stream_observation_count", 0) <= 0:
        raise RuntimeError("PR8_13_LIVE_GATE_STREAM_OBSERVATION_MISSING")
    if observation.get("stream_delivery_incomplete") is not False:
        raise RuntimeError("PR8_13_LIVE_GATE_STREAM_DELIVERY_INCOMPLETE")
    if observation.get("temporary_continuation_identity_proven") is not expected_continuation:
        raise RuntimeError("PR8_13_LIVE_GATE_CONTINUATION_IDENTITY_PROOF_MISMATCH")

    lease_id = observation.get("browser_authority_lease_id")
    if not isinstance(lease_id, str) or not lease_id.strip():
        raise RuntimeError("PR8_13_LIVE_GATE_BROWSER_AUTHORITY_LEASE_MISSING")

    provenance = execution.provenance
    if provenance is None:
        raise RuntimeError("PR8_13_LIVE_GATE_PROVENANCE_MISSING")
    mode = provenance.conversation_mode
    if (
        mode is None
        or mode.requested_conversation_mode is not ConversationMode.TEMPORARY
        or mode.observed_conversation_mode is not ConversationMode.TEMPORARY
        or mode.observed_mode_evidence_source is not ConversationModeEvidenceSource.PRODUCT_MODE_OBSERVATION
        or mode.observed_mode_proven is not True
    ):
        raise RuntimeError("PR8_13_LIVE_GATE_MODE_PROVENANCE_INVALID")

    lifecycle = provenance.temporary_lifecycle
    if (
        lifecycle is None
        or lifecycle.temporary_lifecycle_state is not TemporaryLifecycleState.LIVE
        or lifecycle.lifecycle_evidence_source
        is not TemporaryLifecycleEvidenceSource.PRODUCT_LIFECYCLE_OBSERVATION
        or lifecycle.lifecycle_state_proven is not True
        or lifecycle.live_write_authority_proven is not True
    ):
        raise RuntimeError("PR8_13_LIVE_GATE_LIFECYCLE_PROVENANCE_INVALID")

    completion = provenance.completion
    if (
        completion.completed is not True
        or completion.source is not CompletionSource.TRANSPORT_RETURN
        or completion.canonical_completion_proven is not False
    ):
        raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_FINALITY_INVALID")
    if provenance.write_plane != TEMPORARY_WRITE_PLANE:
        raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_WRITE_PLANE_MISMATCH")
    if provenance.readback_plane != TEMPORARY_READBACK_PLANE:
        raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_READBACK_PLANE_MISMATCH")
    if provenance.session_plane != TEMPORARY_SESSION_PLANE:
        raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_SESSION_PLANE_MISMATCH")

    return {
        "response": actual,
        "conversation_id": conversation_id,
        "message_id": response.conversation.message_id,
        "finish_reason": response.conversation.finish_reason,
        "browser_authority_lease_id": lease_id,
        "temporary_mode_proven": True,
        "temporary_prewrite_proof": observation.get("temporary_prewrite_proof"),
        "temporary_continuation_identity_proven": observation.get(
            "temporary_continuation_identity_proven"
        ),
        "temporary_paused_conversation_write_count": observation.get(
            "temporary_paused_conversation_write_count"
        ),
        "stream_observation_count": observation.get("stream_observation_count"),
        "canonical_completion_proven": completion.canonical_completion_proven,
        "completion_source": completion.source.value,
        "readback_plane": provenance.readback_plane,
    }


def _validate_model_profile_selection(
    provider: ProductModelProfileProvider,
    *,
    profile: str,
    lease_id: str,
) -> dict[str, Any]:
    record = provider.model_profile_selection_for_lease(lease_id)
    target = PROFILE_TO_PRODUCT_MODE[profile]
    if record.get("browserAuthorityLeaseId") != lease_id:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_LEASE_MISMATCH")
    if record.get("requestedModelMode") != target:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_TARGET_MISMATCH")
    if record.get("selectionComplete") is not True:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_SELECTION_INCOMPLETE")
    if record.get("selectedModeAfterProven") is not True:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_SELECTION_NOT_PROVEN")
    if record.get("selectedModeAfter") != target:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_SELECTED_MODE_MISMATCH")
    if record.get("conversationWriteBeforeSelection") is True:
        raise RuntimeError("PR8_13_LIVE_GATE_PROFILE_WRITE_BEFORE_SELECTION")
    return {
        "requested_model_mode": target,
        "selected_mode_after": record.get("selectedModeAfter"),
        "selected_mode_after_proven": True,
        "conversation_write_before_selection": False,
    }


def _validate_canonical_not_found(result: Any, *, phase: str) -> dict[str, Any]:
    if result.canonical_payload_read_calls != 1:
        raise RuntimeError(f"PR8_13_{phase}_CANONICAL_READ_COUNT_MISMATCH")
    if result.canonical_read_succeeded is not False:
        raise RuntimeError(f"PR8_13_{phase}_CANONICAL_READ_UNEXPECTEDLY_SUCCEEDED")
    if result.canonical_readability_status != "NOT_FOUND" or result.http_status != 404:
        raise RuntimeError(
            f"PR8_13_{phase}_CANONICAL_EXPECTED_404_NOT_FOUND: "
            f"status={result.canonical_readability_status!r} http={result.http_status!r}"
        )
    if result.write_performed or result.attach_performed or result.browser_navigation_performed:
        raise RuntimeError(f"PR8_13_{phase}_CANONICAL_PROBE_CROSSED_READ_ONLY_BOUNDARY")
    return {
        "source_temporary_tab_state": result.source_temporary_tab_state,
        "canonical_read_succeeded": False,
        "canonical_readability_status": "NOT_FOUND",
        "http_status": 404,
        "canonical_payload_read_calls": 1,
        "write_performed": False,
        "attach_performed": False,
        "browser_navigation_performed": False,
    }


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
        "pr": "PR8.13",
        "product_write_budget": 2,
        "product_write_completions": 0,
        "automatic_write_retry": False,
        "durable_fallback": None,
        "profile": profile,
        "target_product_mode": PROFILE_TO_PRODUCT_MODE[profile],
        "turns": [],
    }

    lifecycle_ended = False
    conversation_id: str | None = None
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

        second = runtime.send_text_observed(
            _prompt(SECOND_EXPECTED),
            conversation=conversation_id,
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
            raise RuntimeError("PR8_13_LIVE_GATE_TEMPORARY_ID_CHANGED_ACROSS_LIVE_CONTINUATION")
        if second_summary["browser_authority_lease_id"] == first_summary["browser_authority_lease_id"]:
            raise RuntimeError("PR8_13_LIVE_GATE_BROWSER_AUTHORITY_LEASE_REUSED_ACROSS_TURNS")
        report["turns"].append(second_summary)

        live_snapshot = runtime.temporary_lifecycle_snapshot()
        if (
            live_snapshot.get("state") != "LIVE"
            or live_snapshot.get("conversation_id") != conversation_id
            or live_snapshot.get("token_present") is not True
            or live_snapshot.get("token_exported") is not False
        ):
            raise RuntimeError("PR8_13_LIVE_GATE_LIVE_LIFECYCLE_SNAPSHOT_INVALID")
        report["live_lifecycle"] = live_snapshot

        while_live = probe_temporary_canonical_read(
            conversation_id,
            source_temporary_tab_confirmed_open=True,
            client=runtime.canonical,
            timeout=timeout,
        )
        report["canonical_while_live"] = _validate_canonical_not_found(
            while_live,
            phase="WHILE_LIVE",
        )

        if runtime.end_temporary_chat() is not True:
            raise RuntimeError("PR8_13_LIVE_GATE_EXPLICIT_END_NOT_PROVEN")
        lifecycle_ended = True
        ended_snapshot = runtime.temporary_lifecycle_snapshot()
        if (
            ended_snapshot.get("state") != "NOT_ESTABLISHED"
            or ended_snapshot.get("conversation_id") is not None
            or ended_snapshot.get("token_present") is not False
            or ended_snapshot.get("token_exported") is not False
        ):
            raise RuntimeError("PR8_13_LIVE_GATE_ENDED_LIFECYCLE_SNAPSHOT_INVALID")
        report["ended_lifecycle"] = ended_snapshot

        after_close = probe_temporary_canonical_read(
            conversation_id,
            source_temporary_tab_confirmed_closed=True,
            client=runtime.canonical,
            timeout=timeout,
        )
        report["canonical_after_close"] = _validate_canonical_not_found(
            after_close,
            phase="AFTER_CLOSE",
        )

        try:
            runtime.send_text_observed(
                THIRD_BLOCKED_TEXT,
                conversation=conversation_id,
                conversation_mode="temporary",
                timeout=timeout,
                model_profile=profile,
            )
        except TemporaryProductWriteRuntimeError as error:
            if "PR8_13_TEMPORARY_LIFECYCLE_NOT_LIVE" not in str(error):
                raise RuntimeError(
                    f"PR8_13_LIVE_GATE_UNEXPECTED_POST_END_ERROR:{error}"
                ) from error
            if error.write_may_have_been_submitted is not False:
                raise RuntimeError("PR8_13_LIVE_GATE_POST_END_WRITE_MAY_HAVE_BEEN_SUBMITTED")
            if error.reconciliation_required is not False:
                raise RuntimeError("PR8_13_LIVE_GATE_POST_END_RECONCILIATION_UNEXPECTED")
            report["post_end_continuation"] = {
                "blocked_before_product_write": True,
                "error": str(error),
                "write_may_have_been_submitted": False,
                "reconciliation_required": False,
            }
        else:
            raise RuntimeError("PR8_13_LIVE_GATE_POST_END_CONTINUATION_WAS_NOT_BLOCKED")

        if report["product_write_completions"] != report["product_write_budget"]:
            raise RuntimeError("PR8_13_LIVE_GATE_PRODUCT_WRITE_BUDGET_MISMATCH")

        report["ok"] = True
        report["summary"] = {
            "fresh_temporary_prewrite_proven": True,
            "same_lifecycle_continuation_proven": True,
            "same_temporary_conversation_identity_proven": True,
            "canonical_while_live_not_found": True,
            "canonical_after_close_not_found": True,
            "explicit_lifecycle_end_proven": True,
            "post_end_continuation_blocked_before_write": True,
            "page_owned_temporary_finality_proven": True,
            "durable_fallback": False,
            "automatic_write_retry": False,
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
        description="PR8.13 Temporary Chat production graduation live gate"
    )
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument(
        "--profile",
        type=normalize_standalone_model_profile,
        choices=STANDALONE_MODEL_PROFILES,
        default=DEFAULT_STANDALONE_MODEL_PROFILE,
        help="semantic profile; default DEEP maps to product HIGH",
    )
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required; this gate performs exactly two Temporary product writes"
        )

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
                    "pr": "PR8.13",
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
