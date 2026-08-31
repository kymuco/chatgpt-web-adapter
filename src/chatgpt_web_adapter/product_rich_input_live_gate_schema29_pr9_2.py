from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any
import uuid

from .client import ChatGPTWebClient
from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema28_pr9_2 as _v28
from .product_runtime import assemble_product_runtime


SCHEMA = 29
PRODUCT_WRITE_BUDGET = _v28.PRODUCT_WRITE_BUDGET
_SCHEMA20_PLUS_IDENTITY_AUTHORITY = "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF"
_SCHEMA20_REQUEST_CORRELATION = "PAGE_SIDE_ARMED_SINGLE_CONVERSATION_POST"
_EXPECTED_REQUEST_CORRELATION = "VALIDATED_CLICK_REQUEST_BODY_USER_MESSAGE_IDENTITY"


class ProductRichInputSchema29LiveProvider(_v28.ProductRichInputSchema28LiveProvider):
    """PR9.2 schema-29 request-body-bound rich-submit identity probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

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
            raise RuntimeError("PR9_2_SCHEMA29_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA29_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        fields = {
            "new_chat_conversation_identity_authority": "newChatConversationIdentityAuthority",
            "request_bound_protocol_conversation_id_authority": "requestBoundProtocolConversationIdAuthority",
            "request_bound_protocol_conversation_id_consensus_required": "requestBoundProtocolConversationIdConsensusRequired",
            "top_level_conversation_id_authority": "topLevelConversationIdAuthority",
            "root_add_value_conversation_id_authority": "rootAddValueConversationIdAuthority",
            "unrecognized_nested_conversation_id_can_satisfy_identity": "unrecognizedNestedConversationIdCanSatisfyIdentity",
            "stream_handoff_required_for_causal_conversation_identity": "streamHandoffRequiredForCausalConversationIdentity",
            "conflicting_request_bound_conversation_ids_fail_closed": "conflictingRequestBoundConversationIdsFailClosed",
            "protected_submit_request_correlation": "protectedSubmitRequestCorrelation",
            "validated_click_request_body_correlation": "validatedClickRequestBodyCorrelation",
            "request_post_data_required_for_protected_submit_correlation": "requestPostDataRequiredForProtectedSubmitCorrelation",
            "request_post_data_fallback_supported": "requestPostDataFallbackSupported",
            "request_post_data_fallback_exact_request_bound": "requestPostDataFallbackExactRequestBound",
            "unresolved_request_body_fails_closed": "unresolvedRequestBodyFailsClosed",
            "exact_user_text_required_for_protected_submit_correlation": "exactUserTextRequiredForProtectedSubmitCorrelation",
            "request_message_id_required_for_protected_submit_correlation": "requestMessageIdRequiredForProtectedSubmitCorrelation",
            "request_attachment_count_required_for_protected_submit_correlation": "requestAttachmentCountRequiredForProtectedSubmitCorrelation",
            "continuation_conversation_id_required_for_protected_submit_correlation": "continuationConversationIdRequiredForProtectedSubmitCorrelation",
            "new_chat_conversation_id_must_be_absent_for_protected_submit_correlation": "newChatConversationIdMustBeAbsentForProtectedSubmitCorrelation",
            "additional_service_post_arm_requests_allowed": "additionalServicePostArmRequestsAllowed",
            "additional_post_arm_conversation_requests_authoritative": "additionalPostArmConversationRequestsAuthoritative",
            "duplicate_same_logical_message_request_allowed": "duplicateSameLogicalMessageRequestAllowed",
            "distinct_post_arm_user_messages_fail_closed": "distinctPostArmUserMessagesFailClosed",
            "has_user_gesture_authoritative": "hasUserGestureAuthoritative",
            "exactly_one_post_arm_conversation_request_required": "exactlyOnePostArmConversationRequestRequired",
            "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete": "ambiguousPostArmConversationRequestsSignalCommittedReadbackIncomplete",
            "submit_correlation_failure_diagnostics_available": "submitCorrelationFailureDiagnosticsAvailable",
            "automatic_write_retry_after_submit_correlation_failure": "automaticWriteRetryAfterSubmitCorrelationFailure",
        }
        for key, response_key in fields.items():
            support[key] = response.get(response_key)
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA29_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Preserve the complete reviewed schema-28-and-earlier contract while
    # reconstructing schema 20's historical final correlation claims for the
    # inherited validator. Schema 29 then proves its stronger replacement.
    legacy = dict(support)
    legacy["schema"] = _v28.SCHEMA
    legacy["new_chat_conversation_identity_authority"] = (
        _SCHEMA20_PLUS_IDENTITY_AUTHORITY
    )
    legacy["protected_submit_request_correlation"] = _SCHEMA20_REQUEST_CORRELATION
    legacy["exactly_one_post_arm_conversation_request_required"] = True
    legacy[
        "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete"
    ] = True
    _v28._validate_support(legacy)

    if support.get("new_chat_conversation_identity_authority") != (
        "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS"
    ):
        raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_AUTHORITY_NOT_PROVEN")
    for key, error in (
        ("request_bound_protocol_conversation_id_authority", "PR9_2_SCHEMA29_PROTOCOL_ID_AUTHORITY_NOT_PROVEN"),
        ("request_bound_protocol_conversation_id_consensus_required", "PR9_2_SCHEMA29_PROTOCOL_ID_CONSENSUS_NOT_PROVEN"),
        ("top_level_conversation_id_authority", "PR9_2_SCHEMA29_TOP_LEVEL_ID_AUTHORITY_NOT_PROVEN"),
        ("root_add_value_conversation_id_authority", "PR9_2_SCHEMA29_ROOT_ADD_VALUE_ID_AUTHORITY_NOT_PROVEN"),
        ("conflicting_request_bound_conversation_ids_fail_closed", "PR9_2_SCHEMA29_CONFLICTING_REQUEST_BOUND_IDS_NOT_FAIL_CLOSED"),
    ):
        if support.get(key) is not True:
            raise RuntimeError(error)
    if support.get("unrecognized_nested_conversation_id_can_satisfy_identity") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_UNRECOGNIZED_NESTED_IDENTITY_AUTHORITY_REGRESSED")
    if support.get("stream_handoff_required_for_causal_conversation_identity") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_STREAM_HANDOFF_REQUIREMENT_NOT_REMOVED")
    if support.get("route_conversation_identity_authoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_ROUTE_IDENTITY_AUTHORITY_REGRESSED")

    if support.get("protected_submit_request_correlation") != _EXPECTED_REQUEST_CORRELATION:
        raise RuntimeError("PR9_2_SCHEMA29_REQUEST_BODY_CORRELATION_NOT_PROVEN")
    for key, error in (
        ("validated_click_request_body_correlation", "PR9_2_SCHEMA29_VALIDATED_CLICK_BODY_BINDING_NOT_PROVEN"),
        ("request_post_data_required_for_protected_submit_correlation", "PR9_2_SCHEMA29_REQUEST_POST_DATA_NOT_REQUIRED"),
        ("request_post_data_fallback_supported", "PR9_2_SCHEMA29_REQUEST_POST_DATA_FALLBACK_NOT_SUPPORTED"),
        ("request_post_data_fallback_exact_request_bound", "PR9_2_SCHEMA29_REQUEST_POST_DATA_FALLBACK_NOT_REQUEST_BOUND"),
        ("unresolved_request_body_fails_closed", "PR9_2_SCHEMA29_UNRESOLVED_REQUEST_BODY_NOT_FAIL_CLOSED"),
        ("exact_user_text_required_for_protected_submit_correlation", "PR9_2_SCHEMA29_EXACT_USER_TEXT_NOT_REQUIRED"),
        ("request_message_id_required_for_protected_submit_correlation", "PR9_2_SCHEMA29_MESSAGE_ID_NOT_REQUIRED"),
        ("request_attachment_count_required_for_protected_submit_correlation", "PR9_2_SCHEMA29_ATTACHMENT_COUNT_NOT_REQUIRED"),
        ("continuation_conversation_id_required_for_protected_submit_correlation", "PR9_2_SCHEMA29_CONTINUATION_ID_NOT_REQUIRED"),
        ("new_chat_conversation_id_must_be_absent_for_protected_submit_correlation", "PR9_2_SCHEMA29_NEW_CHAT_ID_ABSENCE_NOT_REQUIRED"),
        ("additional_service_post_arm_requests_allowed", "PR9_2_SCHEMA29_SERVICE_POST_POLICY_NOT_PROVEN"),
        ("duplicate_same_logical_message_request_allowed", "PR9_2_SCHEMA29_LOGICAL_DUPLICATE_POLICY_NOT_PROVEN"),
        ("distinct_post_arm_user_messages_fail_closed", "PR9_2_SCHEMA29_CONCURRENT_USER_TURN_NOT_FAIL_CLOSED"),
        ("submit_correlation_failure_diagnostics_available", "PR9_2_SCHEMA29_SUBMIT_CORRELATION_DIAGNOSTICS_NOT_AVAILABLE"),
    ):
        if support.get(key) is not True:
            raise RuntimeError(error)

    if support.get("additional_post_arm_conversation_requests_authoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_ADDITIONAL_POST_ARM_REQUEST_AUTHORITY_REGRESSED")
    if support.get("has_user_gesture_authoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_USER_GESTURE_REMAINS_IDENTITY_AUTHORITY")
    if support.get("exactly_one_post_arm_conversation_request_required") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_POST_ARM_MULTIPLICITY_RULE_NOT_REMOVED")
    if (
        support.get(
            "ambiguous_post_arm_conversation_requests_signal_committed_readback_incomplete"
        )
        is not False
    ):
        raise RuntimeError("PR9_2_SCHEMA29_RAW_POST_ARM_MULTIPLICITY_STILL_AUTHORITATIVE")
    if support.get("automatic_write_retry_after_submit_correlation_failure") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_SUBMIT_CORRELATION_RETRY_REGRESSED")
    if support.get("automatic_write_retry_after_causal_identity_failure") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_RETRY_REGRESSED")


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema29LiveProvider()
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

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema29-live-") as temp_dir:
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
        raise RuntimeError("PR9_2_SCHEMA29_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA29_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "attachment_dependent_response_after_every_write": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "schema_28_and_prior_safety_contract_preserved": True,
        "validated_click_request_body_correlation": True,
        "request_post_data_fallback_supported": True,
        "exact_user_text_request_binding": True,
        "request_message_id_binding": True,
        "request_attachment_count_binding": True,
        "continuation_conversation_id_binding": True,
        "additional_service_post_arm_requests_allowed": True,
        "distinct_post_arm_user_messages_fail_closed": True,
        "raw_post_arm_multiplicity_non_authoritative": True,
        "has_user_gesture_non_authoritative": True,
        "request_bound_protocol_conversation_id_consensus": True,
        "top_level_conversation_id_authority": True,
        "root_add_value_conversation_id_authority": True,
        "stream_handoff_required_for_causal_conversation_identity": False,
        "unrecognized_nested_conversation_id_can_satisfy_identity": False,
        "conflicting_request_bound_conversation_ids_fail_closed": True,
        "route_conversation_identity_authoritative": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 schema-29 request-body-bound rich-input live gate"
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
