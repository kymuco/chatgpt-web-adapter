from __future__ import annotations

import uuid
from typing import Any

from . import product_rich_input_live_gate_schema17_pr9_2 as _v17


SCHEMA = 18
PRODUCT_WRITE_BUDGET = _v17.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema18LiveProvider(_v17.ProductRichInputSchema17LiveProvider):
    """PR9.2 schema-18 identity-authority probe on the frozen schema-17 provider."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Frozen earlier gates deliberately cannot interpret schema-18 fields.
        # This twelfth characterization-only RPC carries neither text nor paths.
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
            raise RuntimeError("PR9_2_SCHEMA18_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA18_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["new_chat_conversation_identity_required_before_success"] = (
            response.get("newChatConversationIdentityRequiredBeforeSuccess")
        )
        support["post_write_conversation_identity_resolution_deadline_bounded"] = (
            response.get("postWriteConversationIdentityResolutionDeadlineBounded")
        )
        support["post_write_conversation_identity_dedicated_reserve_ms"] = response.get(
            "postWriteConversationIdentityDedicatedReserveMs"
        )
        support["missing_conversation_identity_can_return_transport_success"] = (
            response.get("missingConversationIdentityCanReturnTransportSuccess")
        )
        support[
            "unresolved_conversation_identity_signals_committed_readback_incomplete"
        ] = response.get(
            "unresolvedConversationIdentitySignalsCommittedReadbackIncomplete"
        )
        support["automatic_write_retry_after_identity_failure"] = response.get(
            "automaticWriteRetryAfterIdentityFailure"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA18_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v17.SCHEMA
    _v17._validate_support(legacy)

    if (
        support.get("new_chat_conversation_identity_required_before_success")
        is not True
    ):
        raise RuntimeError(
            "PR9_2_NEW_CHAT_CONVERSATION_ID_SUCCESS_AUTHORITY_NOT_PROVEN"
        )
    if (
        support.get("post_write_conversation_identity_resolution_deadline_bounded")
        is not True
    ):
        raise RuntimeError(
            "PR9_2_POST_WRITE_CONVERSATION_ID_RESOLUTION_BOUND_NOT_PROVEN"
        )
    reserve = support.get("post_write_conversation_identity_dedicated_reserve_ms")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve <= 0:
        raise RuntimeError("PR9_2_POST_WRITE_CONVERSATION_ID_RESERVE_NOT_PROVEN")
    if (
        support.get("missing_conversation_identity_can_return_transport_success")
        is not False
    ):
        raise RuntimeError("PR9_2_MISSING_CONVERSATION_ID_TRANSPORT_SUCCESS_NOT_DENIED")
    if (
        support.get(
            "unresolved_conversation_identity_signals_committed_readback_incomplete"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_COMMITTED_IDENTITY_FAILURE_CLASSIFICATION_NOT_PROVEN")
    if support.get("automatic_write_retry_after_identity_failure") is not False:
        raise RuntimeError("PR9_2_IDENTITY_FAILURE_AUTOMATIC_RETRY_NOT_DENIED")
