from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import tempfile
from typing import Any, Iterable
import uuid
import zlib

from .client import ChatGPTWebClient
from .product_model_profile_pr8_10 import ProductModelProfileProvider
from .product_provenance import CompletionSource, ProductExecutionProvenance
from .product_runtime import assemble_product_runtime

SCHEMA = 7
PRODUCT_WRITE_BUDGET = 3

_IMAGE_REPLY = "BLUE,RED,GREEN"
_FILE_REPLY = "CWA_PR9_2_FILE_EVIDENCE_7Q4M9X"
_CONTINUATION_REPLY = "CWA_PR9_2_CONTINUATION_EVIDENCE_K8N2VP"

_IMAGE_PROMPT = (
    "Inspect the attached PNG image. It contains three solid vertical color bands. "
    "Reply with only the color names from left to right in uppercase, separated "
    "by commas with no spaces."
)
_FILE_PROMPT = (
    "Read the attached text file. Find the line beginning with EVIDENCE:. "
    "Reply with only the text after EVIDENCE:, exactly as written."
)
_CONTINUATION_PROMPT = (
    "Read the newly attached text file in this continuation. Find the line "
    "beginning with EVIDENCE:. Reply with only the text after EVIDENCE:, exactly "
    "as written."
)


class ProductRichInputLiveProvider(ProductModelProfileProvider):
    """Production provider plus a PR9.2 no-write overlay-presence probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "characterizeRichInputSupport": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if response.get("request_id") != request_id:
            raise RuntimeError("PR9_2_RICH_INPUT_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_RICH_INPUT_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )
        return {
            "supported": response.get("richInputSupported") is True,
            "schema": response.get("richInputSchemaVersion"),
            "staging_primitive": response.get("stagingPrimitive"),
            "max_attachment_count": response.get("maxAttachmentCount"),
            "native_messaging_carries_attachment_bytes": response.get(
                "nativeMessagingCarriesAttachmentBytes"
            ),
            "official_page_owns_upload": response.get("officialPageOwnsUpload"),
            "official_page_owns_protected_write": response.get(
                "officialPageOwnsProtectedWrite"
            ),
            "recovery_before_attachment_staging": response.get(
                "recoveryBeforeAttachmentStaging"
            ),
            "stale_attachment_failure_fence": response.get(
                "staleAttachmentFailureFence"
            ),
            "stale_attachment_fence_persistent_across_worker_restart": response.get(
                "staleAttachmentFencePersistentAcrossWorkerRestart"
            ),
            "single_total_turn_deadline": response.get("singleTotalTurnDeadline"),
            "pre_submit_deadline_guard": response.get("preSubmitDeadlineGuard"),
            "deadline_bounded_post_write_cleanup": response.get(
                "deadlineBoundedPostWriteCleanup"
            ),
            "post_write_fence_retained_until_next_prewrite": response.get(
                "postWriteFenceRetainedUntilNextPrewrite"
            ),
            "enter_key_release_affects_submitted_outcome": response.get(
                "enterKeyReleaseAffectsSubmittedOutcome"
            ),
            "mouse_to_enter_fallback_after_release_attempt": response.get(
                "mouseToEnterFallbackAfterReleaseAttempt"
            ),
            "mouse_release_outcome_ambiguity_fails_closed": response.get(
                "mouseReleaseOutcomeAmbiguityFailsClosed"
            ),
            "stale_attachment_cleanup_proof": response.get(
                "staleAttachmentCleanupProof"
            ),
            "attachment_count_evidence": response.get("attachmentCountEvidence"),
            "attachment_evidence_stable_poll_count": response.get(
                "attachmentEvidenceStablePollCount"
            ),
            "pre_submit_attachment_revalidation": response.get(
                "preSubmitAttachmentRevalidation"
            ),
            "post_send_readiness_attachment_revalidation": response.get(
                "postSendReadinessAttachmentRevalidation"
            ),
            "protected_submit_primitive": response.get("protectedSubmitPrimitive"),
            "rich_input_raw_cdp_input_submit_disabled": response.get(
                "richInputRawCdpInputSubmitDisabled"
            ),
            "rich_input_enter_fallback_enabled": response.get(
                "richInputEnterFallbackEnabled"
            ),
            "late_protected_submit_execution_prevented_by_page_deadline": response.get(
                "lateProtectedSubmitExecutionPreventedByPageDeadline"
            ),
            "atomic_attachment_validation_and_submit": response.get(
                "atomicAttachmentValidationAndSubmit"
            ),
            "post_click_debugger_ack_required": response.get(
                "postClickDebuggerAckRequired"
            ),
            "protected_submit_outcome_proof": response.get(
                "protectedSubmitOutcomeProof"
            ),
            "submit_observation_reserve_ms": response.get("submitObservationReserveMs"),
            "stale_attachment_cleanup_requires_session_runtime_identity": response.get(
                "staleAttachmentCleanupRequiresSessionRuntimeIdentity"
            ),
            "stale_attachment_identity_mismatch_closes_tab": response.get(
                "staleAttachmentIdentityMismatchClosesTab"
            ),
            "stale_attachment_identity_mismatch_fails_closed": response.get(
                "staleAttachmentIdentityMismatchFailsClosed"
            ),
            "stale_attachment_unproven_identity_fails_closed": response.get(
                "staleAttachmentUnprovenIdentityFailsClosed"
            ),
            "automatic_write_retry": response.get("automaticWriteRetry"),
            "fallback_transport": response.get("fallbackTransport"),
            "write_performed": response.get("writePerformed"),
        }


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_RICH_INPUT_SUPPORT_NOT_PROVEN")
    if support.get("staging_primitive") != "DOM.setFileInputFiles":
        raise RuntimeError("PR9_2_RICH_INPUT_STAGING_PRIMITIVE_MISMATCH")
    maximum = support.get("max_attachment_count")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        raise RuntimeError("PR9_2_RICH_INPUT_ATTACHMENT_LIMIT_INVALID")
    if support.get("native_messaging_carries_attachment_bytes") is not False:
        raise RuntimeError("PR9_2_NATIVE_MESSAGING_BYTE_BOUNDARY_NOT_PROVEN")
    if support.get("official_page_owns_upload") is not True:
        raise RuntimeError("PR9_2_OFFICIAL_PAGE_UPLOAD_OWNERSHIP_NOT_PROVEN")
    if support.get("official_page_owns_protected_write") is not True:
        raise RuntimeError("PR9_2_OFFICIAL_PAGE_WRITE_OWNERSHIP_NOT_PROVEN")
    if support.get("recovery_before_attachment_staging") is not True:
        raise RuntimeError("PR9_2_RECOVERY_BEFORE_STAGING_NOT_PROVEN")
    if support.get("stale_attachment_failure_fence") is not True:
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_FAILURE_FENCE_NOT_PROVEN")
    if support.get("stale_attachment_fence_persistent_across_worker_restart") is not True:
        raise RuntimeError("PR9_2_PERSISTENT_STALE_ATTACHMENT_FENCE_NOT_PROVEN")
    if support.get("single_total_turn_deadline") is not True:
        raise RuntimeError("PR9_2_SINGLE_TOTAL_TURN_DEADLINE_NOT_PROVEN")
    if support.get("pre_submit_deadline_guard") is not True:
        raise RuntimeError("PR9_2_PRE_SUBMIT_DEADLINE_GUARD_NOT_PROVEN")
    if support.get("deadline_bounded_post_write_cleanup") is not True:
        raise RuntimeError("PR9_2_DEADLINE_BOUNDED_POST_WRITE_CLEANUP_NOT_PROVEN")
    if support.get("post_write_fence_retained_until_next_prewrite") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_FENCE_RETENTION_NOT_PROVEN")
    if support.get("enter_key_release_affects_submitted_outcome") is not False:
        raise RuntimeError("PR9_2_ENTER_KEY_RELEASE_OUTCOME_NOT_PROVEN")
    if support.get("mouse_to_enter_fallback_after_release_attempt") is not False:
        raise RuntimeError("PR9_2_MOUSE_TO_ENTER_POST_RELEASE_RETRY_NOT_PROVEN")
    if support.get("mouse_release_outcome_ambiguity_fails_closed") is not True:
        raise RuntimeError("PR9_2_MOUSE_RELEASE_AMBIGUITY_FAIL_CLOSED_NOT_PROVEN")
    if (
        support.get("stale_attachment_cleanup_proof")
        != "RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED"
    ):
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_CLEANUP_PROOF_NOT_PROVEN")
    if support.get("attachment_count_evidence") != "PAGE_OWNED_COMPOSER_ATTACHMENT_STATE":
        raise RuntimeError("PR9_2_PAGE_ATTACHMENT_COUNT_EVIDENCE_NOT_PROVEN")
    stable_polls = support.get("attachment_evidence_stable_poll_count")
    if not isinstance(stable_polls, int) or isinstance(stable_polls, bool) or stable_polls < 2:
        raise RuntimeError("PR9_2_PAGE_ATTACHMENT_STABILITY_NOT_PROVEN")
    if support.get("pre_submit_attachment_revalidation") is not True:
        raise RuntimeError("PR9_2_PRE_SUBMIT_ATTACHMENT_REVALIDATION_NOT_PROVEN")
    if support.get("post_send_readiness_attachment_revalidation") is not True:
        raise RuntimeError("PR9_2_POST_SEND_READINESS_ATTACHMENT_REVALIDATION_NOT_PROVEN")
    if (
        support.get("protected_submit_primitive")
        != "PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK"
    ):
        raise RuntimeError("PR9_2_PROTECTED_SUBMIT_PRIMITIVE_NOT_PROVEN")
    if support.get("rich_input_raw_cdp_input_submit_disabled") is not True:
        raise RuntimeError("PR9_2_RAW_CDP_INPUT_SUBMIT_NOT_DISABLED")
    if support.get("rich_input_enter_fallback_enabled") is not False:
        raise RuntimeError("PR9_2_RICH_INPUT_ENTER_FALLBACK_MUST_BE_DISABLED")
    if support.get("late_protected_submit_execution_prevented_by_page_deadline") is not True:
        raise RuntimeError("PR9_2_LATE_PROTECTED_SUBMIT_GUARD_NOT_PROVEN")
    if support.get("atomic_attachment_validation_and_submit") is not True:
        raise RuntimeError("PR9_2_ATOMIC_ATTACHMENT_SUBMIT_NOT_PROVEN")
    if support.get("post_click_debugger_ack_required") is not False:
        raise RuntimeError("PR9_2_POST_CLICK_DEBUGGER_ACK_MUST_NOT_BE_REQUIRED")
    if support.get("protected_submit_outcome_proof") != "NETWORK_REQUEST_OBSERVATION":
        raise RuntimeError("PR9_2_PROTECTED_SUBMIT_OUTCOME_PROOF_NOT_PROVEN")
    reserve_ms = support.get("submit_observation_reserve_ms")
    if (
        not isinstance(reserve_ms, int)
        or isinstance(reserve_ms, bool)
        or reserve_ms < 10_000
    ):
        raise RuntimeError("PR9_2_SUBMIT_OBSERVATION_RESERVE_NOT_PROVEN")
    if support.get("stale_attachment_cleanup_requires_session_runtime_identity") is not True:
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_SESSION_IDENTITY_NOT_PROVEN")
    if support.get("stale_attachment_identity_mismatch_closes_tab") is not False:
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_IDENTITY_MISMATCH_MUST_NOT_CLOSE_TAB")
    if support.get("stale_attachment_identity_mismatch_fails_closed") is not True:
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_IDENTITY_MISMATCH_FAIL_CLOSED_NOT_PROVEN")
    if support.get("stale_attachment_unproven_identity_fails_closed") is not True:
        raise RuntimeError("PR9_2_STALE_ATTACHMENT_UNPROVEN_IDENTITY_FAIL_CLOSED_NOT_PROVEN")
    if support.get("automatic_write_retry") is not False:
        raise RuntimeError("PR9_2_AUTOMATIC_WRITE_RETRY_MUST_BE_FALSE")
    if support.get("fallback_transport") is not None:
        raise RuntimeError("PR9_2_FALLBACK_TRANSPORT_MUST_BE_NONE")
    if support.get("write_performed") is not False:
        raise RuntimeError("PR9_2_SUPPORT_PROBE_MUST_BE_NO_WRITE")


def _events_of_type(events: Iterable[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [
        dict(event)
        for event in events
        if isinstance(event, dict) and event.get("type") == event_type
    ]


def _validate_execution(
    *,
    label: str,
    execution: Any,
    events: list[dict[str, Any]],
    expected_text: str,
    expected_attachment_count: int,
    attachment_evidence_kind: str,
    expected_conversation_id: str | None = None,
) -> dict[str, Any]:
    response = execution.response
    actual_text = response.text.strip()
    if actual_text != expected_text:
        raise RuntimeError(
            f"PR9_2_{label}:ATTACHMENT_DEPENDENT_RESPONSE_MISMATCH "
            f"expected={expected_text!r} actual={actual_text!r}"
        )

    write_events = _events_of_type(events, "browser_native_write_completed")
    readback_events = _events_of_type(events, "browser_native_readback_completed")
    if len(write_events) != 1:
        raise RuntimeError(f"PR9_2_{label}:WRITE_EVENT_COUNT:{len(write_events)}")
    if len(readback_events) != 1:
        raise RuntimeError(f"PR9_2_{label}:READBACK_EVENT_COUNT:{len(readback_events)}")
    if write_events[0].get("attachment_count") != expected_attachment_count:
        raise RuntimeError(f"PR9_2_{label}:WRITE_ATTACHMENT_COUNT_MISMATCH")
    if readback_events[0].get("attachment_count") != expected_attachment_count:
        raise RuntimeError(f"PR9_2_{label}:READBACK_ATTACHMENT_COUNT_MISMATCH")

    observation = execution.observation
    if getattr(observation, "write_event_observed", None) is not True:
        raise RuntimeError(f"PR9_2_{label}:WRITE_OBSERVATION_NOT_PROVEN")

    provenance = execution.provenance
    if not isinstance(provenance, ProductExecutionProvenance):
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_MISSING")
    completion = provenance.completion
    if (
        completion.completed is not True
        or completion.source is not CompletionSource.CANONICAL_READBACK
        or completion.canonical_completion_proven is not True
    ):
        raise RuntimeError(f"PR9_2_{label}:CANONICAL_FINALITY_NOT_PROVEN")

    conversation_id = response.conversation.conversation_id
    message_id = response.conversation.message_id
    if provenance.identity.conversation_id != conversation_id:
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_CONVERSATION_ID_MISMATCH")
    if provenance.identity.message_id != message_id:
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_MESSAGE_ID_MISMATCH")
    if expected_conversation_id is not None and conversation_id != expected_conversation_id:
        raise RuntimeError(f"PR9_2_{label}:CONTINUATION_CONVERSATION_ID_MISMATCH")

    return {
        "label": label,
        "response": actual_text,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "observed_model": provenance.identity.observed_model,
        "attachment_count": expected_attachment_count,
        "attachment_dependent_evidence": True,
        "attachment_evidence_kind": attachment_evidence_kind,
        "write_event_count": len(write_events),
        "readback_event_count": len(readback_events),
        "browser_authority_lease_id": write_events[0].get(
            "browser_authority_lease_id"
        ),
        "canonical_completion_proven": True,
        "completion_source": completion.source.value,
    }


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", checksum)
    )


def _build_color_band_png() -> bytes:
    """Create a deterministic BLUE | RED | GREEN PNG without external deps."""

    width = 96
    height = 48
    blue = bytes((0, 0, 255))
    red = bytes((255, 0, 0))
    green = bytes((0, 255, 0))
    row = blue * 32 + red * 32 + green * 32
    raw = b"".join(b"\x00" + row for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _write_fixtures(root: Path) -> tuple[Path, Path, Path]:
    image = root / "pr9_2_attachment_evidence.png"
    text_file = root / "pr9_2_file_evidence.txt"
    continuation_file = root / "pr9_2_continuation_evidence.txt"
    image.write_bytes(_build_color_band_png())
    text_file.write_text(
        "PR9.2 general-file attachment evidence fixture.\n"
        f"EVIDENCE: {_FILE_REPLY}\n",
        encoding="utf-8",
    )
    continuation_file.write_text(
        "PR9.2 continuation attachment evidence fixture.\n"
        f"EVIDENCE: {_CONTINUATION_REPLY}\n",
        encoding="utf-8",
    )
    return image, text_file, continuation_file


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputLiveProvider()
    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    support = provider.rich_input_support(timeout=min(10.0, timeout))
    _validate_support(support)

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR9.2",
        "schema": SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "support": support,
        "turns": [],
    }

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-live-") as temp_dir:
        image_path, file_path, continuation_path = _write_fixtures(Path(temp_dir))

        image_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        image_execution = runtime.send_text_observed(
            _IMAGE_PROMPT,
            media=[image_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=image_events.append,
        )
        report["write_completions"] += 1
        image_turn = _validate_execution(
            label="IMAGE_NEW_CHAT",
            execution=image_execution,
            events=image_events,
            expected_text=_IMAGE_REPLY,
            expected_attachment_count=1,
            attachment_evidence_kind="image_color_band_order",
        )
        report["turns"].append(image_turn)

        file_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        file_execution = runtime.send_text_observed(
            _FILE_PROMPT,
            media=[file_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=file_events.append,
        )
        report["write_completions"] += 1
        file_turn = _validate_execution(
            label="FILE_NEW_CHAT",
            execution=file_execution,
            events=file_events,
            expected_text=_FILE_REPLY,
            expected_attachment_count=1,
            attachment_evidence_kind="general_file_hidden_marker",
        )
        report["turns"].append(file_turn)

        continuation_events: list[dict[str, Any]] = []
        continuation_id = image_execution.response.conversation.conversation_id
        report["write_attempts"] += 1
        continuation_execution = runtime.send_text_observed(
            _CONTINUATION_PROMPT,
            conversation=image_execution.response.conversation,
            media=[continuation_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=continuation_events.append,
        )
        report["write_completions"] += 1
        continuation_turn = _validate_execution(
            label="MULTIMODAL_CONTINUATION",
            execution=continuation_execution,
            events=continuation_events,
            expected_text=_CONTINUATION_REPLY,
            expected_attachment_count=1,
            attachment_evidence_kind="continuation_file_hidden_marker",
            expected_conversation_id=continuation_id,
        )
        report["turns"].append(continuation_turn)

    if report["write_attempts"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "attachment_dependent_response_after_every_write": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "recovery_before_attachment_staging": True,
        "stale_attachment_failure_fence": True,
        "stale_attachment_fence_persistent_across_worker_restart": True,
        "single_total_turn_deadline": True,
        "pre_submit_deadline_guard": True,
        "deadline_bounded_post_write_cleanup": True,
        "post_write_fence_retained_until_next_prewrite": True,
        "enter_key_release_affects_submitted_outcome": False,
        "mouse_to_enter_fallback_after_release_attempt": False,
        "mouse_release_outcome_ambiguity_fails_closed": True,
        "stale_attachment_cleanup_proof": "RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED",
        "attachment_count_evidence": "PAGE_OWNED_COMPOSER_ATTACHMENT_STATE",
        "attachment_evidence_stable_poll_count": 2,
        "pre_submit_attachment_revalidation": True,
        "post_send_readiness_attachment_revalidation": True,
        "atomic_attachment_validation_and_submit": True,
        "protected_submit_primitive": "PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK",
        "post_click_debugger_ack_required": False,
        "protected_submit_outcome_proof": "NETWORK_REQUEST_OBSERVATION",
        "stale_attachment_cleanup_requires_session_runtime_identity": True,
        "stale_attachment_identity_mismatch_closes_tab": False,
        "stale_attachment_identity_mismatch_fails_closed": True,
        "stale_attachment_unproven_identity_fails_closed": True,
        "rich_input_raw_cdp_input_submit_disabled": True,
        "rich_input_enter_fallback_enabled": False,
        "late_protected_submit_execution_prevented_by_page_deadline": True,
        "native_messaging_attachment_bytes": False,
        "official_page_owned_upload_and_write": True,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 bounded authenticated rich-input production live gate"
    )
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required; this gate performs exactly three product writes"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    report = run_live_gate(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
