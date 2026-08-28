from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any
import uuid

from .client import ChatGPTWebClient
from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema19_pr9_2 as _v19
from .product_runtime import assemble_product_runtime


SCHEMA = 20
PRODUCT_WRITE_BUDGET = _v19.PRODUCT_WRITE_BUDGET
_EXPECTED_IDENTITY_AUTHORITY = "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF"
_EXPECTED_REQUEST_CORRELATION = "PROTECTED_SUBMIT_ARMED_SINGLE_CONVERSATION_POST"
_SCHEMA19_IDENTITY_AUTHORITY = "NETWORK_REQUEST_BOUND_STREAM_HANDOFF"


class ProductRichInputSchema20LiveProvider(_v19.ProductRichInputSchema19LiveProvider):
    """PR9.2 schema-20 protected-submit request-correlation probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Fourteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA20_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA20_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["new_chat_conversation_identity_authority"] = response.get(
            "newChatConversationIdentityAuthority"
        )
        support["protected_submit_request_correlation"] = response.get(
            "protectedSubmitRequestCorrelation"
        )
        support["protected_submit_request_armed_at_atomic_dispatch_boundary"] = response.get(
            "protectedSubmitRequestArmedAtAtomicDispatchBoundary"
        )
        support["pre_arm_conversation_requests_authoritative"] = response.get(
            "preArmConversationRequestsAuthoritative"
        )
        support["exactly_one_post_arm_conversation_request_required"] = response.get(
            "exactlyOnePostArmConversationRequestRequired"
        )
        support["user_gesture_post_arm_request_can_satisfy_protected_submit"] = response.get(
            "userGesturePostArmRequestCanSatisfyProtectedSubmit"
        )
        support[
            "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete"
        ] = response.get(
            "ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete"
        )
        support["automatic_write_retry_after_submit_correlation_failure"] = response.get(
            "automaticWriteRetryAfterSubmitCorrelationFailure"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA20_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v19.SCHEMA
    legacy["new_chat_conversation_identity_authority"] = _SCHEMA19_IDENTITY_AUTHORITY
    _v19._validate_support(legacy)

    if support.get("new_chat_conversation_identity_authority") != _EXPECTED_IDENTITY_AUTHORITY:
        raise RuntimeError("PR9_2_SUBMIT_BOUND_CONVERSATION_ID_AUTHORITY_NOT_PROVEN")
    if support.get("protected_submit_request_correlation") != _EXPECTED_REQUEST_CORRELATION:
        raise RuntimeError("PR9_2_PROTECTED_SUBMIT_REQUEST_CORRELATION_NOT_PROVEN")
    if support.get("protected_submit_request_armed_at_atomic_dispatch_boundary") is not True:
        raise RuntimeError("PR9_2_PROTECTED_SUBMIT_ARM_BOUNDARY_NOT_PROVEN")
    if support.get("pre_arm_conversation_requests_authoritative") is not False:
        raise RuntimeError("PR9_2_PRE_ARM_CONVERSATION_REQUEST_AUTHORITY_NOT_DENIED")
    if support.get("exactly_one_post_arm_conversation_request_required") is not True:
        raise RuntimeError("PR9_2_SINGLE_POST_ARM_CONVERSATION_REQUEST_NOT_REQUIRED")
    if support.get("user_gesture_post_arm_request_can_satisfy_protected_submit") is not False:
        raise RuntimeError("PR9_2_USER_GESTURE_REQUEST_AUTHORITY_NOT_DENIED")
    if (
        support.get(
            "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_AMBIGUOUS_POST_ARM_CLASSIFICATION_NOT_PROVEN")
    if support.get("automatic_write_retry_after_submit_correlation_failure") is not False:
        raise RuntimeError("PR9_2_SUBMIT_CORRELATION_AUTOMATIC_RETRY_NOT_DENIED")


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema20LiveProvider()
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

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema20-live-") as temp_dir:
        image_path, file_path, continuation_path = _v7._write_fixtures(Path(temp_dir))

        image_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        image_execution = runtime.send_text_observed(
            _v7._IMAGE_PROMPT,
            media=[image_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=image_events.append,
        )
        report["write_completions"] += 1
        report["turns"].append(
            _v7._validate_execution(
                label="IMAGE_NEW_CHAT",
                execution=image_execution,
                events=image_events,
                expected_text=_v7._IMAGE_REPLY,
                expected_attachment_count=1,
                attachment_evidence_kind="image_color_band_order",
            )
        )

        file_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        file_execution = runtime.send_text_observed(
            _v7._FILE_PROMPT,
            media=[file_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=file_events.append,
        )
        report["write_completions"] += 1
        report["turns"].append(
            _v7._validate_execution(
                label="FILE_NEW_CHAT",
                execution=file_execution,
                events=file_events,
                expected_text=_v7._FILE_REPLY,
                expected_attachment_count=1,
                attachment_evidence_kind="general_file_hidden_marker",
            )
        )

        continuation_events: list[dict[str, Any]] = []
        continuation_id = image_execution.response.conversation.conversation_id
        report["write_attempts"] += 1
        continuation_execution = runtime.send_text_observed(
            _v7._CONTINUATION_PROMPT,
            conversation=image_execution.response.conversation,
            media=[continuation_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=continuation_events.append,
        )
        report["write_completions"] += 1
        report["turns"].append(
            _v7._validate_execution(
                label="MULTIMODAL_CONTINUATION",
                execution=continuation_execution,
                events=continuation_events,
                expected_text=_v7._CONTINUATION_REPLY,
                expected_attachment_count=1,
                attachment_evidence_kind="continuation_file_hidden_marker",
                expected_conversation_id=continuation_id,
            )
        )

    if report["write_attempts"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA20_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA20_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "attachment_dependent_response_after_every_write": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "schema_19_safety_contract_preserved": True,
        "new_chat_conversation_identity_authority": _EXPECTED_IDENTITY_AUTHORITY,
        "protected_submit_request_correlation": _EXPECTED_REQUEST_CORRELATION,
        "pre_arm_conversation_requests_authoritative": False,
        "exactly_one_post_arm_conversation_request_required": True,
        "user_gesture_post_arm_request_can_satisfy_protected_submit": False,
        "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete": True,
        "automatic_write_retry_after_submit_correlation_failure": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 schema-20 protected-submit request-correlation rich-input live gate"
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
