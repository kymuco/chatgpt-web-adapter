from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from .client import ChatGPTWebClient
from . import product_rich_input_live_gate_pr9_2 as _v7
from .product_rich_input_live_gate_schema29_pr9_2 import (
    ProductRichInputSchema29LiveProvider,
    _validate_support,
)
from .product_runtime import assemble_product_runtime


SCHEMA = 29
PRODUCT_WRITE_BUDGET = 1


def run_identity_probe(*, timeout: float = 150.0) -> dict[str, Any]:
    """Perform exactly one authenticated rich new-chat write to prove schema-29 identity."""
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
        "probe": "SCHEMA29_REQUEST_BOUND_PROTOCOL_IDENTITY_CONSENSUS",
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "support": support,
        "turn": None,
    }

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-schema29-identity-live-") as temp_dir:
        image_path, _, _ = _v7._write_fixtures(Path(temp_dir))
        events: list[dict[str, Any]] = []

        report["write_attempts"] += 1
        execution = runtime.send_text_observed(
            _v7._IMAGE_PROMPT,
            media=[image_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=events.append,
        )
        report["write_completions"] += 1

        turn = _v7._validate_execution(
            label="SCHEMA29_IDENTITY_IMAGE_NEW_CHAT",
            execution=execution,
            events=events,
            expected_text=_v7._IMAGE_REPLY,
            expected_attachment_count=1,
            attachment_evidence_kind="image_color_band_order",
        )
        conversation_id = turn.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_PROBE_CONVERSATION_ID_NOT_PROVEN")
        report["turn"] = turn

    if report["write_attempts"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_PROBE_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_SCHEMA29_IDENTITY_PROBE_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "exactly_one_product_write": True,
        "image_new_chat_proven": True,
        "attachment_dependent_response_proven": True,
        "canonical_finality_proven": True,
        "conversation_identity_resolved": True,
        "new_chat_conversation_identity_authority": support.get(
            "new_chat_conversation_identity_authority"
        ),
        "request_bound_protocol_conversation_id_consensus": True,
        "top_level_conversation_id_authority": True,
        "root_add_value_conversation_id_authority": True,
        "stream_handoff_required_for_causal_conversation_identity": False,
        "unrecognized_nested_conversation_id_can_satisfy_identity": False,
        "route_conversation_identity_authoritative": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR9.2 schema-29 one-write authenticated exact-request protocol identity probe"
        )
    )
    parser.add_argument("--acknowledge-live-write", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    if not args.acknowledge_live_write:
        parser.error(
            "--acknowledge-live-write is required; this probe performs exactly one product write"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    report = run_identity_probe(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
