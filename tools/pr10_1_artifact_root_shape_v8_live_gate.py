from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


ARTIFACT_ROOT_SHAPE_SCHEMA = 8
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": ARTIFACT_ROOT_SHAPE_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "fiber_graph_bounded": True,
    "structural_artifact_roots_only": True,
    "dotted_localization_keys_excluded": True,
    "svg_use_fibers_excluded": True,
    "accessor_properties_skipped": True,
    "dom_state_node_values_excluded": True,
    "root_value_types_only": True,
    "root_cardinality_bucket_only": True,
    "root_values_exported": False,
    "child_values_exported": False,
    "raw_dom_exported": False,
    "raw_text_exported": False,
    "attribute_values_exported": False,
    "react_prop_values_exported": False,
    "react_state_values_exported": False,
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


def _safe_name_list(value: Any, *, max_items: int = 32) -> list[str]:
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
    source_container_kind = value.get("sourceContainerKind")
    if source_container_kind not in {"object", "array"}:
        source_container_kind = "object"
    root_value_kind = value.get("rootValueKind")
    if root_value_kind not in {
        "null", "undefined", "array", "object", "string", "number", "boolean",
        "bigint", "symbol", "function", "other",
    }:
        root_value_kind = "other"
    bucket = value.get("rootCardinalityBucket")
    if bucket not in {
        "zero", "one", "two_to_four", "five_to_sixteen", "over_sixteen",
        "not_applicable", "unknown",
    }:
        bucket = "unknown"
    return {
        "index": _safe_count(value.get("index"), maximum=32),
        "relation_kind": relation_kind,
        "fiber_depth": _safe_count(value.get("fiberDepth"), maximum=64),
        "component_name": _safe_name(value.get("componentName")) or "unknown",
        "source_kind": source_kind,
        "source_nested_depth": _safe_count(value.get("sourceNestedDepth"), maximum=5),
        "source_container_kind": source_container_kind,
        "artifact_root_key_name": _safe_name(value.get("artifactRootKeyName")) or "unknown",
        "root_value_kind": root_value_kind,
        "root_empty": value.get("rootEmpty") is True,
        "root_cardinality_bucket": bucket,
        "root_element_value_kinds": _safe_name_list(value.get("rootElementValueKinds"), max_items=12),
    }


