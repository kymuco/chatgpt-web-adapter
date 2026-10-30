from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema18_pr9_2 as _v18


SCHEMA = 19
PRODUCT_WRITE_BUDGET = _v18.PRODUCT_WRITE_BUDGET
_EXPECTED_IDENTITY_AUTHORITY = "NETWORK_REQUEST_BOUND_STREAM_HANDOFF"


class ProductRichInputSchema19LiveProvider(_v18.ProductRichInputSchema18LiveProvider):
    """PR9.2 schema-19 request-bound identity probe on frozen schema 18."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Thirteenth characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA19_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA19_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["new_chat_conversation_identity_authority"] = response.get(
            "newChatConversationIdentityAuthority"
        )
        support["response_body_conversation_identity_request_bound"] = response.get(
            "responseBodyConversationIdentityRequestBound"
        )
        support["route_conversation_identity_authoritative"] = response.get(
            "routeConversationIdentityAuthoritative"
        )
        support["manual_route_navigation_can_satisfy_new_chat_identity"] = response.get(
            "manualRouteNavigationCanSatisfyNewChatIdentity"
        )
        support["causal_conversation_identity_read_deadline_bounded"] = response.get(
            "causalConversationIdentityReadDeadlineBounded"
        )
        support["causal_conversation_identity_rpc_return_reserve_ms"] = response.get(
            "causalConversationIdentityRpcReturnReserveMs"
        )
        support[
            "missing_request_bound_conversation_identity_signals_committed_readback_incomplete"
        ] = response.get(
            "missingRequestBoundConversationIdentitySignalsCommittedReadbackIncomplete"
        )
        support["automatic_write_retry_after_causal_identity_failure"] = response.get(
            "automaticWriteRetryAfterCausalIdentityFailure"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA19_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v18.SCHEMA
    _v18._validate_support(legacy)

    if support.get("new_chat_conversation_identity_authority") != _EXPECTED_IDENTITY_AUTHORITY:
        raise RuntimeError("PR9_2_REQUEST_BOUND_CONVERSATION_ID_AUTHORITY_NOT_PROVEN")
    if support.get("response_body_conversation_identity_request_bound") is not True:
        raise RuntimeError("PR9_2_RESPONSE_BODY_CONVERSATION_ID_REQUEST_BINDING_NOT_PROVEN")
    if support.get("route_conversation_identity_authoritative") is not False:
        raise RuntimeError("PR9_2_ROUTE_CONVERSATION_ID_AUTHORITY_NOT_DENIED")
    if support.get("manual_route_navigation_can_satisfy_new_chat_identity") is not False:
        raise RuntimeError("PR9_2_MANUAL_ROUTE_IDENTITY_SATISFACTION_NOT_DENIED")
    if support.get("causal_conversation_identity_read_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_CAUSAL_CONVERSATION_ID_READ_BOUND_NOT_PROVEN")
    reserve = support.get("causal_conversation_identity_rpc_return_reserve_ms")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve <= 0:
        raise RuntimeError("PR9_2_CAUSAL_CONVERSATION_ID_RPC_RESERVE_NOT_PROVEN")
    if (
        support.get(
            "missing_request_bound_conversation_identity_signals_committed_readback_incomplete"
        )
        is not True
    ):
        raise RuntimeError("PR9_2_MISSING_REQUEST_BOUND_IDENTITY_CLASSIFICATION_NOT_PROVEN")
    if support.get("automatic_write_retry_after_causal_identity_failure") is not False:
        raise RuntimeError("PR9_2_CAUSAL_IDENTITY_FAILURE_AUTOMATIC_RETRY_NOT_DENIED")
