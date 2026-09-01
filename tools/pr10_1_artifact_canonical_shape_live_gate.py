from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from typing import Any

from chatgpt_web_adapter import ChatGPTWebClient, assemble_product_runtime
from chatgpt_web_adapter.messages import _current_branch_nodes
from chatgpt_web_adapter.product_artifact_observation_pr10_1 import ProductArtifactObservation
from chatgpt_web_adapter.product_provenance import CompletionSource, ProductExecutionProvenance

from pr10_1_artifact_live_gate import (
    DEFAULT_PROMPT,
    ProductArtifactLiveProvider,
    _EXPECTED_ARTIFACT_SUPPORT,
    _git_output,
    _private_thought_text_exported,
    _safe_event,
    _tracked_clean,
)


PROBE_FILENAME = "cwa_pr10_1_probe.txt"
CANONICAL_SHAPE_SCHEMA = 1
PRODUCT_WRITE_BUDGET = 1
ADDITIONAL_CANONICAL_READ_BUDGET = 1
MAX_DEPTH = 12
MAX_VISITED_NODES = 4096
MAX_FINDINGS = 16
MAX_SIBLING_KEYS = 32

_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_TEXT_VALUE_KEYS = frozenset(
    {
        "text",
        "delta",
        "content",
        "code",
        "stdout",
        "stderr",
        "output",
        "input",
        "prompt",
        "arguments",
        "args",
    }
)
_LOCATOR_KEYS = frozenset(
    {"url", "href", "download_url", "download_uri", "signed_url", "asset_pointer"}
)
_IDENTITY_KEYS = frozenset(
    {
        "id",
        "artifact_id",
        "file_id",
        "asset_id",
        "attachment_id",
        "generated_file_id",
    }
)
_SAFE_RESPONSE_MARKERS = {"ARTIFACT_PROBE_CREATED", "ARTIFACT_PROBE_UNAVAILABLE"}


def _safe_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not _SAFE_KEY_RE.fullmatch(text):
        return None
    return text


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _message_role(message: dict[str, Any]) -> str | None:
    author = message.get("author")
    if not isinstance(author, dict):
        return None
    return _optional_text(author.get("role"))


