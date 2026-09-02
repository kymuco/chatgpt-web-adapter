from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


ARTIFACT_SUBTREE_SCHEMA = 7
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": ARTIFACT_SUBTREE_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "fiber_graph_bounded": True,
    "structural_artifact_roots_only": True,
    "dotted_localization_keys_excluded": True,
    "svg_use_fibers_excluded": True,
    "accessor_properties_skipped": True,
    "dom_state_node_values_excluded": True,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "attribute_values_exported": False,
    "react_prop_values_exported": False,
    "react_state_values_exported": False,
    "artifact_subtree_values_exported": False,
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


def _safe_name_list(value: Any, *, max_items: int = 64) -> list[str]:
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


def _safe_nullable_depth(value: Any, *, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= maximum else None


def _safe_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    relation_kind = value.get("relationKind")
    if relation_kind not in {"turn_root", "turn_ancestor", "turn_descendant"}:
        relation_kind = "turn_descendant"
    source_kind = value.get("sourceKind")
    if source_kind not in {
        "memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"
    }:
        source_kind = "memoized_state"
    container_kind = value.get("sourceContainerKind")
    if container_kind not in {"object", "array"}:
        container_kind = "object"
    return {
        "index": _safe_count(value.get("index"), maximum=32),
        "relation_kind": relation_kind,
        "fiber_depth": _safe_count(value.get("fiberDepth"), maximum=64),
        "component_name": _safe_name(value.get("componentName")) or "unknown",
        "source_kind": source_kind,
        "source_nested_depth": _safe_count(value.get("sourceNestedDepth"), maximum=5),
        "source_container_kind": container_kind,
        "artifact_root_key_names": _safe_name_list(value.get("artifactRootKeyNames"), max_items=8),
        "same_container_identity_like_key_names": _safe_name_list(
            value.get("sameContainerIdentityLikeKeyNames"), max_items=24
        ),
        "same_container_locator_like_key_names": _safe_name_list(
            value.get("sameContainerLocatorLikeKeyNames"), max_items=24
        ),
        "subtree_container_count": _safe_count(value.get("subtreeContainerCount"), maximum=64),
        "subtree_identity_like_key_names": _safe_name_list(
            value.get("subtreeIdentityLikeKeyNames"), max_items=24
        ),
        "subtree_locator_like_key_names": _safe_name_list(
            value.get("subtreeLocatorLikeKeyNames"), max_items=24
        ),
        "subtree_structural_artifact_key_names": _safe_name_list(
            value.get("subtreeStructuralArtifactKeyNames"), max_items=24
        ),
        "subtree_identity_min_depth": _safe_nullable_depth(
            value.get("subtreeIdentityMinDepth"), maximum=4
        ),
        "subtree_locator_min_depth": _safe_nullable_depth(
            value.get("subtreeLocatorMinDepth"), maximum=4
        ),
        "strong_candidate": value.get("strongCandidate") is True,
    }


class ProductArtifactSubtreeV7Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for targeted PR10.1 artifact-subtree state reads."""

    def _subtree_rpc(self, flag: str, *, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
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

    def subtree_support(self, *, timeout: float = 5.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._subtree_rpc(
            "characterizeGeneratedArtifactSubtreeV7Support", timeout=timeout
        )
        fields = (
            "generatedArtifactSubtreeV7CharacterizationSupported",
            "generatedArtifactSubtreeV7CharacterizationSchemaVersion",
            "orderedProbePairRequired",
            "assistantTurnAnchorRequired",
            "fiberGraphBounded",
            "structuralArtifactRootsOnly",
            "dottedLocalizationKeysExcluded",
            "svgUseFibersExcluded",
            "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded",
            "rawDomExported",
            "rawTextExported",
            "attributeValuesExported",
            "reactPropValuesExported",
            "reactStateValuesExported",
            "artifactSubtreeValuesExported",
            "locatorValuesExported",
            "clickPerformed",
            "downloadAttempted",
            "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactSubtreeV7CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactSubtreeV7CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "artifact_subtree_values_exported": response.get("artifactSubtreeValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def subtree_snapshot(self, *, timeout: float = 20.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._subtree_rpc("characterizeGeneratedArtifactSubtreeV7", timeout=timeout)
        fields = (
            "schema", "runtimeTabPresent", "runtimeRouteKind", "runtimeConversationIdPresent",
            "surfaceReady", "selectorKind", "visibleTurnCount", "userProbeMarkerTurnCount",
            "assistantCompletionMarkerTurnCount", "orderedProbeTurnPairPresent", "probePlacementProven",
            "placementRoleEvidenceKinds", "fiberRootCount", "scannedFiberCount",
            "scannedSourceContainerCount", "artifactRootHitCount", "attachmentRootHitCount",
            "artifactSubtreeIdentityHitCount", "artifactSubtreeLocatorHitCount",
            "sameContainerIdentityHitCount", "sameContainerLocatorHitCount", "strongCandidateCount",
            "candidateSummaries", "fiberGraphBounded", "structuralArtifactRootsOnly",
            "dottedLocalizationKeysExcluded", "svgUseFibersExcluded", "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded", "rawDomExported", "rawTextExported",
            "attributeValuesExported", "reactPropValuesExported", "reactStateValuesExported",
            "artifactSubtreeValuesExported", "locatorValuesExported", "clickPerformed",
            "downloadAttempted", "writePerformed", "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        candidates: list[dict[str, Any]] = []
        raw_candidates = response.get("candidateSummaries")
        if isinstance(raw_candidates, list):
            for item in raw_candidates[:32]:
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
            "runtime_tab_present": response.get("runtimeTabPresent") is True,
            "runtime_route_kind": route_kind,
            "runtime_conversation_id_present": response.get("runtimeConversationIdPresent") is True,
            "surface_ready": response.get("surfaceReady") is True,
            "selector_kind": selector_kind,
            "visible_turn_count": _safe_count(response.get("visibleTurnCount"), maximum=64),
            "user_probe_marker_turn_count": _safe_count(response.get("userProbeMarkerTurnCount"), maximum=64),
            "assistant_completion_marker_turn_count": _safe_count(
                response.get("assistantCompletionMarkerTurnCount"), maximum=64
            ),
            "ordered_probe_turn_pair_present": response.get("orderedProbeTurnPairPresent") is True,
            "probe_placement_proven": response.get("probePlacementProven") is True,
            "placement_role_evidence_kinds": _safe_name_list(
                response.get("placementRoleEvidenceKinds"), max_items=8
            ),
            "fiber_root_count": _safe_count(response.get("fiberRootCount"), maximum=4),
            "scanned_fiber_count": _safe_count(response.get("scannedFiberCount"), maximum=4096),
            "scanned_source_container_count": _safe_count(
                response.get("scannedSourceContainerCount"), maximum=200000
            ),
            "artifact_root_hit_count": _safe_count(response.get("artifactRootHitCount"), maximum=4096),
            "attachment_root_hit_count": _safe_count(response.get("attachmentRootHitCount"), maximum=4096),
            "artifact_subtree_identity_hit_count": _safe_count(
                response.get("artifactSubtreeIdentityHitCount"), maximum=4096
            ),
            "artifact_subtree_locator_hit_count": _safe_count(
                response.get("artifactSubtreeLocatorHitCount"), maximum=4096
            ),
            "same_container_identity_hit_count": _safe_count(
                response.get("sameContainerIdentityHitCount"), maximum=4096
            ),
            "same_container_locator_hit_count": _safe_count(
                response.get("sameContainerLocatorHitCount"), maximum=4096
            ),
            "strong_candidate_count": _safe_count(response.get("strongCandidateCount"), maximum=4096),
            "candidate_summaries": candidates,
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "artifact_subtree_values_exported": response.get("artifactSubtreeValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == ARTIFACT_SUBTREE_SCHEMA
            and snapshot["fiber_graph_bounded"] is True
            and snapshot["structural_artifact_roots_only"] is True
            and snapshot["dotted_localization_keys_excluded"] is True
            and snapshot["svg_use_fibers_excluded"] is True
            and snapshot["accessor_properties_skipped"] is True
            and snapshot["dom_state_node_values_excluded"] is True
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["react_prop_values_exported"] is False
            and snapshot["react_state_values_exported"] is False
            and snapshot["artifact_subtree_values_exported"] is False
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


def run_gate(*, expected_head: str | None, timeout: float, preflight_only: bool = False) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_SUBTREE_V7_LIVE_GATE_V1",
        "artifact_subtree_schema": ARTIFACT_SUBTREE_SCHEMA,
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
        "react_state_values_exported": False,
        "artifact_subtree_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
        "ok": False,
    }
    if not head_matches or not tracked_clean:
        report["preflight_error"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    provider = ProductArtifactSubtreeV7Provider()
    report["support_probe_attempted"] = True
    try:
        support, diagnostic = provider.subtree_support(timeout=min(timeout, 10.0))
    except Exception as exc:
        report["support_probe_error_type"] = type(exc).__name__
        report["preflight_error"] = "ARTIFACT_SUBTREE_V7_SUPPORT_RPC_FAILED"
        return report
    report["artifact_subtree_support"] = support
    report["support_probe_diagnostic"] = diagnostic
    if support != _EXPECTED_SUPPORT:
        report["preflight_error"] = "ARTIFACT_SUBTREE_V7_SUPPORT_NOT_PROVEN"
        return report
    report["support_probe_proven"] = True

    if preflight_only:
        report["characterization"] = "ARTIFACT_SUBTREE_V7_SUPPORT_PREFLIGHT_ONLY_PROVEN"
        report["ok"] = True
        return report

    report["surface_read_attempted"] = True
    try:
        snapshot, snapshot_diagnostic = provider.subtree_snapshot(timeout=min(timeout, 25.0))
    except Exception as exc:
        report["surface_read_error_type"] = type(exc).__name__
        return report
    report["artifact_subtree_snapshot"] = snapshot
    report["artifact_subtree_snapshot_diagnostic"] = snapshot_diagnostic
    if snapshot is None or snapshot_diagnostic.get("snapshot_contract_ok") is not True:
        return report

    placement_proven = bool(snapshot.get("probe_placement_proven"))
    identity = snapshot.get("artifact_subtree_identity_hit_count", 0) > 0
    locator = snapshot.get("artifact_subtree_locator_hit_count", 0) > 0
    strong = snapshot.get("strong_candidate_count", 0) > 0
    roots = snapshot.get("artifact_root_hit_count", 0) > 0

    report["experiment_valid"] = placement_proven
    report["artifact_structural_roots_observed"] = roots
    report["artifact_subtree_identity_key_names_observed"] = identity
    report["artifact_subtree_locator_key_names_observed"] = locator
    report["strong_artifact_subtree_candidate_observed"] = strong

    if not placement_proven:
        characterization = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif identity:
        characterization = "PROBE_ANCHORED_ARTIFACT_SUBTREE_IDENTITY_KEY_NAMES_OBSERVED"
    elif locator:
        characterization = "PROBE_ANCHORED_ARTIFACT_SUBTREE_LOCATOR_KEY_NAMES_OBSERVED"
    elif roots:
        characterization = "PROBE_ANCHORED_ARTIFACT_STRUCTURAL_ROOTS_ONLY"
    else:
        characterization = "PROBE_ANCHORED_NO_ARTIFACT_STRUCTURAL_ROOTS_OBSERVED"

    report["characterization"] = characterization
    report["ok"] = placement_proven
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PR10.1 targeted artifact-subtree v7 live gate")
    parser.add_argument("--expected-head", default=None)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.preflight_only and not args.acknowledge_live_read:
        raise SystemExit("live artifact-subtree read requires --acknowledge-live-read")
    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
