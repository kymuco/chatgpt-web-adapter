from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


TOPOLOGY_SCHEMA = 3
PROBE_FILENAME = "cwa_pr10_1_probe.txt"
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": TOPOLOGY_SCHEMA,
    "fixed_probe_filename": PROBE_FILENAME,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "per_candidate_structural_only": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "attribute_values_exported": False,
    "react_prop_values_exported": False,
    "locator_values_exported": False,
    "click_performed": False,
    "download_attempted": False,
    "write_performed": False,
}


def _safe_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 80 or not text.isascii():
        return None
    if not all(ch.isalnum() or ch in "_.:-" for ch in text):
        return None
    return text


def _safe_name_list(value: Any, *, max_items: int = 160) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        name = _safe_name(item)
        if name is None:
            continue
        output.append(name)
        if len(output) >= max_items:
            break
    return sorted(set(output))


def _safe_count(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, maximum)


def _safe_nullable_depth(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 16 else None


def _safe_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "index": _safe_count(value.get("index"), maximum=16),
        "tag_name": _safe_name(value.get("tagName")) or "unknown",
        "candidate_attribute_names": _safe_name_list(
            value.get("candidateAttributeNames"), max_items=64
        ),
        "ancestor_tag_path": _safe_name_list(value.get("ancestorTagPath"), max_items=16),
        "ancestor_attribute_names": _safe_name_list(
            value.get("ancestorAttributeNames"), max_items=96
        ),
        "ancestor_depth_to_turn": _safe_nullable_depth(value.get("ancestorDepthToTurn")),
        "inside_pre": value.get("insidePre") is True,
        "inside_code": value.get("insideCode") is True,
        "inside_blockquote": value.get("insideBlockquote") is True,
        "inside_table": value.get("insideTable") is True,
        "direct_interactive_ancestor_present": value.get("directInteractiveAncestorPresent") is True,
        "nearest_interactive_container_depth": _safe_nullable_depth(
            value.get("nearestInteractiveContainerDepth")
        ),
        "nearby_interactive_count": _safe_count(value.get("nearbyInteractiveCount"), maximum=32),
        "nearby_interactive_kinds": _safe_name_list(
            value.get("nearbyInteractiveKinds"), max_items=16
        ),
        "nearby_interactive_attribute_names": _safe_name_list(
            value.get("nearbyInteractiveAttributeNames"), max_items=96
        ),
        "nearby_href_attribute_present": value.get("nearbyHrefAttributePresent") is True,
        "nearby_download_attribute_present": value.get("nearbyDownloadAttributePresent") is True,
        "react_fiber_property_present": value.get("reactFiberPropertyPresent") is True,
        "react_props_property_present": value.get("reactPropsPropertyPresent") is True,
        "react_prop_names": _safe_name_list(value.get("reactPropNames"), max_items=160),
        "identity_like_react_prop_names": _safe_name_list(
            value.get("identityLikeReactPropNames"), max_items=32
        ),
        "locator_like_react_prop_names": _safe_name_list(
            value.get("locatorLikeReactPropNames"), max_items=32
        ),
    }


