from __future__ import annotations

import argparse
import json
from typing import Any
import uuid

from pr10_1_artifact_live_gate import ProductArtifactLiveProvider, _git_output, _tracked_clean


ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA = 10
PRODUCT_WRITE_BUDGET = 0
SURFACE_READ_BUDGET = 1
DOWNLOAD_BUDGET = 0
LOCAL_WRITE_BUDGET = 0

_EXPECTED_SUPPORT = {
    "supported": True,
    "schema": ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA,
    "ordered_probe_pair_required": True,
    "assistant_turn_anchor_required": True,
    "fiber_graph_bounded": True,
    "attachment_roots_only": True,
    "nonempty_attachment_roots_only": True,
    "opaque_array_children_only": True,
    "array_elements_bounded": True,
    "element_value_types_only": True,
    "string_element_shape_classification_only": True,
    "known_structural_key_whitelist_only": True,
    "accessor_properties_skipped": True,
    "dom_state_node_values_excluded": True,
    "raw_attachment_child_keys_exported": False,
    "raw_array_element_values_exported": False,
    "raw_string_values_exported": False,
    "raw_root_values_exported": False,
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

_VALUE_KINDS = {
    "null", "undefined", "array", "object", "string", "number", "boolean",
    "bigint", "symbol", "function", "other",
}
_STRING_SHAPES = {
    "empty", "uuid_like", "file_prefixed_token", "artifact_prefixed_token",
    "hex_like", "opaque_token", "semantic_identifier", "other",
}
_LENGTH_BUCKETS = {
    "zero", "up_to_8", "nine_to_sixteen", "seventeen_to_thirty_two",
    "thirty_three_to_sixty_four", "over_sixty_four",
}
_CARDINALITY_BUCKETS = {"zero", "one", "two_to_four", "five_to_sixteen", "over_sixteen", "unknown"}
_KEY_LENGTH_BUCKETS = {
    "up_to_8", "nine_to_sixteen", "seventeen_to_thirty_two",
    "thirty_three_to_sixty_four", "over_sixty_four",
}
_STRUCTURAL_KEYS = {
    "id", "type", "kind", "name", "filename", "fileName", "mimeType", "mediaType", "size", "sizeBytes", "status",
    "items", "byId", "allIds", "data", "value", "current", "payload", "state", "metadata", "records", "entities",
    "nodes", "edges", "list", "map", "attachment", "attachments", "file", "files", "artifact", "artifacts",
    "asset", "assets", "content",
}
_IDENTITY_KEYS = {
    "id", "fileId", "file_id", "artifactId", "artifact_id", "assetId", "asset_id",
    "attachmentId", "attachment_id", "generatedFileId", "generated_file_id",
}
_LOCATOR_KEYS = {
    "href", "url", "uri", "download", "downloadUrl", "download_url", "downloadUri", "download_uri",
    "signedUrl", "signed_url", "assetPointer", "asset_pointer",
}


def _wire_value(value: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in value:
        return value.get(camel)
    return value.get(snake)


def _safe_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 80 or not text.isascii():
        return None
    if not all(ch.isalnum() or ch in "_.:-" for ch in text):
        return None
    return text


def _safe_count(value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, maximum)


def _safe_fixed_counts(value: Any, keys: set[str], *, maximum: int = 64) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {key: _safe_count(source.get(key), maximum=maximum) for key in sorted(keys)}


def _safe_whitelist_list(value: Any, allowed: set[str], *, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        name = _safe_name(item)
        if name is None or name not in allowed:
            continue
        output.append(name)
        if len(output) >= max_items:
            break
    return sorted(set(output))


def _safe_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    relation_kind = _wire_value(value, "relationKind", "relation_kind")
    if relation_kind not in {"turn_root", "turn_ancestor", "turn_descendant"}:
        relation_kind = "turn_descendant"
    source_kind = _wire_value(value, "sourceKind", "source_kind")
    if source_kind not in {"memoized_props", "pending_props", "memoized_state", "update_queue", "dependencies"}:
        source_kind = "memoized_state"
    source_container_kind = _wire_value(value, "sourceContainerKind", "source_container_kind")
    if source_container_kind not in {"object", "array"}:
        source_container_kind = "object"
    root_name = _wire_value(value, "artifactRootKeyName", "artifact_root_key_name")
    if root_name not in {"attachment", "attachments"}:
        root_name = "attachments"
    child_key_shape = _wire_value(value, "childKeyShape", "child_key_shape")
    if child_key_shape != "opaque_token":
        child_key_shape = "opaque_token"
    child_key_length = _wire_value(value, "childKeyLengthBucket", "child_key_length_bucket")
    if child_key_length not in _KEY_LENGTH_BUCKETS:
        child_key_length = "over_sixty_four"
    array_bucket = _wire_value(value, "arrayCardinalityBucket", "array_cardinality_bucket")
    if array_bucket not in _CARDINALITY_BUCKETS:
        array_bucket = "unknown"

    return {
        "relation_kind": relation_kind,
        "fiber_depth": _safe_count(_wire_value(value, "fiberDepth", "fiber_depth"), maximum=64),
        "component_name": _safe_name(_wire_value(value, "componentName", "component_name")) or "unknown",
        "source_kind": source_kind,
        "source_nested_depth": _safe_count(
            _wire_value(value, "sourceNestedDepth", "source_nested_depth"), maximum=5
        ),
        "source_container_kind": source_container_kind,
        "artifact_root_key_name": root_name,
        "child_key_shape": child_key_shape,
        "child_key_length_bucket": child_key_length,
        "array_cardinality_bucket": array_bucket,
        "elements_scanned_count": _safe_count(
            _wire_value(value, "elementsScannedCount", "elements_scanned_count"), maximum=64
        ),
        "element_value_kind_counts": _safe_fixed_counts(
            _wire_value(value, "elementValueKindCounts", "element_value_kind_counts"), _VALUE_KINDS
        ),
        "string_element_shape_counts": _safe_fixed_counts(
            _wire_value(value, "stringElementShapeCounts", "string_element_shape_counts"), _STRING_SHAPES
        ),
        "string_element_length_bucket_counts": _safe_fixed_counts(
            _wire_value(value, "stringElementLengthBucketCounts", "string_element_length_bucket_counts"),
            _LENGTH_BUCKETS,
        ),
        "traversable_object_element_count": _safe_count(
            _wire_value(value, "traversableObjectElementCount", "traversable_object_element_count"), maximum=64
        ),
        "plain_object_element_count": _safe_count(
            _wire_value(value, "plainObjectElementCount", "plain_object_element_count"), maximum=64
        ),
        "known_structural_element_key_names": _safe_whitelist_list(
            _wire_value(value, "knownStructuralElementKeyNames", "known_structural_element_key_names"),
            _STRUCTURAL_KEYS,
            max_items=32,
        ),
        "identity_like_element_key_names": _safe_whitelist_list(
            _wire_value(value, "identityLikeElementKeyNames", "identity_like_element_key_names"),
            _IDENTITY_KEYS,
            max_items=16,
        ),
        "locator_like_element_key_names": _safe_whitelist_list(
            _wire_value(value, "locatorLikeElementKeyNames", "locator_like_element_key_names"),
            _LOCATOR_KEYS,
            max_items=16,
        ),
    }


class ProductArtifactArrayElementShapeV10Provider(ProductArtifactLiveProvider):
    """Bounded no-write provider for attachment opaque-array element shape reads."""

    def _shape_rpc(self, flag: str, *, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {"type": "turn", "request_id": request_id, flag: True, "timeoutMs": int(timeout * 1000)},
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
            "characterizeGeneratedArtifactArrayElementShapeV10Support", timeout=timeout
        )
        fields = (
            "generatedArtifactArrayElementShapeV10CharacterizationSupported",
            "generatedArtifactArrayElementShapeV10CharacterizationSchemaVersion",
            "orderedProbePairRequired", "assistantTurnAnchorRequired", "fiberGraphBounded",
            "attachmentRootsOnly", "nonemptyAttachmentRootsOnly", "opaqueArrayChildrenOnly",
            "arrayElementsBounded", "elementValueTypesOnly", "stringElementShapeClassificationOnly",
            "knownStructuralKeyWhitelistOnly", "accessorPropertiesSkipped", "domStateNodeValuesExcluded",
            "rawAttachmentChildKeysExported", "rawArrayElementValuesExported", "rawStringValuesExported",
            "rawRootValuesExported", "rawDomExported", "rawTextExported", "attributeValuesExported",
            "reactPropValuesExported", "reactStateValuesExported", "locatorValuesExported",
            "clickPerformed", "downloadAttempted", "writePerformed",
        )
        diagnostic["support_fields_present"] = all(key in response for key in fields)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic
        support = {
            "supported": response.get("generatedArtifactArrayElementShapeV10CharacterizationSupported") is True,
            "schema": response.get("generatedArtifactArrayElementShapeV10CharacterizationSchemaVersion"),
            "ordered_probe_pair_required": response.get("orderedProbePairRequired"),
            "assistant_turn_anchor_required": response.get("assistantTurnAnchorRequired"),
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "attachment_roots_only": response.get("attachmentRootsOnly"),
            "nonempty_attachment_roots_only": response.get("nonemptyAttachmentRootsOnly"),
            "opaque_array_children_only": response.get("opaqueArrayChildrenOnly"),
            "array_elements_bounded": response.get("arrayElementsBounded"),
            "element_value_types_only": response.get("elementValueTypesOnly"),
            "string_element_shape_classification_only": response.get("stringElementShapeClassificationOnly"),
            "known_structural_key_whitelist_only": response.get("knownStructuralKeyWhitelistOnly"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_attachment_child_keys_exported": response.get("rawAttachmentChildKeysExported"),
            "raw_array_element_values_exported": response.get("rawArrayElementValuesExported"),
            "raw_string_values_exported": response.get("rawStringValuesExported"),
            "raw_root_values_exported": response.get("rawRootValuesExported"),
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
        response, diagnostic = self._shape_rpc(
            "characterizeGeneratedArtifactArrayElementShapeV10", timeout=timeout
        )
        required = (
            "schema", "runtimeTabPresent", "runtimeRouteKind", "runtimeConversationIdPresent",
            "surfaceReady", "selectorKind", "visibleTurnCount", "userProbeMarkerTurnCount",
            "assistantCompletionMarkerTurnCount", "orderedProbeTurnPairPresent", "probePlacementProven",
            "placementRoleEvidenceKinds", "fiberRootCount", "scannedFiberCount", "scannedSourceContainerCount",
            "nonemptyAttachmentRootCount", "opaqueArrayChildCount", "totalArrayElementsScannedCount",
            "arrayWithObjectElementCount", "arrayWithTokenStringElementCount", "arrayWithIdentityKeySchemaCount",
            "arrayWithLocatorKeySchemaCount", "arrayCandidateSummaries", "fiberGraphBounded", "attachmentRootsOnly",
            "nonemptyAttachmentRootsOnly", "opaqueArrayChildrenOnly", "arrayElementsBounded",
            "elementValueTypesOnly", "stringElementShapeClassificationOnly", "knownStructuralKeyWhitelistOnly",
            "accessorPropertiesSkipped", "domStateNodeValuesExcluded", "rawAttachmentChildKeysExported",
            "rawArrayElementValuesExported", "rawStringValuesExported", "rawRootValuesExported",
            "rawDomExported", "rawTextExported", "attributeValuesExported", "reactPropValuesExported",
            "reactStateValuesExported", "locatorValuesExported", "clickPerformed", "downloadAttempted",
            "writePerformed", "debuggerAttachedAfter",
        )
        diagnostic["snapshot_fields_present"] = all(key in response for key in required)
        if diagnostic["failure_reason"] is not None:
            return None, diagnostic

        route_kind = response.get("runtimeRouteKind")
        if route_kind not in {"absent", "root", "conversation", "chatgpt_other", "not_chatgpt", "invalid"}:
            route_kind = "invalid"
        selector_kind = response.get("selectorKind")
        if selector_kind not in {"none", "conversation_testid", "article_fallback"}:
            selector_kind = "none"

        candidates: list[dict[str, Any]] = []
        raw_candidates = response.get("arrayCandidateSummaries")
        if isinstance(raw_candidates, list):
            for item in raw_candidates[:8]:
                candidate = _safe_candidate(item)
                if candidate is not None:
                    candidates.append(candidate)

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
            "placement_role_evidence_kinds": _safe_whitelist_list(
                response.get("placementRoleEvidenceKinds"),
                {"data_turn", "direct_message_author_role", "nested_message_author_role"},
                max_items=8,
            ),
            "fiber_root_count": _safe_count(response.get("fiberRootCount"), maximum=4),
            "scanned_fiber_count": _safe_count(response.get("scannedFiberCount"), maximum=4096),
            "scanned_source_container_count": _safe_count(
                response.get("scannedSourceContainerCount"), maximum=200000
            ),
            "nonempty_attachment_root_count": _safe_count(
                response.get("nonemptyAttachmentRootCount"), maximum=4096
            ),
            "opaque_array_child_count": _safe_count(response.get("opaqueArrayChildCount"), maximum=4096),
            "total_array_elements_scanned_count": _safe_count(
                response.get("totalArrayElementsScannedCount"), maximum=512
            ),
            "array_with_object_element_count": _safe_count(
                response.get("arrayWithObjectElementCount"), maximum=4096
            ),
            "array_with_token_string_element_count": _safe_count(
                response.get("arrayWithTokenStringElementCount"), maximum=4096
            ),
            "array_with_identity_key_schema_count": _safe_count(
                response.get("arrayWithIdentityKeySchemaCount"), maximum=4096
            ),
            "array_with_locator_key_schema_count": _safe_count(
                response.get("arrayWithLocatorKeySchemaCount"), maximum=4096
            ),
            "array_candidate_summaries": candidates,
            "fiber_graph_bounded": response.get("fiberGraphBounded"),
            "attachment_roots_only": response.get("attachmentRootsOnly"),
            "nonempty_attachment_roots_only": response.get("nonemptyAttachmentRootsOnly"),
            "opaque_array_children_only": response.get("opaqueArrayChildrenOnly"),
            "array_elements_bounded": response.get("arrayElementsBounded"),
            "element_value_types_only": response.get("elementValueTypesOnly"),
            "string_element_shape_classification_only": response.get("stringElementShapeClassificationOnly"),
            "known_structural_key_whitelist_only": response.get("knownStructuralKeyWhitelistOnly"),
            "accessor_properties_skipped": response.get("accessorPropertiesSkipped"),
            "dom_state_node_values_excluded": response.get("domStateNodeValuesExcluded"),
            "raw_attachment_child_keys_exported": response.get("rawAttachmentChildKeysExported"),
            "raw_array_element_values_exported": response.get("rawArrayElementValuesExported"),
            "raw_string_values_exported": response.get("rawStringValuesExported"),
            "raw_root_values_exported": response.get("rawRootValuesExported"),
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

        contract_ok = (
            snapshot["schema"] == ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA
            and snapshot["fiber_graph_bounded"] is True
            and snapshot["attachment_roots_only"] is True
            and snapshot["nonempty_attachment_roots_only"] is True
            and snapshot["opaque_array_children_only"] is True
            and snapshot["array_elements_bounded"] is True
            and snapshot["element_value_types_only"] is True
            and snapshot["string_element_shape_classification_only"] is True
            and snapshot["known_structural_key_whitelist_only"] is True
            and snapshot["accessor_properties_skipped"] is True
            and snapshot["dom_state_node_values_excluded"] is True
            and snapshot["raw_attachment_child_keys_exported"] is False
            and snapshot["raw_array_element_values_exported"] is False
            and snapshot["raw_string_values_exported"] is False
            and snapshot["raw_root_values_exported"] is False
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
    provider = ProductArtifactArrayElementShapeV10Provider()

    support = None
    support_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}
    try:
        support, support_diagnostic = provider.shape_support(timeout=min(timeout, 5.0))
    except Exception as exc:  # noqa: BLE001
        support_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}
    support_proven = bool(
        support == _EXPECTED_SUPPORT and support_diagnostic.get("failure_reason") is None
    )

    report: dict[str, Any] = {
        "schema": "CWA_PR10_1_ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_LIVE_GATE_V1",
        "expected_head": expected_head,
        "head": head,
        "head_matches": head_matches,
        "tracked_clean": clean,
        "preflight_only": preflight_only,
        "artifact_array_element_shape_schema": ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "surface_read_budget": 0 if preflight_only else SURFACE_READ_BUDGET,
        "download_budget": DOWNLOAD_BUDGET,
        "local_write_budget": LOCAL_WRITE_BUDGET,
        "support_probe_attempted": True,
        "support_probe_proven": support_proven,
        "artifact_array_element_shape_support": support,
        "support_probe_diagnostic": support_diagnostic,
        "surface_read_attempted": False,
        "write_attempted": False,
        "download_attempted": False,
        "local_write_attempted": False,
        "raw_attachment_child_keys_exported": False,
        "raw_array_element_values_exported": False,
        "raw_string_values_exported": False,
        "raw_root_values_exported": False,
        "raw_dom_exported": False,
        "raw_text_exported": False,
        "attribute_values_exported": False,
        "react_prop_values_exported": False,
        "react_state_values_exported": False,
        "locator_values_exported": False,
        "click_performed": False,
    }

    if preflight_only:
        report["characterization"] = (
            "ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SUPPORT_PREFLIGHT_ONLY_PROVEN"
            if support_proven and head_matches and clean
            else "ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_SUPPORT_PREFLIGHT_FAILED"
        )
        report["ok"] = bool(support_proven and head_matches and clean)
        return report

    if not (support_proven and head_matches and clean):
        report["characterization"] = "ARTIFACT_ARRAY_ELEMENT_SHAPE_V10_LIVE_PREFLIGHT_NOT_PROVEN"
        report["ok"] = False
        return report

    snapshot = None
    snapshot_diagnostic: dict[str, Any] = {"failure_reason": "NOT_ATTEMPTED"}
    try:
        snapshot, snapshot_diagnostic = provider.shape_snapshot(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        snapshot_diagnostic = {"failure_reason": f"{type(exc).__name__}: {exc}"}

    report["surface_read_attempted"] = True
    report["artifact_array_element_shape_snapshot"] = snapshot
    report["artifact_array_element_shape_snapshot_diagnostic"] = snapshot_diagnostic

    placement_proven = bool(
        snapshot
        and snapshot_diagnostic.get("failure_reason") is None
        and snapshot.get("probe_placement_proven") is True
        and snapshot.get("ordered_probe_turn_pair_present") is True
    )
    array_count = int(snapshot.get("opaque_array_child_count", 0)) if snapshot else 0
    object_array_count = int(snapshot.get("array_with_object_element_count", 0)) if snapshot else 0
    token_string_array_count = int(snapshot.get("array_with_token_string_element_count", 0)) if snapshot else 0
    identity_schema_count = int(snapshot.get("array_with_identity_key_schema_count", 0)) if snapshot else 0
    locator_schema_count = int(snapshot.get("array_with_locator_key_schema_count", 0)) if snapshot else 0

    report["opaque_attachment_array_observed"] = array_count > 0
    report["object_element_array_observed"] = object_array_count > 0
    report["token_string_array_observed"] = token_string_array_count > 0
    report["identity_key_schema_observed"] = identity_schema_count > 0
    report["locator_key_schema_observed"] = locator_schema_count > 0

    if not placement_proven:
        characterization = "PROBE_TURN_PLACEMENT_NOT_PROVEN"
    elif array_count == 0:
        characterization = "PROBE_ANCHORED_NO_OPAQUE_ATTACHMENT_ARRAY_CHILDREN_OBSERVED"
    elif identity_schema_count > 0:
        characterization = "PROBE_ANCHORED_ATTACHMENT_ARRAY_IDENTITY_KEY_SCHEMA_OBSERVED"
    elif locator_schema_count > 0:
        characterization = "PROBE_ANCHORED_ATTACHMENT_ARRAY_LOCATOR_KEY_SCHEMA_OBSERVED"
    elif object_array_count > 0:
        characterization = "PROBE_ANCHORED_ATTACHMENT_ARRAY_OBJECT_ELEMENTS_OBSERVED"
    elif token_string_array_count > 0:
        characterization = "PROBE_ANCHORED_ATTACHMENT_ARRAY_TOKEN_STRING_ELEMENTS_OBSERVED"
    else:
        characterization = "PROBE_ANCHORED_ATTACHMENT_ARRAY_SCALAR_OR_NESTED_ONLY_ELEMENTS_OBSERVED"

    report["characterization"] = characterization
    report["ok"] = placement_proven
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PR10.1 attachment opaque-array element-shape v10 live gate")
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
