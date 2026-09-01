from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


ARTIFACT_ROOT_KEY_SHAPE_SCHEMA = 9
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": ARTIFACT_ROOT_KEY_SHAPE_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "fiber_graph_bounded": True,
    "structural_artifact_roots_only": True,
    "nonempty_roots_only": True,
    "dotted_localization_keys_excluded": True,
    "svg_use_fibers_excluded": True,
    "accessor_properties_skipped": True,
    "dom_state_node_values_excluded": True,
    "key_shape_classification_only": True,
    "known_structural_key_whitelist_only": True,
    "raw_root_keys_exported": False,
    "raw_root_values_exported": False,
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

_KEY_SHAPES = {
    "known_structural", "numeric", "uuid_like", "file_prefixed_token",
    "artifact_prefixed_token", "hex_like", "opaque_token", "semantic_identifier", "other",
}
_VALUE_KINDS = {
    "null", "undefined", "array", "object", "string", "number", "boolean",
    "bigint", "symbol", "function", "other",
}
_BUCKETS = {"zero", "one", "two_to_four", "five_to_sixteen", "over_sixteen", "not_applicable", "unknown"}
_LENGTH_BUCKETS = {"up_to_8", "nine_to_sixteen", "seventeen_to_thirty_two", "thirty_three_to_sixty_four", "over_sixty_four"}
_OBJECT_KINDS = {"array", "not_object", "null_prototype", "plain_object", "other_object"}


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


def _safe_fixed_counts(value: Any, keys: set[str]) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {key: _safe_count(source.get(key), maximum=4096) for key in sorted(keys)}


