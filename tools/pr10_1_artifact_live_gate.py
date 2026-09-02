from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
from typing import Any
import uuid

from chatgpt_web_adapter import ChatGPTWebClient, assemble_product_runtime
from chatgpt_web_adapter.product_artifact_observation_pr10_1 import ProductArtifactObservation
from chatgpt_web_adapter.product_model_profile_pr8_10 import ProductModelProfileProvider
from chatgpt_web_adapter.product_provenance import CompletionSource, ProductExecutionProvenance


PRODUCT_WRITE_BUDGET = 1
ARTIFACT_OBSERVATION_SCHEMA = 1
DEFAULT_PROMPT = (
    "Create one tiny plain-text downloadable file named cwa_pr10_1_probe.txt containing "
    "exactly CWA_PR10_1_ARTIFACT_PROBE. Do not use connectors, do not access private data, "
    "and do not create, edit, send, or upload anything outside this ChatGPT conversation. "
    "If the downloadable file is actually attached or available in your response, reply "
    "exactly ARTIFACT_PROBE_CREATED. Otherwise reply exactly ARTIFACT_PROBE_UNAVAILABLE."
)
_SAFE_RESPONSE_MARKERS = {"ARTIFACT_PROBE_CREATED", "ARTIFACT_PROBE_UNAVAILABLE"}
_SAFE_EVENT_KEYS = (
    "type",
    "sequence",
    "activity_id",
    "activity_kind",
    "tool_name",
    "operation",
    "source_content_type",
    "artifact_id",
    "filename",
    "media_type",
    "size_bytes",
    "download_available",
    "source_origin",
    "observation_id",
)
_EXPECTED_ARTIFACT_SUPPORT = {
    "supported": True,
    "schema": ARTIFACT_OBSERVATION_SCHEMA,
    "explicit_artifact_identity_required": True,
    "artifact_locator_exported": False,
    "grants_download_authority": False,
    "grants_overwrite_authority": False,
    "write_performed": False,
}


class ProductArtifactLiveProvider(ProductModelProfileProvider):
    """Production provider plus the PR10.1 no-write artifact support proof."""

    def artifact_observation_support(
        self,
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "characterizeConnectorObservationSupport": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        request_id_matches = response.get("request_id") == request_id
        response_ok = response.get("ok") is True
        artifact_fields = (
            "generatedArtifactObservationSupported",
            "generatedArtifactObservationSchemaVersion",
            "explicitArtifactIdentityRequired",
            "artifactLocatorExported",
            "artifactObservationGrantsDownloadAuthority",
            "artifactObservationGrantsOverwriteAuthority",
            "writePerformed",
        )
        diagnostic = {
            "request_id_matches": request_id_matches,
            "response_ok": response_ok,
            "artifact_support_fields_present": all(key in response for key in artifact_fields),
        }
        if not request_id_matches:
            diagnostic["failure_reason"] = "REQUEST_ID_MISMATCH"
            return None, diagnostic
        if not response_ok:
            diagnostic["failure_reason"] = "WORKER_RETURNED_ERROR"
            return None, diagnostic

        support = {
            "supported": response.get("generatedArtifactObservationSupported") is True,
            "schema": response.get("generatedArtifactObservationSchemaVersion"),
            "explicit_artifact_identity_required": response.get("explicitArtifactIdentityRequired"),
            "artifact_locator_exported": response.get("artifactLocatorExported"),
            "grants_download_authority": response.get("artifactObservationGrantsDownloadAuthority"),
            "grants_overwrite_authority": response.get("artifactObservationGrantsOverwriteAuthority"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = (
            None if support == _EXPECTED_ARTIFACT_SUPPORT else "CONTRACT_MISMATCH"
        )
        return support, diagnostic


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
        if isinstance(value, bool):
            summary[key] = value
        elif isinstance(value, (str, int)):
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
        "schema": "CWA_PR10_1_ARTIFACT_LIVE_GATE_V1",
        "artifact_observation_schema": ARTIFACT_OBSERVATION_SCHEMA,
        "product_write_budget": 0 if preflight_only else PRODUCT_WRITE_BUDGET,
        "preflight_only": preflight_only,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "support_probe_attempted": False,
        "support_probe_proven": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactLiveProvider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.artifact_observation_support(timeout=min(10.0, timeout))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_OBSERVATION_SUPPORT_RPC_FAILED"
        return report

    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_ARTIFACT_SUPPORT:
        report["support"] = support
        report["preflight_error"] = "ARTIFACT_OBSERVATION_SUPPORT_NOT_PROVEN"
        return report

    report["support"] = support
    report["support_probe_proven"] = True
    if preflight_only:
        report["characterization"] = "ARTIFACT_SUPPORT_PREFLIGHT_ONLY_PROVEN"
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

    artifacts = [
        value for value in execution.observations if isinstance(value, ProductArtifactObservation)
    ]
    write_events = [event for event in events if event.get("type") == "browser_native_write_completed"]
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
    governance = runtime.governance()
    private_thought_text_exported = _private_thought_text_exported(events)
    response_text = response.text.strip()
    response_marker = (
        response_text if response_text in _SAFE_RESPONSE_MARKERS else "OTHER_RESPONSE_REDACTED"
    )
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
    artifact_observed = bool(artifacts)

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
            "characterization": (
                "EXPLICIT_ARTIFACT_EVIDENCE_OBSERVED"
                if artifact_observed
                else "NO_EXPLICIT_ARTIFACT_EVIDENCE_OBSERVED"
            ),
            "ok": safety_and_finality_ok and artifact_observed,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded authenticated PR10.1 generated-artifact characterization."
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
            "the live gate performs exactly one product write and no artifact download"
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
