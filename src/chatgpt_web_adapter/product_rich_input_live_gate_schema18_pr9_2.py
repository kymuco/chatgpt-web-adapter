from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any
import uuid

from .client import ChatGPTWebClient
from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema17_pr9_2 as _v17
from .product_runtime import assemble_product_runtime


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

        support["new_chat_conversation_identity_required_before_success"] = response.get(
            "newChatConversationIdentityRequiredBeforeSuccess"
        )
        support["post_write_conversation_identity_resolution_deadline_bounded"] = response.get(
            "postWriteConversationIdentityResolutionDeadlineBounded"
        )
        support["post_write_conversation_identity_dedicated_reserve_ms"] = response.get(
            "postWriteConversationIdentityDedicatedReserveMs"
        )
        support["missing_conversation_identity_can_return_transport_success"] = response.get(
            "missingConversationIdentityCanReturnTransportSuccess"
        )
        support["unresolved_conversation_identity_signals_committed_readback_incomplete"] = response.get(
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

    if support.get("new_chat_conversation_identity_required_before_success") is not True:
        raise RuntimeError("PR9_2_NEW_CHAT_CONVERSATION_ID_SUCCESS_AUTHORITY_NOT_PROVEN")
    if support.get("post_write_conversation_identity_resolution_deadline_bounded") is not True:
        raise RuntimeError("PR9_2_POST_WRITE_CONVERSATION_ID_RESOLUTION_BOUND_NOT_PROVEN")
    reserve = support.get("post_write_conversation_identity_dedicated_reserve_ms")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve <= 0:
        raise RuntimeError("PR9_2_POST_WRITE_CONVERSATION_ID_RESERVE_NOT_PROVEN")
    if support.get("missing_conversation_identity_can_return_transport_success") is not False:
        raise RuntimeError("PR9_2_MISSING_CONVERSATION_ID_TRANSPORT_SUCCESS_NOT_DENIED")
    if support.get("unresolved_conversation_identity_signals_committed_readback_incomplete") is not True:
        raise RuntimeError("PR9_2_COMMITTED_IDENTITY_FAILURE_CLASSIFICATION_NOT_PROVEN")
    if support.get("automatic_write_retry_after_identity_failure") is not False:
        raise RuntimeError("PR9_2_IDENTITY_FAILURE_AUTOMATIC_RETRY_NOT_DENIED")


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema18LiveProvider()
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

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema18-live-") as temp_dir:
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
        raise RuntimeError("PR9_2_SCHEMA18_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA18_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "attachment_dependent_response_after_every_write": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "schema_17_safety_contract_preserved": True,
        "new_chat_conversation_identity_required_before_success": True,
        "post_write_conversation_identity_resolution_deadline_bounded": True,
        "post_write_conversation_identity_dedicated_reserve_ms": support[
            "post_write_conversation_identity_dedicated_reserve_ms"
        ],
        "missing_conversation_identity_can_return_transport_success": False,
        "unresolved_conversation_identity_signals_committed_readback_incomplete": True,
        "automatic_write_retry_after_identity_failure": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 schema-18 conversation-identity-safe rich-input live gate"
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
