from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import (
    DEFAULT_PROMPT,
    ProductArtifactLiveProvider,
    _git_output,
    _tracked_clean,
    run_gate,
)


SHAPE_SCHEMA = 1
SHAPE_EVENT = "product_artifact_shape_observed"
_EXPECTED_SHAPE_SUPPORT = {
    "supported": True,
    "schema": SHAPE_SCHEMA,
    "probe_filename_anchored": True,
    "raw_payload_exported": False,
    "artifact_locator_exported": False,
    "write_performed": False,
}


def _shape_support(
    provider: ProductArtifactLiveProvider,
    *,
    timeout: float,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    request_id = str(uuid.uuid4())
    response = provider._rpc(
        {
            "type": "turn",
            "request_id": request_id,
            "characterizeGeneratedArtifactShapeSupport": True,
            "timeoutMs": int(timeout * 1000),
        },
        timeout=timeout,
    )
    request_id_matches = response.get("request_id") == request_id
    response_ok = response.get("ok") is True
    fields = (
        "generatedArtifactShapeCharacterizationSupported",
        "generatedArtifactShapeCharacterizationSchemaVersion",
        "probeFilenameAnchored",
        "rawPayloadExported",
        "artifactLocatorExported",
        "writePerformed",
    )
    diagnostic = {
        "request_id_matches": request_id_matches,
        "response_ok": response_ok,
        "shape_support_fields_present": all(key in response for key in fields),
    }
    if not request_id_matches:
        diagnostic["failure_reason"] = "REQUEST_ID_MISMATCH"
        return None, diagnostic
    if not response_ok:
        diagnostic["failure_reason"] = "WORKER_RETURNED_ERROR"
        return None, diagnostic

    support = {
        "supported": response.get("generatedArtifactShapeCharacterizationSupported") is True,
        "schema": response.get("generatedArtifactShapeCharacterizationSchemaVersion"),
        "probe_filename_anchored": response.get("probeFilenameAnchored"),
        "raw_payload_exported": response.get("rawPayloadExported"),
        "artifact_locator_exported": response.get("artifactLocatorExported"),
        "write_performed": response.get("writePerformed"),
    }
    diagnostic["failure_reason"] = None if support == _EXPECTED_SHAPE_SUPPORT else "CONTRACT_MISMATCH"
    return support, diagnostic


def run_shape_gate(
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
        "schema": "CWA_PR10_1_ARTIFACT_SHAPE_LIVE_GATE_V1",
        "shape_schema": SHAPE_SCHEMA,
        "product_write_budget": 0 if preflight_only else 1,
        "preflight_only": preflight_only,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "shape_support_probe_attempted": False,
        "shape_support_probe_proven": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactLiveProvider()
    report["shape_support_probe_attempted"] = True
    try:
        support, diagnostic = _shape_support(provider, timeout=min(10.0, timeout))
    except Exception as exc:
        report["shape_support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_SHAPE_SUPPORT_RPC_FAILED"
        return report

    report["shape_support_probe_diagnostic"] = diagnostic
    report["shape_support"] = support
    if support != _EXPECTED_SHAPE_SUPPORT:
        report["preflight_error"] = "ARTIFACT_SHAPE_SUPPORT_NOT_PROVEN"
        return report

    report["shape_support_probe_proven"] = True
    if preflight_only:
        report["characterization"] = "ARTIFACT_SHAPE_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    base = run_gate(
        prompt=prompt,
        expected_head=expected_head,
        timeout=timeout,
        preflight_only=False,
    )
    shape_events = [
        event
        for event in base.get("safe_events", [])
        if isinstance(event, dict) and event.get("type") == SHAPE_EVENT
    ]
    shape_observations = [
        {
            "operation": event.get("operation"),
            "source_content_type": event.get("source_content_type"),
        }
        for event in shape_events
    ]
    safety_ok = base.get("safety_and_finality_ok") is True

    report = {
        **base,
        "schema": "CWA_PR10_1_ARTIFACT_SHAPE_LIVE_GATE_V1",
        "shape_schema": SHAPE_SCHEMA,
        "shape_support_probe_attempted": True,
        "shape_support_probe_proven": True,
        "shape_support_probe_diagnostic": diagnostic,
        "shape_support": support,
        "base_artifact_characterization": base.get("characterization"),
        "shape_observation_count": len(shape_events),
        "shape_observations": shape_observations,
        "characterization": (
            "PROBE_ANCHORED_ARTIFACT_SHAPE_OBSERVED"
            if shape_events
            else "NO_PROBE_ANCHORED_ARTIFACT_SHAPE_OBSERVED"
        ),
        "ok": safety_ok and bool(shape_events),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded PR10.1 probe-anchored generated-artifact shape characterization."
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
            "the shape gate performs exactly one product write and no artifact download"
        )

    report = run_shape_gate(
        prompt=args.prompt,
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