def _message_content_type(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if not isinstance(content, dict):
        return None
    return _optional_text(content.get("content_type"))


def _anchor_kind(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if value == PROBE_FILENAME:
        return "exact_filename"
    normalized = value.replace("\\", "/")
    if normalized.endswith("/" + PROBE_FILENAME) or normalized.endswith(":" + PROBE_FILENAME):
        return "filename_suffix"
    return None


def _path_string(parts: list[str]) -> str:
    return ".".join(parts)[:800]


def _safe_sibling_keys(value: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for key in value.keys():
        safe = _safe_key(key)
        if safe is not None:
            output.append(safe)
        if len(output) >= MAX_SIBLING_KEYS:
            break
    return sorted(set(output))


def _scan_message_structure(
    message: dict[str, Any],
    *,
    branch_index: int,
    findings: list[dict[str, Any]],
    budget: dict[str, int],
) -> None:
    role = _message_role(message)
    content_type = _message_content_type(message)
    if role == "user" or content_type == "thoughts":
        return

    def visit(value: Any, path: list[str], depth: int) -> None:
        if len(findings) >= MAX_FINDINGS or budget["visited"] >= MAX_VISITED_NODES:
            return
        if depth > MAX_DEPTH:
            return
        budget["visited"] += 1

        if isinstance(value, list):
            # Primitive strings in arrays are commonly assistant prose/content parts.
            # They are intentionally not inspected for the probe filename.
            for item in value[:128]:
                if isinstance(item, (dict, list)):
                    visit(item, [*path, "[]"], depth + 1)
            return
        if not isinstance(value, dict):
            return

        siblings = _safe_sibling_keys(value)
        locator_key_present = any(key in _LOCATOR_KEYS for key in siblings)
        identity_keys = [key for key in siblings if key in _IDENTITY_KEYS]

        for raw_key, child in list(value.items())[:128]:
            safe_key = _safe_key(raw_key)
            if safe_key is None:
                continue
            child_path = [*path, safe_key]
            if isinstance(child, str) and safe_key not in _TEXT_VALUE_KEYS:
                anchor = _anchor_kind(child)
                if anchor is not None:
                    findings.append(
                        {
                            "anchor_kind": anchor,
                            "path": _path_string(child_path),
                            "field_key": safe_key,
                            "sibling_keys": ",".join(siblings)[:800] or None,
                            "identity_key_candidates": ",".join(identity_keys)[:400] or None,
                            "locator_key_present": locator_key_present,
                            "source_role": role,
                            "source_content_type": content_type,
                            "branch_index": branch_index,
                        }
                    )
                    if len(findings) >= MAX_FINDINGS:
                        return
            if isinstance(child, (dict, list)):
                visit(child, child_path, depth + 1)

    # Scan structured message metadata/content only. Top-level text-like fields,
    # ids, recipients, and author names cannot create an artifact shape finding.
    for root_key in ("metadata", "content"):
        root = message.get(root_key)
        if isinstance(root, (dict, list)):
            visit(root, ["branch", "[]", "message", root_key], 0)


def characterize_canonical_payload(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    budget = {"visited": 0}
    if not isinstance(payload, dict):
        return {
            "payload_present": False,
            "current_branch_node_count": 0,
            "visited_structure_nodes": 0,
            "findings": [],
        }

    branch = _current_branch_nodes(payload)
    for branch_index, (_node_id, node) in enumerate(branch):
        if len(findings) >= MAX_FINDINGS or budget["visited"] >= MAX_VISITED_NODES:
            break
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if isinstance(message, dict):
            _scan_message_structure(
                message,
                branch_index=branch_index,
                findings=findings,
                budget=budget,
            )

    return {
        "payload_present": True,
        "current_branch_node_count": len(branch),
        "visited_structure_nodes": budget["visited"],
        "findings": findings,
    }


def _support_preflight(
    provider: ProductArtifactLiveProvider,
    *,
    timeout: float,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return provider.artifact_observation_support(timeout=min(10.0, timeout))


def run_gate(
    *,
    prompt: str,
    expected_head: str | None,
    timeout: float,
    preflight_only: bool = False,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_CANONICAL_SHAPE_LIVE_GATE_V1",
        "canonical_shape_schema": CANONICAL_SHAPE_SCHEMA,
        "product_write_budget": 0 if preflight_only else PRODUCT_WRITE_BUDGET,
        "additional_canonical_read_budget": 0 if preflight_only else ADDITIONAL_CANONICAL_READ_BUDGET,
        "preflight_only": preflight_only,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "support_probe_attempted": False,
        "support_probe_proven": False,
        "write_attempted": False,
        "additional_canonical_read_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_canonical_payload_exported": False,
        "raw_canonical_payload_persisted": False,
        "assistant_text_used_as_artifact_evidence": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactLiveProvider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = _support_preflight(provider, timeout=timeout)
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_OBSERVATION_SUPPORT_RPC_FAILED"
        return report

    report["support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_ARTIFACT_SUPPORT:
        report["preflight_error"] = "ARTIFACT_OBSERVATION_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    report["canonical_shape_support"] = {
        "supported": True,
        "schema": CANONICAL_SHAPE_SCHEMA,
        "fixed_probe_filename": PROBE_FILENAME,
        "current_branch_only": True,
        "user_messages_excluded": True,
        "thoughts_excluded": True,
        "primitive_content_parts_excluded": True,
        "raw_payload_exported": False,
        "raw_payload_persisted": False,
        "locator_values_exported": False,
        "additional_write_required": False,
    }
    if preflight_only:
        report["characterization"] = "ARTIFACT_CANONICAL_SHAPE_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)
    events: list[dict[str, Any]] = []
    report["write_attempted"] = True
    try:
        execution = runtime.send_text_observed(prompt, timeout=timeout, on_event=events.append)
    except Exception as exc:
        report.update(
            {
                "error_type": type(exc).__name__,
                "event_type_counts": dict(Counter(str(event.get("type")) for event in events)),
                "safe_events": [item for event in events if (item := _safe_event(event))],
                "private_thought_text_exported": _private_thought_text_exported(events),
            }
        )
        return report

    provenance = execution.provenance
    response = execution.response
    conversation_id = getattr(response.conversation, "conversation_id", None)
    message_id = getattr(response.conversation, "message_id", None)
    canonical_finality = bool(
        isinstance(provenance, ProductExecutionProvenance)
        and provenance.completion.completed is True
        and provenance.completion.source is CompletionSource.CANONICAL_READBACK
        and provenance.completion.canonical_completion_proven is True
    )
    identity_matches = bool(
        isinstance(provenance, ProductExecutionProvenance)
        and provenance.identity.conversation_id == conversation_id
        and provenance.identity.message_id == message_id
        and conversation_id
        and message_id
    )
    governance = runtime.governance()
    write_events = [event for event in events if event.get("type") == "browser_native_write_completed"]
    readback_events = [
        event for event in events if event.get("type") == "browser_native_readback_completed"
    ]
    private_thought_text_exported = _private_thought_text_exported(events)
    safety_and_finality_ok = bool(
        len(write_events) == PRODUCT_WRITE_BUDGET
        and len(readback_events) == PRODUCT_WRITE_BUDGET
        and canonical_finality
        and identity_matches
        and getattr(execution.observation, "write_event_observed", None) is True
        and governance.get("automatic_write_retry") is False
        and governance.get("fallback_transport") is None
        and not private_thought_text_exported
        and execution.dropped_observation_event_count == 0
    )

    canonical_payload = None
    canonical_read_error_type = None
    reader = getattr(client, "_get_conversation_payload", None)
    if callable(reader) and isinstance(conversation_id, str) and conversation_id:
        report["additional_canonical_read_attempted"] = True
        try:
            canonical_payload = reader(conversation_id)
        except Exception as exc:
            canonical_read_error_type = type(exc).__name__

    shape = characterize_canonical_payload(canonical_payload)
    findings = shape["findings"]
    artifacts = [
        value for value in execution.observations if isinstance(value, ProductArtifactObservation)
    ]
    response_text = response.text.strip()
    response_marker = (
        response_text if response_text in _SAFE_RESPONSE_MARKERS else "OTHER_RESPONSE_REDACTED"
    )

    report.update(
        {
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
            "automatic_write_retry": governance.get("automatic_write_retry"),
            "fallback_transport": governance.get("fallback_transport"),
            "private_thought_text_exported": private_thought_text_exported,
            "dropped_observation_event_count": execution.dropped_observation_event_count,
            "artifact_observation_count": len(artifacts),
            "artifact_observations": [value.to_dict() for value in artifacts],
            "event_type_counts": dict(Counter(str(event.get("type")) for event in events)),
            "safe_events": [item for event in events if (item := _safe_event(event))],
            "safety_and_finality_ok": safety_and_finality_ok,
            "additional_canonical_read_error_type": canonical_read_error_type,
            "canonical_payload_present": shape["payload_present"],
            "current_branch_node_count": shape["current_branch_node_count"],
            "visited_structure_nodes": shape["visited_structure_nodes"],
            "canonical_shape_observation_count": len(findings),
            "canonical_shape_observations": findings,
            "characterization": (
                "PROBE_ANCHORED_CANONICAL_ARTIFACT_SHAPE_OBSERVED"
                if findings
                else "NO_PROBE_ANCHORED_CANONICAL_ARTIFACT_SHAPE_OBSERVED"
            ),
            "ok": safety_and_finality_ok and shape["payload_present"] and bool(findings),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded PR10.1 canonical-payload generated-artifact shape characterization."
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-write", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_write:
        parser.error(
            "--acknowledge-live-write is required unless --preflight-only is used; "
            "the gate performs exactly one product write, one extra canonical read, "
            "and no artifact download"
        )

    report = run_gate(
        prompt=args.prompt,
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
