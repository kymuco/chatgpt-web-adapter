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


class ProductRichInputSchema29LiveProvider(_v28.ProductRichInputSchema28LiveProvider):
    """PR9.2 schema-29 exact-request protocol conversation-id consensus probe."""

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

        support["new_chat_conversation_identity_authority"] = response.get(
            "newChatConversationIdentityAuthority"
        )
        support["request_bound_protocol_conversation_id_authority"] = response.get(
            "requestBoundProtocolConversationIdAuthority"
        )
        support["request_bound_protocol_conversation_id_consensus_required"] = response.get(
            "requestBoundProtocolConversationIdConsensusRequired"
        )
        support["top_level_conversation_id_authority"] = response.get(
            "topLevelConversationIdAuthority"
        )
        support["root_add_value_conversation_id_authority"] = response.get(
            "rootAddValueConversationIdAuthority"
        )
        support["unrecognized_nested_conversation_id_can_satisfy_identity"] = response.get(
            "unrecognizedNestedConversationIdCanSatisfyIdentity"
        )
        support["stream_handoff_required_for_causal_conversation_identity"] = response.get(
            "streamHandoffRequiredForCausalConversationIdentity"
        )
        support["conflicting_request_bound_conversation_ids_fail_closed"] = response.get(
            "conflictingRequestBoundConversationIdsFailClosed"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA29_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Schema 29 supersedes the final identity-authority name only. The immutable
    # schema-28 validator chain reaches schema 20 before schema 20 itself
    # reconstructs schema 19's NETWORK_REQUEST_BOUND_STREAM_HANDOFF view, so the
    # historical input to schema 28 must retain the schema-20+ protected-submit-
    # bound authority rather than prematurely downgrading to schema 19 here.
    legacy = dict(support)
    legacy["schema"] = _v28.SCHEMA
    legacy["new_chat_conversation_identity_authority"] = (
        _SCHEMA20_PLUS_IDENTITY_AUTHORITY
    )
    _v28._validate_support(legacy)

    if support.get("new_chat_conversation_identity_authority") != (
        "NETWORK_REQUEST_BOUND_PROTOCOL_CONVERSATION_ID_CONSENSUS"
    ):
        raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_AUTHORITY_NOT_PROVEN")
    if support.get("request_bound_protocol_conversation_id_authority") is not True:
        raise RuntimeError("PR9_2_SCHEMA29_PROTOCOL_ID_AUTHORITY_NOT_PROVEN")
    if support.get("request_bound_protocol_conversation_id_consensus_required") is not True:
        raise RuntimeError("PR9_2_SCHEMA29_PROTOCOL_ID_CONSENSUS_NOT_PROVEN")
    if support.get("top_level_conversation_id_authority") is not True:
        raise RuntimeError("PR9_2_SCHEMA29_TOP_LEVEL_ID_AUTHORITY_NOT_PROVEN")
    if support.get("root_add_value_conversation_id_authority") is not True:
        raise RuntimeError("PR9_2_SCHEMA29_ROOT_ADD_VALUE_ID_AUTHORITY_NOT_PROVEN")
    if support.get("unrecognized_nested_conversation_id_can_satisfy_identity") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_UNRECOGNIZED_NESTED_IDENTITY_AUTHORITY_REGRESSED")
    if support.get("stream_handoff_required_for_causal_conversation_identity") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_STREAM_HANDOFF_REQUIREMENT_NOT_REMOVED")
    if support.get("conflicting_request_bound_conversation_ids_fail_closed") is not True:
        raise RuntimeError("PR9_2_SCHEMA29_CONFLICTING_REQUEST_BOUND_IDS_NOT_FAIL_CLOSED")
    if support.get("route_conversation_identity_authoritative") is not False:
        raise RuntimeError("PR9_2_SCHEMA29_ROUTE_IDENTITY_AUTHORITY_REGRESSED")
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
        description="PR9.2 schema-29 exact-request protocol identity rich-input live gate"
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