class ProductArtifactTopologyV3Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for PR10.1 per-candidate frontend topology reads."""

    def _topology_rpc(
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

    def topology_support(
        self,
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._topology_rpc(
            "characterizeGeneratedArtifactTopologyV3Support",
            timeout=timeout,
        )
        fields = (
            "generatedArtifactTopologyV3CharacterizationSupported",
            "generatedArtifactTopologyV3CharacterizationSchemaVersion",
            "fixedProbeFilename",
            "orderedProbePairRequired",
            "assistantTurnAnchorRequired",
            "perCandidateStructuralOnly",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactTopologyV3CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactTopologyV3CharacterizationSchemaVersion"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "per_candidate_structural_only": response.get("perCandidateStructuralOnly"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def topology_snapshot(
        self,
        *,
        timeout: float = 10.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._topology_rpc(
            "characterizeGeneratedArtifactTopologyV3",
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
            "visibleTurnCount",
            "userProbeMarkerTurnCount",
            "assistantCompletionMarkerTurnCount",
            "orderedProbeTurnPairPresent",
            "probePlacementProven",
            "placementRoleEvidenceKinds",
            "filenameCandidateCount",
            "candidateSummaries",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
            "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        candidates = []
        raw_candidates = response.get("candidateSummaries")
        if isinstance(raw_candidates, list):
            for item in raw_candidates[:8]:
                candidate = _safe_candidate(item)
                if candidate is not None:
                    candidates.append(candidate)

        route_kind = response.get("runtimeRouteKind")
        if route_kind not in {
            "absent", "root", "conversation", "chatgpt_other", "not_chatgpt", "invalid"
        }:
            route_kind = "invalid"
        selector_kind = response.get("selectorKind")
        if selector_kind not in {"none", "conversation_testid", "article_fallback"}:
            selector_kind = "none"

        snapshot = {
            "schema": response.get("schema"),
            "fixed_probe_filename": response.get("fixedProbeFilename"),
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "runtime_route_kind": route_kind,
            "runtime_conversation_id_present": response.get("runtimeConversationIdPresent") is True,
            "surface_ready": response.get("surfaceReady") is True,
            "selector_kind": selector_kind,
            "visible_turn_count": _safe_count(response.get("visibleTurnCount"), maximum=64),
            "user_probe_marker_turn_count": _safe_count(
                response.get("userProbeMarkerTurnCount"), maximum=64
            ),
            "assistant_completion_marker_turn_count": _safe_count(
                response.get("assistantCompletionMarkerTurnCount"), maximum=64
            ),
            "ordered_probe_turn_pair_present": response.get("orderedProbeTurnPairPresent") is True,
            "probe_placement_proven": response.get("probePlacementProven") is True,
            "placement_role_evidence_kinds": _safe_name_list(
                response.get("placementRoleEvidenceKinds"), max_items=8
            ),
            "filename_candidate_count": _safe_count(
                response.get("filenameCandidateCount"), maximum=12
            ),
            "candidate_summaries": candidates,
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == TOPOLOGY_SCHEMA
            and snapshot["fixed_probe_filename"] == PROBE_FILENAME
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["react_prop_values_exported"] is False
            and snapshot["locator_values_exported"] is False
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
        "schema": "CWA_PR10_1_ARTIFACT_TOPOLOGY_V3_LIVE_GATE_V1",
        "topology_schema": TOPOLOGY_SCHEMA,
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
        "attribute_values_exported": False,
        "react_prop_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactTopologyV3Provider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.topology_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_TOPOLOGY_V3_SUPPORT_RPC_FAILED"
        return report
    report["topology_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SUPPORT:
        report["preflight_error"] = "ARTIFACT_TOPOLOGY_V3_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_TOPOLOGY_V3_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.topology_snapshot(timeout=min(timeout, 20.0))
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["topology_snapshot"] = snapshot
    report["topology_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        report["characterization"] = "ARTIFACT_TOPOLOGY_V3_SNAPSHOT_CONTRACT_NOT_PROVEN"
        return report

    placement_proven = bool(
        snapshot["runtime_tab_present"]
        and snapshot["surface_ready"]
        and snapshot["ordered_probe_turn_pair_present"]
        and snapshot["probe_placement_proven"]
        and snapshot["user_probe_marker_turn_count"] >= 1
        and snapshot["assistant_completion_marker_turn_count"] >= 1
    )
    candidates = snapshot["candidate_summaries"]
    topology_observed = bool(placement_proven and snapshot["filename_candidate_count"] >= 1 and candidates)
    identity_key_names_observed = any(item["identity_like_react_prop_names"] for item in candidates)
    locator_key_names_observed = any(item["locator_like_react_prop_names"] for item in candidates)
    nearby_interactive_observed = any(item["nearby_interactive_count"] >= 1 for item in candidates)
    code_like_only = bool(
        candidates and all(item["inside_pre"] or item["inside_code"] for item in candidates)
    )

    report["experiment_valid"] = placement_proven
    report["topology_observed"] = topology_observed
    report["identity_key_names_observed"] = identity_key_names_observed
    report["locator_key_names_observed"] = locator_key_names_observed
    report["nearby_interactive_observed"] = nearby_interactive_observed
    report["code_like_only"] = code_like_only

    if not placement_proven:
        report["characterization"] = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif not topology_observed:
        report["characterization"] = "PROBE_TURN_PROVEN_NO_FILENAME_CANDIDATE_TOPOLOGY"
    elif identity_key_names_observed:
        report["characterization"] = "PROBE_ANCHORED_TOPOLOGY_IDENTITY_KEY_NAMES_OBSERVED"
    elif locator_key_names_observed or nearby_interactive_observed:
        report["characterization"] = "PROBE_ANCHORED_TOPOLOGY_INTERACTIVE_OR_LOCATOR_KEY_NAMES_OBSERVED"
    elif code_like_only:
        report["characterization"] = "PROBE_ANCHORED_TOPOLOGY_CODE_LIKE_ONLY"
    else:
        report["characterization"] = "PROBE_ANCHORED_TOPOLOGY_STRUCTURAL_ONLY"

    report["ok"] = placement_proven
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PR10.1 bounded no-write per-candidate artifact topology characterization."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    args = parser.parse_args()

    if not args.preflight_only and not args.acknowledge_live_read:
        parser.error(
            "--acknowledge-live-read is required unless --preflight-only is used; "
            "the gate performs one read-only structural frontend snapshot, zero product writes, "
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
