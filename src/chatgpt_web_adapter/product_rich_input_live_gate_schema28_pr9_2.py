from __future__ import annotations

from typing import Any
import uuid

from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema27_pr9_2 as _v27


SCHEMA = 28
PRODUCT_WRITE_BUDGET = _v27.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema28LiveProvider(_v27.ProductRichInputSchema27LiveProvider):
    """PR9.2 schema-28 request-bound stream-handoff parser support probe."""

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
            raise RuntimeError("PR9_2_SCHEMA28_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA28_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["causal_stream_handoff_json_parsed_before_type_filter"] = response.get(
            "causalStreamHandoffJsonParsedBeforeTypeFilter"
        )
        support["causal_stream_handoff_json_whitespace_invariant"] = response.get(
            "causalStreamHandoffJsonWhitespaceInvariant"
        )
        support["causal_stream_handoff_base64_body_decoding_supported"] = response.get(
            "causalStreamHandoffBase64BodyDecodingSupported"
        )
        support["conflicting_stream_handoff_conversation_ids_fail_closed"] = response.get(
            "conflictingStreamHandoffConversationIdsFailClosed"
        )
        support["prior_stream_metadata_observer_side_effects_preserved"] = response.get(
            "priorStreamMetadataObserverSideEffectsPreserved"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA28_RICH_INPUT_SUPPORT_NOT_PROVEN")

    legacy = dict(support)
    legacy["schema"] = _v27.SCHEMA
    _v27._validate_support(legacy)

    if support.get("causal_stream_handoff_json_parsed_before_type_filter") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_JSON_FIRST_STREAM_HANDOFF_PARSE_NOT_PROVEN")
    if support.get("causal_stream_handoff_json_whitespace_invariant") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_STREAM_HANDOFF_WHITESPACE_INVARIANCE_NOT_PROVEN")
    if support.get("causal_stream_handoff_base64_body_decoding_supported") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_BASE64_RESPONSE_BODY_DECODING_NOT_PROVEN")
    if support.get("conflicting_stream_handoff_conversation_ids_fail_closed") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_CONFLICTING_STREAM_HANDOFF_IDS_NOT_FAIL_CLOSED")
    if support.get("prior_stream_metadata_observer_side_effects_preserved") is not True:
        raise RuntimeError("PR9_2_SCHEMA28_PRIOR_METADATA_OBSERVER_NOT_PRESERVED")
    if support.get("route_conversation_identity_authoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_ROUTE_IDENTITY_AUTHORITY_REGRESSED")
    if support.get("automatic_write_retry_after_causal_identity_failure") is not False:
        raise RuntimeError("PR9_2_SCHEMA28_IDENTITY_RETRY_REGRESSED")
