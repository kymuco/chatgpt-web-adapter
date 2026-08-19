from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from typing import Any

from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
PROMPT = (
    "PR8.9 production revision-safe streaming gate. Produce exactly 24 numbered "
    "plain-text lines. Each line must be one neutral sentence of roughly 12 to 18 "
    "words about mathematics, computing, measurement, or engineering. Start line 1 "
    "with PR8_9_PRODUCTION_STREAM_START and end line 24 with "
    "PR8_9_PRODUCTION_STREAM_END. Do not use a code block."
)
STREAM_TYPES = {
    "assistant_text_snapshot",
    "assistant_text_delta",
    "assistant_text_revision",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PR8.9.3 production streaming live gate")
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    if not args.acknowledge_live_writes:
        raise SystemExit("Refusing live gate without --acknowledge-live-writes")

    client = ChatGPTWebClient()
    read_client = ChatGPTWebClient(
        auth=copy.deepcopy(client.auth),
        timeout=max(10, int(args.timeout)),
        auto_refresh_auth=False,
        persist_refreshed_auth=False,
        auto_login=False,
        auto_sentinel=False,
    )
    baseline = read_client.get_status(args.conversation)
    if getattr(baseline, "status", None) != "completed":
        raise SystemExit("PR8_9_PRODUCTION_STREAM_BASELINE_NOT_COMPLETED")

    runtime = assemble_product_runtime(client=client, browser_authority_policy="PERSISTENT")
    started = time.monotonic()
    events: list[dict[str, Any]] = []

    def elapsed_ms() -> int:
        return round((time.monotonic() - started) * 1000)

    def on_event(event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        event_type = event.get("type")
        if not isinstance(event_type, str):
            return
        reduced: dict[str, Any] = {"type": event_type, "observed_ms": elapsed_ms()}
        for key in (
            "sequence",
            "message_id",
            "text_length",
            "provisional_text_length",
            "before_network_complete",
            "reconciliation",
            "stream_observation_count",
            "stream_revision_count",
            "stream_delta_count",
            "stream_delivery_incomplete",
            "revision_safe_stream_observation_count",
        ):
            if key in event:
                reduced[key] = event[key]
        if event_type == "assistant_text_snapshot" and isinstance(event.get("text"), str):
            reduced["text_sha256"] = _sha256(event["text"])
        elif event_type == "assistant_text_delta" and isinstance(event.get("delta"), str):
            reduced["delta_length"] = len(event["delta"])
        elif event_type == "assistant_text_revision" and isinstance(event.get("text"), str):
            reduced["text_sha256"] = _sha256(event["text"])
        elif event_type == "canonical_text_finalized" and isinstance(event.get("text"), str):
            reduced["canonical_text_sha256"] = _sha256(event["text"])
        events.append(reduced)

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR8.9.3",
        "product_write_budget": 1,
        "write_attempts": 1,
        "write_completions": 0,
        "automatic_write_retry": False,
        "conversation": args.conversation,
    }
    try:
        execution = runtime.send_text_observed(
            PROMPT,
            conversation=args.conversation,
            timeout=args.timeout,
            poll_interval=0.5,
            conversation_mode="normal",
            browser_authority_policy="PERSISTENT",
            on_event=on_event,
        )
    except BaseException as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        report["events"] = events
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    report["write_completions"] = 1
    response = execution.response
    stream_events = [event for event in events if event["type"] in STREAM_TYPES]
    write_completed = next(
        (event for event in events if event["type"] == "browser_native_write_completed"),
        None,
    )
    finalized = next(
        (event for event in events if event["type"] == "canonical_text_finalized"),
        None,
    )
    first_stream_ms = stream_events[0]["observed_ms"] if stream_events else None
    write_completed_ms = write_completed["observed_ms"] if write_completed else None
    early = (
        isinstance(first_stream_ms, int)
        and isinstance(write_completed_ms, int)
        and first_stream_ms < write_completed_ms
    )
    reconciliation = finalized.get("reconciliation") if finalized else None
    supported = bool(
        stream_events
        and early
        and finalized
        and reconciliation in {
            "EXACT_MATCH",
            "CANONICAL_EXTENDS_STREAM",
            "STREAM_REVISED_BY_CANONICAL",
        }
    )
    report["events"] = events
    report["summary"] = {
        "stream_event_count": len(stream_events),
        "snapshot_count": sum(e["type"] == "assistant_text_snapshot" for e in stream_events),
        "delta_count": sum(e["type"] == "assistant_text_delta" for e in stream_events),
        "revision_count": sum(e["type"] == "assistant_text_revision" for e in stream_events),
        "first_stream_event_ms": first_stream_ms,
        "browser_native_write_completed_ms": write_completed_ms,
        "first_text_lead_before_browser_write_completed_ms": (
            write_completed_ms - first_stream_ms if early else None
        ),
        "canonical_text_finalized_ms": finalized.get("observed_ms") if finalized else None,
        "response_returned_ms": elapsed_ms(),
        "reconciliation": reconciliation,
        "final_response_length": len(response.text),
        "final_response_sha256": _sha256(response.text),
        "production_revision_safe_streaming_supported": supported,
    }
    report["architecture_invalidation_check"] = {
        "single_product_write_preserved": True,
        "automatic_write_retry": False,
        "canonical_finality_authoritative": True,
        "candidate_b_production_delivery": "SUPPORTED" if supported else "NOT_PROVEN",
    }
    report["ok"] = True
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
