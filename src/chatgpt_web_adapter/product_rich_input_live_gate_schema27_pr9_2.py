from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any
import uuid

from .client import ChatGPTWebClient
from . import product_rich_input_live_gate_pr9_2 as _v7
from . import product_rich_input_live_gate_schema21_pr9_2 as _v21
from . import product_rich_input_live_gate_schema25_pr9_2 as _v25
from . import product_rich_input_live_gate_schema26_pr9_2 as _v26
from .product_runtime import assemble_product_runtime


SCHEMA = 27
PRODUCT_WRITE_BUDGET = _v21.PRODUCT_WRITE_BUDGET


class ProductRichInputSchema27LiveProvider(_v26.ProductRichInputSchema26LiveProvider):
    """PR9.2 schema-27 bidirectional indexed-removal ambiguity support probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        support = super().rich_input_support(timeout=timeout)

        # Twenty-first characterization-only RPC: no text and no attachment paths.
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
            raise RuntimeError("PR9_2_SCHEMA27_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_SCHEMA27_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )

        support["indexed_removal_ambiguity_bidirectional_fail_closed"] = response.get(
            "indexedRemovalAmbiguityBidirectionalFailClosed"
        )
        support["indexed_removal_literal_interpretation_requires_independent_filename_group"] = response.get(
            "indexedRemovalLiteralInterpretationRequiresIndependentFilenameGroup"
        )
        support["indexed_removal_stripped_interpretation_requires_independent_filename_group"] = response.get(
            "indexedRemovalStrippedInterpretationRequiresIndependentFilenameGroup"
        )
        support["indexed_removal_removal_only_authority_allowed"] = response.get(
            "indexedRemovalRemovalOnlyAuthorityAllowed"
        )
        support["unindexed_removal_literal_semantics_preserved"] = response.get(
            "unindexedRemovalLiteralSemanticsPreserved"
        )
        support["indexed_removal_interpretation_selected_by_exact_filename_group_only"] = response.get(
            "indexedRemovalInterpretationSelectedByExactFilenameGroupOnly"
        )
        return support


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_SCHEMA27_RICH_INPUT_SUPPORT_NOT_PROVEN")

    # Schema 27 explicitly supersedes schema 26's literal-first indexed-removal
    # interpretation, so do not validate the invalid schema-26 semantic claim as a
    # prerequisite. Preserve the complete safe chain through schema 25 instead.
    legacy = dict(support)
    legacy["schema"] = _v25.SCHEMA
    _v25._validate_support(legacy)

    if support.get("indexed_removal_ambiguity_bidirectional_fail_closed") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_BIDIRECTIONAL_AMBIGUITY_NOT_FAIL_CLOSED")
    if support.get("indexed_removal_literal_interpretation_requires_independent_filename_group") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_LITERAL_INDEXED_CORROBORATION_NOT_PROVEN")
    if support.get("indexed_removal_stripped_interpretation_requires_independent_filename_group") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_STRIPPED_INDEXED_CORROBORATION_NOT_PROVEN")
    if support.get("indexed_removal_removal_only_authority_allowed") is not False:
        raise RuntimeError("PR9_2_SCHEMA27_INDEXED_REMOVAL_ONLY_AUTHORITY_NOT_REVOKED")
    if support.get("unindexed_removal_literal_semantics_preserved") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_UNINDEXED_LITERAL_SEMANTICS_NOT_PRESERVED")
    if support.get("indexed_removal_interpretation_selected_by_exact_filename_group_only") is not True:
        raise RuntimeError("PR9_2_SCHEMA27_INDEXED_INTERPRETATION_SELECTOR_NOT_PROVEN")


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputSchema27LiveProvider()
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

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema27-live-") as temp_dir:
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
        raise RuntimeError("PR9_2_SCHEMA27_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA27_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "attachment_dependent_response_after_every_write": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "schema_25_and_prior_safety_contract_preserved": True,
        "schema_26_literal_first_indexed_semantics_superseded": True,
        "indexed_removal_ambiguity_bidirectional_fail_closed": True,
        "indexed_removal_literal_interpretation_requires_independent_filename_group": True,
        "indexed_removal_stripped_interpretation_requires_independent_filename_group": True,
        "indexed_removal_removal_only_authority_allowed": False,
        "unindexed_removal_literal_semantics_preserved": True,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 schema-27 bidirectional indexed-removal ambiguity rich-input live gate"
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
