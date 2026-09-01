from __future__ import annotations

import argparse
import json
import re
from typing import Any
import uuid

from pr10_1_artifact_live_gate import (
    ProductArtifactLiveProvider,
    _git_output,
    _tracked_clean,
)


SURFACE_SCHEMA = 1
PROBE_FILENAME = "cwa_pr10_1_probe.txt"
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_EXPECTED_SURFACE_SUPPORT = {
    "supported": True,
    "schema": SURFACE_SCHEMA,
    "fixed_probe_filename": PROBE_FILENAME,
    "assistant_ownership_required": True,
    "user_turn_matches_excluded": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "locator_values_exported": False,
    "attribute_values_exported": False,
    "click_performed": False,
    "download_attempted": False,
    "write_performed": False,
}

_NAME_LIST_FIELDS = (
    "assistantRoleEvidenceKinds",
    "candidateTagNames",
    "candidateAttributeNames",
    "ancestorAttributeNames",
    "interactiveKinds",
    "interactiveAttributeNames",
)


def _safe_name_list(value: Any, *, max_items: int = 96) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not _SAFE_NAME_RE.fullmatch(text):
            continue
        output.append(text)
        if len(output) >= max_items:
            break
    return sorted(set(output))


def _safe_count(value: Any, *, max_value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, max_value)