def _safe_child(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    key_shape = value.get("keyShape") if value.get("keyShape") in _KEY_SHAPES else "other"
    key_length_bucket = value.get("keyLengthBucket") if value.get("keyLengthBucket") in _LENGTH_BUCKETS else "over_sixty_four"
    child_value_kind = value.get("childValueKind") if value.get("childValueKind") in _VALUE_KINDS else "other"
    child_bucket = value.get("childCardinalityBucket") if value.get("childCardinalityBucket") in _BUCKETS else "unknown"
    child_object_kind = value.get("childPlainObjectKind") if value.get("childPlainObjectKind") in _OBJECT_KINDS else "other_object"
    return {
        "key_shape": key_shape,
        "key_length_bucket": key_length_bucket,
        "known_structural_key_name": _safe_name(value.get("knownStructuralKeyName")),
        "child_value_kind": child_value_kind,
        "child_cardinality_bucket": child_bucket,
        "child_plain_object_kind": child_object_kind,
    }


def _safe_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    relation_kind = value.get("relationKind")
    if relation_kind not in {"turn_root", "turn_ancestor", "turn_descendant"}:
        relation_kind = "turn_descendant"
    source_kind = value.get("sourceKind")
    if source_kind not in {"memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"}:
        source_kind = "memoized_state"
    source_container_kind = value.get("sourceContainerKind")
    if source_container_kind not in {"object", "array"}:
        source_container_kind = "object"
    root_value_kind = value.get("rootValueKind") if value.get("rootValueKind") in {"object", "array"} else "object"
    root_bucket = value.get("rootCardinalityBucket") if value.get("rootCardinalityBucket") in _BUCKETS else "unknown"
    root_object_kind = value.get("rootPlainObjectKind") if value.get("rootPlainObjectKind") in _OBJECT_KINDS else "other_object"
    traversable_bucket = value.get("traversableChildCountBucket") if value.get("traversableChildCountBucket") in _BUCKETS else "unknown"
    children: list[dict[str, Any]] = []
    raw_children = value.get("childSummaries")
    if isinstance(raw_children, list):
        for raw_child in raw_children[:8]:
            child = _safe_child(raw_child)
            if child is not None:
                children.append(child)
    return {
        "index": _safe_count(value.get("index"), maximum=16),
        "relation_kind": relation_kind,
        "fiber_depth": _safe_count(value.get("fiberDepth"), maximum=64),
        "component_name": _safe_name(value.get("componentName")) or "unknown",
        "source_kind": source_kind,
        "source_nested_depth": _safe_count(value.get("sourceNestedDepth"), maximum=5),
        "source_container_kind": source_container_kind,
        "artifact_root_key_name": _safe_name(value.get("artifactRootKeyName")) or "unknown",
        "root_value_kind": root_value_kind,
        "root_cardinality_bucket": root_bucket,
        "root_plain_object_kind": root_object_kind,
        "known_structural_child_key_names": _safe_name_list(value.get("knownStructuralChildKeyNames"), max_items=24),
        "key_shape_counts": _safe_fixed_counts(value.get("keyShapeCounts"), _KEY_SHAPES),
        "child_value_kind_counts": _safe_fixed_counts(value.get("childValueKindCounts"), _VALUE_KINDS),
        "traversable_child_count_bucket": traversable_bucket,
        "child_summaries": children,
    }


class ProductArtifactRootKeyShapeV9Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for non-empty artifact-root key/value shape reads."""

    def _shape_rpc(self, flag: str, *, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc({"type": "turn", "request_id": request_id, flag: True, "timeoutMs": int(timeout * 1000)}, timeout=timeout)
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
        response, diagnostic = self._shape_rpc("characterizeGeneratedArtifactRootKeyShapeV9Support", timeout=timeout)
        fields = (
            "generatedArtifactRootKeyShapeV9CharacterizationSupported", "generatedArtifactRootKeyShapeV9CharacterizationSchemaVersion",
            "orderedProbePairRequired", "assistantTurnAnchorRequired", "fiberGraphBounded", "structuralArtifactRootsOnly",
            "nonemptyRootsOnly", "dottedLocalizationKeysExcluded", "svgUseFibersExcluded", "accessorPropertiesSkipped",
            "domStateNodeValuesExcluded", "keyShapeClassificationOnly", "knownStructuralKeyWhitelistOnly", "rawRootKeysExported",
            "rawRootValuesExported", "childValuesExported", "rawDomExported", "rawTextExported", "attributeValuesExported",
            "reactPropValuesExported", "reactStateValuesExported", "locatorValuesExported", "clickPerformed", "downloadAttempted", "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactRootKeyShapeV9CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactRootKeyShapeV9CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "nonempty_roots_only": response.get("nonemptyRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "key_shape_classification_only": response.get("keyShapeClassificationOnly"),
            "known_structural_key_whitelist_only": response.get("knownStructuralKeyWhitelistOnly"),
            "raw_root_keys_exported": response.get("rawRootKeysExported"),
            "raw_root_values_exported": response.get("rawRootValuesExported"),
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
        response, diagnostic = self._shape_rpc("characterizeGeneratedArtifactRootKeyShapeV9", timeout=timeout)
        required = (
            "schema", "runtimeTabPresent", "runtimeRouteKind", "runtimeConversationIdPresent", "surfaceReady", "selectorKind",
            "visibleTurnCount", "userProbeMarkerTurnCount", "assistantCompletionMarkerTurnCount", "orderedProbeTurnPairPresent",
            "probePlacementProven", "placementRoleEvidenceKinds", "fiberRootCount", "scannedFiberCount", "scannedSourceContainerCount",
            "nonemptyArtifactRootCount", "nonemptyAttachmentRootCount", "objectRootCount", "arrayRootCount", "identityAsKeyCandidateCount",
            "knownStructuralKeyHitCount", "recordLikeIdentityKeyChildCount", "candidateSummaries", "fiberGraphBounded",
            "structuralArtifactRootsOnly", "nonemptyRootsOnly", "dottedLocalizationKeysExcluded", "svgUseFibersExcluded",
            "accessorPropertiesSkipped", "domStateNodeValuesExcluded", "keyShapeClassificationOnly", "knownStructuralKeyWhitelistOnly",
            "rawRootKeysExported", "rawRootValuesExported", "childValuesExported", "rawDomExported", "rawTextExported",
            "attributeValuesExported", "reactPropValuesExported", "reactStateValuesExported", "locatorValuesExported", "clickPerformed",
            "downloadAttempted", "writePerformed", "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in required)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        candidates: list[dict[str, Any]] = []
        raw_candidates = response.get("candidateSummaries")
        if isinstance(raw_candidates, list):
            for item in raw_candidates[:16]:
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
            "nonempty_artifact_root_count": _safe_count(response.get("nonemptyArtifactRootCount"), maximum=4096),
            "nonempty_attachment_root_count": _safe_count(response.get("nonemptyAttachmentRootCount"), maximum=4096),
            "object_root_count": _safe_count(response.get("objectRootCount"), maximum=4096),
            "array_root_count": _safe_count(response.get("arrayRootCount"), maximum=4096),
            "identity_as_key_candidate_count": _safe_count(response.get("identityAsKeyCandidateCount"), maximum=4096),
            "known_structural_key_hit_count": _safe_count(response.get("knownStructuralKeyHitCount"), maximum=4096),
            "record_like_identity_key_child_count": _safe_count(response.get("recordLikeIdentityKeyChildCount"), maximum=4096),
            "candidate_summaries": candidates,
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "structural_artifact_roots_only": response.get("structuralArtifactRootsOnly"),
            "nonempty_roots_only": response.get("nonemptyRootsOnly"),
            "dotted_localization_keys_excluded": response.get("dottedLocalizationKeysExcluded"),
            "svg_use_fibers_excluded": response.get("svgUseFibersExcluded"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "key_shape_classification_only": response.get("keyShapeClassificationOnly"),
            "known_structural_key_whitelist_only": response.get("knownStructuralKeyWhitelistOnly"),
            "raw_root_keys_exported": response.get("rawRootKeysExported"),
            "raw_root_values_exported": response.get("rawRootValuesExported"),
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
            snapshot["schema"] == ARTIFACT_ROOT_KEY_SHAPE_SCHEMA
            and snapshot["fiber_graph_bounded"] is True
            and snapshot["structural_artifact_roots_only"] is True
            and snapshot["nonempty_roots_only"] is True
            and snapshot["dotted_localization_keys_excluded"] is True
            and snapshot["svg_use_fibers_excluded"] is True
            and snapshot["accessor_properties_skipped"] is True
            and snapshot["dom_state_node_values_excluded"] is True
            and snapshot["key_shape_classification_only"] is True
            and snapshot["known_structural_key_whitelist_only"] is True
            and snapshot["raw_root_keys_exported"] is False
            and snapshot["raw_root_values_exported"] is False
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
    provider = ProductArtifactRootKeyShapeV9Provider()
    support = None
    support_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}
    try:
        support, support_diagnostic = provider.shape_support(timeout=min(timeout, 5.0))
    except Exception as exc:  # noqa: BLE001
        support_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}
    support_proven = bool(support == _EXPECTED_SUPPORT and support_diagnostic.get("failure_reason") is None)
    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_ROOT_KEY_SHAPE_V9_LIVE_GATE_V1",
        "expected_head": expected_head,
        "head": head,
        "head_matches": head_matches,
        "tracked_clean": clean,
        "preflight_only": preflight_only,
        "artifact_root_key_shape_schema": ARTIFACT_ROOT_KEY_SHAPE_SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "surface_read_budget": 0 if preflight_only else SURFACE_READ_BUDGET,
        "download_budget": DOWNLOAD_BUDGET,
        "local_write_budget": LOCAL_WRITE_BUDGET,
        "support_probe_attempted": True,
        "support_probe_proven": support_proven,
        "artifact_root_key_shape_support": support,
        "support_probe_diagnostic": support_diagnostic,
        "surface_read_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_root_keys_exported": False,
        "raw_root_values_exported": False,
        "child_values_exported": False,
        "raw_dom_exported": False,
        "raw_text_exported": False,
        "attribute_values_exported": False,
        "react_prop_values_exported": False,
        "react_state_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
    }
    if preflight_only:
        report["characterization"] = "ARTIFACT_ROOT_KEY_SHAPE_V9_SUPPORT_PREFLIGHT_ONLY_PROVEN" if support_proven and head_matches and clean else "ARTIFACT_ROOT_KEY_SHAPE_V9_SUPPORT_PREFLIGHT_FAILED"
        report["ok"] = bool(support_proven and head_matches and clean)
        return report
    if not (support_proven and head_matches and clean):
        report["characterization"] = "ARTIFACT_ROOT_KEY_SHAPE_V9_LIVE_PREFLIGHT_NOT_PROVEN"
        report["ok"] = False
        return report
    snapshot = None
    snapshot_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}
    try:
        snapshot, snapshot_diagnostic = provider.shape_snapshot(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        snapshot_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}
    report["surface_read_attempted"] = True
    report["artifact_root_key_shape_snapshot"] = snapshot
    report["artifact_root_key_shape_snapshot_diagnostic"] = snapshot_diagnostic
    placement_proven = bool(snapshot and snapshot_diagnostic.get("failure_reason") is None and snapshot.get("probe_placement_proven") is True and snapshot.get("ordered_probe_turn_pair_present") is True)
    root_count = int(snapshot.get("nonempty_artifact_root_count", 0)) if snapshot else 0
    identity_as_key_count = int(snapshot.get("identity_as_key_candidate_count", 0)) if snapshot else 0
    record_like_count = int(snapshot.get("record_like_identity_key_child_count", 0)) if snapshot else 0
    structural_count = int(snapshot.get("known_structural_key_hit_count", 0)) if snapshot else 0
    report["nonempty_artifact_root_observed"] = root_count > 0
    report["identity_as_key_candidate_observed"] = identity_as_key_count > 0
    report["record_like_identity_as_key_candidate_observed"] = record_like_count > 0
    report["known_structural_schema_observed"] = structural_count > 0
    if not placement_proven:
        characterization = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif root_count == 0:
        characterization = "PROBE_ANCHORED_NO_NONEMPTY_ARTIFACT_ROOT_KEY_SHAPE_OBSERVED"
    elif record_like_count > 0:
        characterization = "PROBE_ANCHORED_RECORD_LIKE_IDENTITY_AS_KEY_SHAPE_OBSERVED"
    elif identity_as_key_count > 0:
        characterization = "PROBE_ANCHORED_IDENTITY_AS_KEY_SHAPE_CANDIDATE_OBSERVED"
    elif structural_count > 0:
        characterization = "PROBE_ANCHORED_KNOWN_STRUCTURAL_ARTIFACT_ROOT_SCHEMA_OBSERVED"
    else:
        characterization = "PROBE_ANCHORED_GENERIC_NONEMPTY_ARTIFACT_ROOT_SCHEMA_OBSERVED"
    report["characterization"] = characterization
    report["ok"] = placement_proven
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PR10.1 artifact-root key/value shape v9 live gate")
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--acknowledge-live-read", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.preflight_only and not args.acknowledge_live_read:
        raise SystemExit("live read requires --acknowledge-live-read")
    report = run_gate(expected_head=args.expected_head, timeout=args.timeout, preflight_only=args.preflight_only)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
