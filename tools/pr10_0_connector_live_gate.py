from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
from typing import Any

from chatgpt_web_adapter import ChatGPTWebClient, assemble_product_runtime
from chatgpt_web_adapter.product_capabilities import TOOLS_CONNECTORS, CapabilityState
from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorObservation,
    ProductRequiredActionLifecycleObservation,
)
from chatgpt_web_adapter.product_provenance import CompletionSource, ProductExecutionProvenance


PRODUCT_WRITE_BUDGET = 1
DEFAULT_PROMPT = (
    "Use one of my already connected ChatGPT apps or plugins, if any is available, "
    "for one harmless read-only operation. Do not create, edit, delete, send, upload, "
    "or modify anything. Do not reveal retrieved private content in the answer. "
    "If a connected app was actually used, reply exactly CONNECTED_APP_READ_ONLY_DONE. "
    "If no connected app is available, reply exactly NO_CONNECTED_APP_AVAILABLE."
)
_SAFE_RESPONSE_MARKERS = {
    "CONNECTED_APP_READ_ONLY_DONE",
    "NO_CONNECTED_APP_AVAILABLE",
}
_SAFE_EVENT_KEYS = (
    "type",
    "sequence",
    "activity_id",
    "activity_kind",
    "operation",
    "tool_name",
    "source_content_type",
    "source_event_type",
    "observation_id",
    "connector_activity_id",
    "connector_id",
    "connector_name",
    "action_id",
    "action_type",
)


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _tracked_clean() -> bool:
    return _git_output("status", "--porcelain", "--untracked-files=no") == ""


def _safe_event(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    summary: dict[str, Any] = {}
    for key in _SAFE_EVENT_KEYS:
        value = event.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            summary[key] = value
    return summary or None


def _private_thought_text_exported(events: list[dict[str, Any]]) -> bool:
    for event in events:
        content_type = event.get("source_content_type") or event.get("content_type")
        if content_type != "thoughts":
            continue
        if any(isinstance(event.get(key), str) and event.get(key) for key in ("text", "delta")):
            return True
    return False


def _observation_payload(value: Any) -> dict[str, Any]:
    payload = value.to_dict()
    # Emitter-produced PR10 observations do not carry labels. Keep the live report
    # bounded even if a custom provider constructs one with a product-visible label.
    payload.pop("label", None)
    return payload


def run_gate(*, prompt: str, expected_head: str | None, timeout: float) -> dict[str, Any]:
    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head

    report: dict[str, Any] = {
        "schema": "CWA_PR10_0_CONNECTOR_LIVE_GATE_V1",
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "write_attempted": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    client = ChatGPTWebClient()
    runtime = assemble_product_runtime(client=client)
    before = runtime.capabilities().state(TOOLS_CONNECTORS)
    events: list[dict[str, Any]] = []

    report["capability_before"] = before.value
    report["write_attempted"] = True
    try:
        execution = runtime.send_text_observed(
            prompt,
            timeout=timeout,
            on_event=events.append,
        )
    except Exception as exc:
        # No retry is performed. The exception class is useful; exception text may
        # contain product details, so keep it out of the shareable report.
        report.update(
            {
                "error_type": type(exc).__name__,
                "event_type_counts": dict(Counter(str(event.get("type")) for event in events)),
                "safe_events": [item for event in events if (item := _safe_event(event))],
                "private_thought_text_exported": _private_thought_text_exported(events),
            }
        )
        return report

    after = runtime.capabilities().state(TOOLS_CONNECTORS)
    connector_observations = [
        value
        for value in execution.observations
        if isinstance(value, ProductConnectorObservation)
    ]
    required_action_observations = [
        value
        for value in execution.observations
        if isinstance(value, ProductRequiredActionLifecycleObservation)
    ]

    write_events = [
        event for event in events if event.get("type") == "browser_native_write_completed"
    ]
    readback_events = [
        event for event in events if event.get("type") == "browser_native_readback_completed"
    ]
    provenance = execution.provenance
    canonical_finality = bool(
        isinstance(provenance, ProductExecutionProvenance)
        and provenance.completion.completed is True
        and provenance.completion.source is CompletionSource.CANONICAL_READBACK
        and provenance.completion.canonical_completion_proven is True
    )
    response = execution.response
    conversation_id = getattr(response.conversation, "conversation_id", None)
    message_id = getattr(response.conversation, "message_id", None)
    identity_matches = bool(
        isinstance(provenance, ProductExecutionProvenance)
        and provenance.identity.conversation_id == conversation_id
        and provenance.identity.message_id == message_id
        and conversation_id
        and message_id
    )
    write_observed = getattr(execution.observation, "write_event_observed", None) is True
    governance = runtime.governance()
    no_retry = governance.get("automatic_write_retry") is False
    no_fallback = governance.get("fallback_transport") is None
    private_thought_text_exported = _private_thought_text_exported(events)
    response_text = response.text.strip()
    response_marker = (
        response_text if response_text in _SAFE_RESPONSE_MARKERS else "OTHER_RESPONSE_REDACTED"
    )

    safety_and_finality_ok = bool(
        len(write_events) == 1
        and len(readback_events) == 1
        and canonical_finality
        and identity_matches
        and write_observed
        and no_retry
        and no_fallback
        and not private_thought_text_exported
        and execution.dropped_observation_event_count == 0
        and before is CapabilityState.UNKNOWN
        and after is CapabilityState.UNKNOWN
    )
    connector_observed = bool(connector_observations)

    report.update(
        {
            "capability_after": after.value,
            "connector_capability_remained_unknown": (
                before is CapabilityState.UNKNOWN and after is CapabilityState.UNKNOWN
            ),
            "response_marker": response_marker,
            "response_length": len(response_text),
            "conversation_id_present": bool(conversation_id),
            "message_id_present": bool(message_id),
            "identity_matches": identity_matches,
            "canonical_finality": canonical_finality,
            "completion_source": (
                provenance.completion.source.value
                if isinstance(provenance, ProductExecutionProvenance)
                else None
            ),
            "write_event_count": len(write_events),
            "readback_event_count": len(readback_events),
            "write_event_observed": write_observed,
            "automatic_write_retry": governance.get("automatic_write_retry"),
            "fallback_transport": governance.get("fallback_transport"),
            "private_thought_text_exported": private_thought_text_exported,
            "dropped_observation_event_count": execution.dropped_observation_event_count,
            "observation_kind_counts": dict(
                Counter(getattr(value.kind, "value", str(value.kind)) for value in execution.observations)
            ),
            "connector_observation_count": len(connector_observations),
            "required_action_observation_count": len(required_action_observations),
            "connector_observations": [
                _observation_payload(value) for value in connector_observations
            ],
            "required_action_observations": [
                _observation_payload(value) for value in required_action_observations
            ],
            "event_type_counts": dict(Counter(str(event.get("type")) for event in events)),
            "safe_events": [item for event in events if (item := _safe_event(event))],
            "safety_and_finality_ok": safety_and_finality_ok,
            "characterization": (
                "EXPLICIT_CONNECTOR_EVIDENCE_OBSERVED"
                if connector_observed
                else "NO_EXPLICIT_CONNECTOR_EVIDENCE_OBSERVED"
            ),
            "ok": safety_and_finality_ok and connector_observed,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded authenticated PR10.0 app/connector characterization turn."
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()

    report = run_gate(
        prompt=args.prompt,
        expected_head=args.expected_head,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