class ProductArtifactRootShapeV8Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for PR10.1 artifact-root value-shape reads."""

    def _shape_rpc(self, flag: str, *, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
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

    def shape_support(self, *, timeout: float = 5.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._shape_rpc(
            "characterizeGeneratedArtifactRootShapeV8Support", timeout=timeout
        )
        fields = (
            "generatedArtifactRootShapeV8CharacterizationSupported",
            "generatedArtifactRootShapeV8CharacterizationSchemaVersion",
            "orderedProbePairRequired", "assistantTurnAnchorRequired", "fiberGraphBounded",
            "structuralArtifactRootsOnly", "dottedLocalizationKeysExcluded", "svgUseFibersExcluded",
            "accessorPropertiesSkipped", "domStateNodeValuesExcluded", "rootValueTypesOnly",
            "rootCardinalityBucketOnly", "rootValuesExported", "childValuesExported",
            "rawDomExported", "rawTextExported", "attributeValuesExported",
            "reactPropValuesExported", "reactStateValuesExported", "locatorValuesExported",
            "clickPerformed", "downloadAttempted", "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactRootShapeV8CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactRootShapeV8CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "root_value_types_only": response.get("rootValueTypesOnly"),
            "root_cardinality_bucket_only": response.get("rootCardinalityBucketOnly"),
            "root_values_exported": response.get("rootValuesExported"),
            "child_values_exported": response.get("childValuesExported"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
        }
        diagnostic["failure_reason"] = None if support == _EXPECTED_SUPPORT else "CONTRACT_MISMATCH"
        return support, diagnostic

    def shape_snapshot(self, *, timeout: float = 20.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        response, diagnostic = self._shape_rpc("characterizeGeneratedArtifactRootShapeV8", timeout=timeout)
        fields = (
            "schema", "runtimeTabPresent", "runtimeRouteKind", "runtimeConversationIdPresent",
            "surfaceReady", "selectorKind", "visibleTurnCount", "userProbeMarkerTurnCount",
            "assistantCompletionMarkerTurnCount", "orderedProbeTurnPairPresent", "probePlacementProven",
            "placementRoleEvidenceKinds", "fiberRootCount", "scannedFiberCount",
            "scannedSourceContainerCount", "artifactRootHitCount", "attachmentRootHitCount",
            "nullOrUndefinedRootCount", "emptyArrayRootCount", "nonemptyArrayRootCount",
            "emptyObjectRootCount", "nonemptyObjectRootCount", "scalarOrFunctionRootCount",
            "candidateSummaries", "fiberGraphBounded", "structuralArtifactRootsOnly",
            "dottedLocalizationKeysExcluded", "svgUseFibersExcluded", "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded", "rootValueTypesOnly", "rootCardinalityBucketOnly",
            "rootValuesExported", "childValuesExported", "rawDomExported", "rawTextExported",
            "attributeValuesExported", "reactPropValuesExported", "reactStateValuesExported",
            "locatorValuesExported", "clickPerformed", "downloadAttempted", "writePerformed",
            "debuggerAttachedAfter",
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
        if route_kind not in {"absent", "root", "conversation", "chatgpt_other", "not_chatgpt", "invalid"}:
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
            "assistant_completion_marker_turn_count": _safe_count(response.get("assistantCompletionMarkerTurnCount"), maximum=64),
            "ordered_probe_turn_pair_present": response.get("orderedProbeTurnPairPresent") is True,
            "probe_placement_proven": response.get("probePlacementProven") is True,
            "placement_role_evidence_kinds": _safe_name_list(response.get("placementRoleEvidenceKinds"), max_items=8),
            "fiber_root_count": _safe_count(response.get("fiberRootCount"), maximum=4),
            "scanned_fiber_count": _safe_count(response.get("scannedFiberCount"), maximum=4096),
            "scanned_source_container_count": _safe_count(response.get("scannedSourceContainerCount"), maximum=200000),
            "artifact_root_hit_count": _safe_count(response.get("artifactRootHitCount"), maximum=4096),
            "attachment_root_hit_count": _safe_count(response.get("attachmentRootHitCount"), maximum=4096),
            "null_or_undefined_root_count": _safe_count(response.get("nullOrUndefinedRootCount"), maximum=4096),
            "empty_array_root_count": _safe_count(response.get("emptyArrayRootCount"), maximum=4096),
            "nonempty_array_root_count": _safe_count(response.get("nonemptyArrayRootCount"), maximum=4096),
            "empty_object_root_count": _safe_count(response.get("emptyObjectRootCount"), maximum=4096),
            "nonempty_object_root_count": _safe_count(response.get("nonemptyObjectRootCount"), maximum=4096),
            "scalar_or_function_root_count": _safe_count(response.get("scalarOrFunctionRootCount"), maximum=4096),
            "candidate_summaries": candidates,
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "root_value_types_only": response.get("rootValueTypesOnly"),
            "root_cardinality_bucket_only": response.get("rootCardinalityBucketOnly"),
            "root_values_exported": response.get("rootValuesExported"),
            "child_values_exported": response.get("childValuesExported"),
            "raw_dom_exported": response.get("rawDomExported"),
            "raw_text_exported": response.get("rawTextExported"),
            "attribute_values_exported": response.get("attributeValuesExported"),
            "react_prop_values_exported": response.get("reactPropValuesExported"),
            "react_state_values_exported": response.get("reactStateValuesExported"),
            "locator_values_exported": response.get("locatorValuesExported"),
            "click_performed": response.get("clickPerformed"),
            "download_attempted": response.get("downloadAttempted"),
            "write_performed": response.get("writePerformed"),
            "debugger_attached_after": response.get("debuggerAttachedAfter"),
        }
        contract_ok = bool(
            snapshot["schema"] == ARTIFACT_ROOT_SHAPE_SCHEMA
            and snapshot["fiber_graph_bounded"] is True
            and snapshot["structural_artifact_roots_only"] is True
            and snapshot["dotted_localization_keys_excluded"] is True
            and snapshot["svg_use_fibers_excluded"] is True
            and snapshot["accessor_properties_skipped"] is True
            and snapshot["dom_state_node_values_excluded"] is True
            and snapshot["root_value_types_only"] is True
            and snapshot["root_cardinality_bucket_only"] is True
            and snapshot["root_values_exported"] is False
            and snapshot["child_values_exported"] is False
            and snapshot["raw_dom_exported"] is False
            and snapshot["raw_text_exported"] is False
            and snapshot["attribute_values_exported"] is False
            and snapshot["react_prop_values_exported"] is False
            and snapshot["react_state_values_exported"] is False
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
    head = _git_output("rev-parse", "HEAD")
    clean = _tracked_clean()
    head_matches = expected_head is None or head == expected_head
    provider = ProductArtifactRootShapeV8Provider()

    support_probe_attempted = False
    surface_read_attempted = False
    support = None
    support_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}
    snapshot = None
    snapshot_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}

    support_probe_attempted = True
    try:
        support, support_diagnostic = provider.shape_support(timeout=min(timeout, 5.0))
    except Exception as exc:  # noqa: BLE001
        support_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}

    support_proven = bool(support == _EXPECTED_SUPPORT and support_diagnostic.get("failure_reason") is None)
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_ROOT_SHAPE_V8_LIVE_GATE_V1",
        "expected_head": expected_head,
        "head": head,
        "head_matches": head_matches,
        "tracked_clean": clean,
        "preflight_only": preflight_only,
        "artifact_root_shape_schema": ARTIFACT_ROOT_SHAPE_SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "surface_read_budget": 0 if preflight_only else SURFACE_READ_BUDGET,
        "download_budget": DOWNLOAD_BUDGET,
        "local_write_budget": LOCAL_WRITE_BUDGET,
        "support_probe_attempted": support_probe_attempted,
        "support_probe_proven": support_proven,
        "artifact_root_shape_support": support,
        "support_probe_diagnostic": support_diagnostic,
        "surface_read_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_dom_exported": False,
        "raw_text_exported": False,
        "attribute_values_exported": False,
        "react_prop_values_exported": False,
        "react_state_values_exported": False,
        "root_values_exported": False,
        "child_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
    }

    if preflight_only:
        report["characterization"] = (
            "ARTIFACT_ROOT_SHAPE_V8_SUPPORT_PREFLIGHT_ONLY_PROVEN"
            if support_proven and head_matches and clean
            else "ARTIFACT_ROOT_SHAPE_V8_SUPPORT_PREFLIGHT_FAILED"
        )
        report["ok"] = bool(support_proven and head_matches and clean)
        return report

    if not (support_proven and head_matches and clean):
        report["characterization"] = "ARTIFACT_ROOT_SHAPE_V8_LIVE_PREFLIGHT_NOT_PROVEN"
        report["ok"] = False
        return report

    surface_read_attempted = True
    try:
        snapshot, snapshot_diagnostic = provider.shape_snapshot(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        snapshot_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}

    report["surface_read_attempted"] = surface_read_attempted
    report["artifact_root_shape_snapshot"] = snapshot
    report["artifact_root_shape_snapshot_diagnostic"] = snapshot_diagnostic
    placement_proven = bool(
        snapshot
        and snapshot_diagnostic.get("failure_reason") is None
        and snapshot.get("probe_placement_proven") is True
        and snapshot.get("ordered_probe_turn_pair_present") is True
    )
    artifact_root_count = int(snapshot.get("artifact_root_hit_count", 0)) if snapshot else 0
    empty_like_count = (
        int(snapshot.get("null_or_undefined_root_count", 0))
        + int(snapshot.get("empty_array_root_count", 0))
        + int(snapshot.get("empty_object_root_count", 0))
        if snapshot else 0
    )
    nonempty_container_count = (
        int(snapshot.get("nonempty_array_root_count", 0))
        + int(snapshot.get("nonempty_object_root_count", 0))
        if snapshot else 0
    )
    scalar_count = int(snapshot.get("scalar_or_function_root_count", 0)) if snapshot else 0
    empty_or_null_only = bool(artifact_root_count > 0 and empty_like_count == artifact_root_count)
    nonempty_artifact_root_observed = bool(nonempty_container_count > 0)

    report["artifact_root_shape_observed"] = artifact_root_count > 0
    report["artifact_root_empty_or_null_only"] = empty_or_null_only
    report["nonempty_artifact_root_observed"] = nonempty_artifact_root_observed
    report["scalar_artifact_root_observed"] = scalar_count > 0

    if not placement_proven:
        characterization = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif artifact_root_count == 0:
        characterization = "PROBE_ANCHORED_NO_ARTIFACT_ROOT_SHAPE_OBSERVED"
    elif empty_or_null_only:
        characterization = "PROBE_ANCHORED_ARTIFACT_ROOT_VALUES_EMPTY_OR_NULL"
    elif nonempty_artifact_root_observed:
        characterization = "PROBE_ANCHORED_NONEMPTY_ARTIFACT_ROOT_SHAPE_OBSERVED"
    elif scalar_count > 0:
        characterization = "PROBE_ANCHORED_SCALAR_ARTIFACT_ROOT_SHAPE_OBSERVED"
    else:
        characterization = "PROBE_ANCHORED_MIXED_ARTIFACT_ROOT_SHAPE_OBSERVED"

    report["characterization"] = characterization
    report["ok"] = placement_proven
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PR10.1 artifact-root value-shape v8 live gate")
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.preflight_only and not args.acknowledge_live_read:
        raise SystemExit("live read requires --acknowledge-live-read")
    report = run_gate(
        expected_head=args.expected_head,
        timeout=args.timeout,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
