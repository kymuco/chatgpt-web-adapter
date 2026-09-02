from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import (
    ProductArtifactLiveProvider,
    _git_output,
    _tracked_clean,
)


SURFACE_SCHEMA = 2
PROBE_FILENAME = "cwa_pr10_1_probe.txt"
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": SURFACE_SCHEMA,
    "fixed_probe_filename": PROBE_FILENAME,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "user_prompt_cannot_become_artifact_evidence": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "locator_values_exported": False,
    "attribute_values_exported": False,
    "click_performed": False,
    "download_attempted": False,
    "write_performed": False,
}

_NAME_LIST_FIELDS = (
    "placementRoleEvidenceKinds",
    "filenameMatchSurfaces",
    "candidateTagNames",
    "candidateAttributeNames",
    "ancestorAttributeNames",
    "interactiveKinds",
    "interactiveAttributeNames",
)
_COUNT_FIELDS = (
    "visibleTurnCount",
    "userTurnCount",
    "assistantTurnCount",
    "roleUnprovenTurnCount",
    "userProbeMarkerTurnCount",
    "assistantCompletionMarkerTurnCount",
    "assistantFilenameSubstringMatchCount",
    "assistantInteractiveFilenameMatchCount",
    "assistantNonInteractiveFilenameMatchCount",
)


def _safe_name_list(value: Any, *, max_items: int = 96) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or len(text) > 80 or not text.isascii():
            continue
        if not all(ch.isalnum() or ch in "_.:-" for ch in text):
            continue
        output.append(text)
        if len(output) >= max_items:
            break
    return sorted(set(output))


def _safe_count(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, maximum)


class ProductArtifactSurfaceV2Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for PR10.1 placement-aware frontend reads."""

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

    def surface_support(
        self,
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._surface_rpc(
            "characterizeGeneratedArtifactSurfaceV2Support",
            timeout=timeout,
        )
        fields = (
            "generatedArtifactSurfaceV2CharacterizationSupported",
            "generatedArtifactSurfaceV2CharacterizationSchemaVersion",
            "fixedProbeFilename",
            "orderedProbePairRequired",
            "assistantTurnAnchorRequired",
            "userPromptCannotBecomeArtifactEvidence",
            "rawDomExported",
            "rawTextExported",
            "locatorValuesExported",
            "attributeValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactSurfaceV2CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactSurfaceV2CharacterizationSchemaVersion"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "user_prompt_cannot_become_artifact_evidence": response.get(
                "userPromptCannotBecomeArtifactEvidence"
            ),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def surface_snapshot(
        self,
        *,
        timeout: float = 10.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._surface_rpc(
            "characterizeGeneratedArtifactSurfaceV2",
            timeout=timeout,
        )
        fields = (
            "schema",
            "fixedProbeFilename",
            "runtimeTabPresent",
            "runtimeRouteKind",
            "runtimeConversationIdPresent",
            "surfaceReady",
            "selectorKind",
            *_COUNT_FIELDS,
            "orderedProbeTurnPairPresent",
            "probePlacementProven",
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
        diagnostic["snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        snapshot: dict[str, Any] = {
            "schema": response.get("schema"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "runtime_route_kind": response.get("runtimeRouteKind")
            if response.get("runtimeRouteKind") in {
                "absent", "root", "conversation", "chatgpt_other", "not_chatgpt", "invalid"
            }
            else "invalid",
            "runtime_conversation_id_present": response.get("runtimeConversationIdPresent") is True,
            "surface_ready": response.get("surfaceReady") is True,
            "selector_kind": response.get("selectorKind")
            if response.get("selectorKind") in {"none", "conversation_testid", "article_fallback"}
            else "none",
            "ordered_probe_turn_pair_present": response.get("orderedProbeTurnPairPresent") is True,
            "probe_placement_proven": response.get("probePlacementProven") is True,
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
        for field in _COUNT_FIELDS:
            key = "".join(["_" + c.lower() if c.isupper() else c for c in field]).lstrip("_")
            snapshot[key] = _safe_count(response.get(field), maximum=64)
        for field in _NAME_LIST_FIELDS:
            key = "".join(["_" + c.lower() if c.isupper() else c for c in field]).lstrip("_")
            snapshot[key] = _safe_name_list(response.get(field))

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
        "schema": "CWA_PR10_1_ARTIFACT_SURFACE_V2_LIVE_GATE_V1",
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

    provider = ProductArtifactSurfaceV2Provider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.surface_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_SURFACE_V2_SUPPORT_RPC_FAILED"
        return report
    report["surface_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SUPPORT:
        report["preflight_error"] = "ARTIFACT_SURFACE_V2_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_SURFACE_V2_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.surface_snapshot(timeout=min(timeout, 20.0))
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["surface_snapshot"] = snapshot
    report["surface_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        report["characterization"] = "ARTIFACT_SURFACE_V2_SNAPSHOT_CONTRACT_NOT_PROVEN"
        return report

    placement_proven = bool(
        snapshot["runtime_tab_present"]
        and snapshot["surface_ready"]
        and snapshot["ordered_probe_turn_pair_present"]
        and snapshot["probe_placement_proven"]
        and snapshot["user_probe_marker_turn_count"] >= 1
        and snapshot["assistant_completion_marker_turn_count"] >= 1
    )
    surface_observed = bool(
        placement_proven
        and (
            snapshot["assistant_filename_substring_match_count"] >= 1
            or snapshot["assistant_interactive_filename_match_count"] >= 1
        )
    )
    interactive_surface_observed = bool(
        placement_proven and snapshot["assistant_interactive_filename_match_count"] >= 1
    )

    report["experiment_valid"] = placement_proven
    report["surface_observed"] = surface_observed
    report["interactive_surface_observed"] = interactive_surface_observed
    if not placement_proven:
        report["characterization"] = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif surface_observed:
        report["characterization"] = "PROBE_ANCHORED_FRONTEND_FILENAME_SURFACE_OBSERVED"
    else:
        report["characterization"] = "PROBE_TURN_PROVEN_NO_FRONTEND_FILENAME_SURFACE_OBSERVED"
    report["ok"] = placement_proven
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PR10.1 placement-aware no-write frontend artifact-surface characterization."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_read:
        parser.error(
            "--acknowledge-live-read is required unless --preflight-only is used; "
            "the gate performs one read-only frontend snapshot, zero product writes, "
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