class ProductArtifactSurfaceProvider(ProductArtifactLiveProvider):
    """PR10.1 provider extension for bounded no-write frontend surface reads."""

    def _surface_rpc(
        self,
        flag: str,
        *,
        timeout: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                flag: True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        diagnostic = {
            "request_id_matches": response.get("request_id") == request_id,
            "response_ok": response.get("ok") is True,
        }
        if diagnostic["request_id_matches"] is not True:
            diagnostic["failure_reason"] = "REQUEST_ID_MISMATCH"
        elif diagnostic["response_ok"] is not True:
            diagnostic["failure_reason"] = "WORKER_RETURNED_ERROR"
        else:
            diagnostic["failure_reason"] = None
        return response, diagnostic

    def artifact_surface_support(
        self,
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._surface_rpc(
            "characterizeGeneratedArtifactSurfaceSupport",
            timeout=timeout,
        )
        fields = (
            "generatedArtifactSurfaceCharacterizationSupported",
            "generatedArtifactSurfaceCharacterizationSchemaVersion",
            "fixedProbeFilename",
            "assistantOwnershipRequired",
            "userTurnMatchesExcluded",
            "rawDomExported",
            "rawTextExported",
            "locatorValuesExported",
            "attributeValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["surface_support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactSurfaceCharacterizationSupported") is True,
            "schema": response.get("generatedArtifactSurfaceCharacterizationSchemaVersion"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "assistant_ownership_required": response.get("assistantOwnershipRequired"),
            "user_turn_matches_excluded": response.get("userTurnMatchesExcluded"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = (
            None if support == _EXPECTED_SURFACE_SUPPORT else "CONTRACT_MISMATCH"
        )
        return support, diagnostic

    def artifact_surface_snapshot(
        self,
        *,
        timeout: float = 10.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._surface_rpc(
            "characterizeGeneratedArtifactSurface",
            timeout=timeout,
        )
        fields = (
            "schema",
            "fixedProbeFilename",
            "runtimeTabPresent",
            "surfaceReady",
            "exactFilenameVisible",
            "exactFilenameMatchCount",
            "anyExactFilenameMatchCount",
            "userOwnedExactFilenameMatchCount",
            "roleUnprovenExactFilenameMatchCount",
            *_NAME_LIST_FIELDS,
            "hrefAttributePresent",
            "downloadAttributePresent",
            "conversationTurnAncestorPresent",
            "reactFiberPropertyPresent",
            "reactPropsPropertyPresent",
            "rawDomExported",
            "rawTextExported",
            "locatorValuesExported",
            "attributeValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
            "debuggerAttachedAfter",
        )
        diagnostic["surface_snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        snapshot = {
            "schema": response.get("schema"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "surface_ready": response.get("surfaceReady") is True,
            "exact_filename_visible": response.get("exactFilenameVisible") is True,
            "exact_filename_match_count": _safe_count(
                response.get("exactFilenameMatchCount"), max_value=16
            ),
            "any_exact_filename_match_count": _safe_count(
                response.get("anyExactFilenameMatchCount"), max_value=32
            ),
            "user_owned_exact_filename_match_count": _safe_count(
                response.get("userOwnedExactFilenameMatchCount"), max_value=32
            ),
            "role_unproven_exact_filename_match_count": _safe_count(
                response.get("roleUnprovenExactFilenameMatchCount"), max_value=32
            ),
            "assistant_role_evidence_kinds": _safe_name_list(
                response.get("assistantRoleEvidenceKinds"), max_items=8
            ),
            "candidate_tag_names": _safe_name_list(response.get("candidateTagNames"), max_items=32),
            "candidate_attribute_names": _safe_name_list(response.get("candidateAttributeNames")),
            "ancestor_attribute_names": _safe_name_list(response.get("ancestorAttributeNames")),
            "interactive_kinds": _safe_name_list(response.get("interactiveKinds"), max_items=16),
            "interactive_attribute_names": _safe_name_list(response.get("interactiveAttributeNames")),
            "href_attribute_present": response.get("hrefAttributePresent") is True,
            "download_attribute_present": response.get("downloadAttributePresent") is True,
            "conversation_turn_ancestor_present": response.get("conversationTurnAncestorPresent") is True,
            "react_fiber_property_present": response.get("reactFiberPropertyPresent") is True,
            "react_props_property_present": response.get("reactPropsPropertyPresent") is True,
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == SURFACE_SCHEMA
            and snapshot["fixed_probe_filename"] == PROBE_FILENAME
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["locator_values_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["click_performed"] is False
            and snapshot["download_attempted"] is False
            and snapshot["write_performed"] is False
            and snapshot["debugger_attached_after"] in {False, None}
        )
        diagnostic["snapshot_contract_ok"] = contract_ok
        if not contract_ok:
            diagnostic["failure_reason"] = "SNAPSHOT_CONTRACT_MISMATCH"
        return snapshot, diagnostic


def run_gate(
    *,
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
        "schema": "CWA_PR10_1_ARTIFACT_SURFACE_LIVE_GATE_V1",
        "surface_schema": SURFACE_SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "surface_read_budget": 0 if preflight_only else SURFACE_READ_BUDGET,
        "download_budget": DOWNLOAD_BUDGET,
        "local_write_budget": LOCAL_WRITE_BUDGET,
        "preflight_only": preflight_only,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head_matches,
        "tracked_clean": tracked_clean,
        "support_probe_attempted": False,
        "support_probe_proven": False,
        "surface_read_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_dom_exported": False,
        "raw_text_exported": False,
        "locator_values_exported": False,
        "attribute_values_exported": False,
        "click_performed": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactSurfaceProvider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.artifact_surface_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_SURFACE_SUPPORT_RPC_FAILED"
        return report
    report["surface_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SURFACE_SUPPORT:
        report["preflight_error"] = "ARTIFACT_SURFACE_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_SURFACE_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.artifact_surface_snapshot(
            timeout=min(timeout, 20.0)
        )
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["surface_snapshot"] = snapshot
    report["surface_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        report["characterization"] = "ARTIFACT_SURFACE_SNAPSHOT_CONTRACT_NOT_PROVEN"
        return report

    observed = bool(
        snapshot["runtime_tab_present"]
        and snapshot["surface_ready"]
        and snapshot["exact_filename_visible"]
        and snapshot["exact_filename_match_count"] >= 1
        and bool(snapshot["assistant_role_evidence_kinds"])
    )
    report["characterization"] = (
        "PROBE_ANCHORED_FRONTEND_ARTIFACT_SURFACE_OBSERVED"
        if observed
        else "NO_PROBE_ANCHORED_FRONTEND_ARTIFACT_SURFACE_OBSERVED"
    )
    report["ok"] = observed
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded PR10.1 no-write generated-artifact frontend surface characterization."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_read:
        parser.error(
            "--acknowledge-live-read is required unless --preflight-only is used; "
            "the gate performs one read-only frontend surface snapshot, zero product writes, "
            "zero clicks, and zero downloads"
        )

    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
