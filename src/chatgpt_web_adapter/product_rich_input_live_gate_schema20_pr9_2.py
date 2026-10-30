from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema19_pr9_2 as _v19


SCHEMA = 20
PRODUCT_WRITE_BUDGET = _v19.PRODUCT_WRITE_BUDGET
_EXPECTED_IDENTITY_AUTHORITY = "PROTECTED_SUBMIT_BOUND_REQUEST_STREAM_HANDOFF"
_EXPECTED_REQUEST_CORRELATION = "PAGE_SIDE_ARMED_SINGLE_CONVERSATION_POST"
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
        support["protected_submit_request_armed_by_page_side_marker"] = response.get(
            "protectedSubmitRequestArmedByPageSideMarker"
        )
        support["page_side_arm_marker_and_protected_click_same_task"] = response.get(
            "pageSideArmMarkerAndProtectedClickSameTask"
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
    if support.get("protected_submit_request_armed_by_page_side_marker") is not True:
        raise RuntimeError("PR9_2_PAGE_SIDE_PROTECTED_SUBMIT_ARM_NOT_PROVEN")
    if support.get("page_side_arm_marker_and_protected_click_same_task") is not True:
        raise RuntimeError("PR9_2_PAGE_SIDE_ARM_CLICK_ATOMICITY_NOT_PROVEN")
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
