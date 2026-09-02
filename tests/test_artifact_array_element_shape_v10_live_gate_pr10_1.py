from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_array_element_shape_v10_live_gate import (  # noqa: E402
    ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA,
    ProductArtifactArrayElementShapeV10Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_array_element_shape_v10_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_array_element_shape_v10_live_gate.py"


def test_array_element_shape_v10_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"
    assert manifest["version"] == "0.1.13"


def test_array_element_shape_v10_loads_after_v9_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v9 = 'importScripts("service_worker_generated_artifact_root_key_shape_v9_pr10_1.js");'
    v10 = 'importScripts("service_worker_generated_artifact_array_element_shape_v10_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v9 in observability
    assert v10 in observability
    assert observability.index(v9) < observability.index(v10) < observability.index(patch)


def test_array_element_shape_v10_targets_only_attachment_opaque_arrays() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "attachmentRoot" in source
    assert "new Set(['attachment','attachments'])" in source
    assert "keyShape(rawChildKey) !== 'opaque_token'" in source
    assert "!Array.isArray(childValue)" in source
    assert "childValue.length === 0" in source
    assert "MAX_ARRAY_ELEMENTS_SCANNED = 64" in source
    assert "opaqueArrayChildrenOnly:true" in source
    assert "arrayElementsBounded:true" in source


def test_array_element_shape_v10_exports_types_shapes_and_whitelisted_key_names_only() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "elementValueKindCounts" in source
    assert "stringElementShapeCounts" in source
    assert "stringElementLengthBucketCounts" in source
    assert "knownStructuralElementKeyNames" in source
    assert "identityLikeElementKeyNames" in source
    assert "locatorLikeElementKeyNames" in source
    assert "rawAttachmentChildKeysExported:false" in source
    assert "rawArrayElementValuesExported:false" in source
    assert "rawStringValuesExported:false" in source
    assert "rawRootValuesExported:false" in source
    assert "locatorValuesExported:false" in source


def test_array_element_shape_v10_skips_accessors_and_dom_state_node() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "Object.getOwnPropertyDescriptors(value)" in source
    assert "Object.prototype.hasOwnProperty.call(descriptor, 'value')" in source
    assert "'stateNode'" in source
    assert "accessorPropertiesSkipped:true" in source
    assert "domStateNodeValuesExcluded:true" in source


def test_array_element_shape_v10_python_boundary_drops_raw_keys_and_values() -> None:
    candidate = _safe_candidate(
        {
            "relationKind": "turn_descendant",
            "fiberDepth": 25,
            "componentName": "SMn",
            "sourceKind": "update_queue",
            "sourceNestedDepth": 5,
            "sourceContainerKind": "object",
            "artifactRootKeyName": "attachments",
            "childKeyShape": "opaque_token",
            "childKeyLengthBucket": "seventeen_to_thirty_two",
            "arrayCardinalityBucket": "two_to_four",
            "elementsScannedCount": 3,
            "elementValueKindCounts": {"object": 1, "string": 2},
            "stringElementShapeCounts": {"file_prefixed_token": 1, "opaque_token": 1},
            "stringElementLengthBucketCounts": {"seventeen_to_thirty_two": 2},
            "traversableObjectElementCount": 1,
            "plainObjectElementCount": 1,
            "knownStructuralElementKeyNames": ["id", "filename", "privateUnknownKey"],
            "identityLikeElementKeyNames": ["fileId", "privateIdentity"],
            "locatorLikeElementKeyNames": ["downloadUrl", "privateLocator"],
            "rawAttachmentChildKey": "secret_opaque_child",
            "rawArrayElementValues": ["file_secret_identifier", "private-value"],
            "rawStringValues": ["private-value"],
            "locatorValue": "https://example.invalid/private",
        }
    )
    assert candidate is not None
    assert candidate["artifact_root_key_name"] == "attachments"
    assert candidate["child_key_shape"] == "opaque_token"
    assert candidate["known_structural_element_key_names"] == ["filename", "id"]
    assert candidate["identity_like_element_key_names"] == ["fileId"]
    assert candidate["locator_like_element_key_names"] == ["downloadUrl"]
    serialized = json.dumps(candidate, sort_keys=True)
    assert "secret_opaque_child" not in serialized
    assert "file_secret_identifier" not in serialized
    assert "private-value" not in serialized
    assert "example.invalid" not in serialized
    assert "privateUnknownKey" not in serialized
    assert "privateIdentity" not in serialized
    assert "privateLocator" not in serialized


def test_array_element_shape_v10_python_boundary_accepts_worker_snake_case() -> None:
    candidate = _safe_candidate(
        {
            "relation_kind": "turn_descendant",
            "fiber_depth": 25,
            "component_name": "SMn",
            "source_kind": "update_queue",
            "source_nested_depth": 5,
            "source_container_kind": "object",
            "artifact_root_key_name": "attachments",
            "child_key_shape": "opaque_token",
            "child_key_length_bucket": "nine_to_sixteen",
            "array_cardinality_bucket": "over_sixteen",
            "elements_scanned_count": 32,
            "element_value_kind_counts": {"string": 32},
            "string_element_shape_counts": {"opaque_token": 32},
            "string_element_length_bucket_counts": {"seventeen_to_thirty_two": 32},
            "traversable_object_element_count": 0,
            "plain_object_element_count": 0,
            "known_structural_element_key_names": [],
            "identity_like_element_key_names": [],
            "locator_like_element_key_names": [],
        }
    )
    assert candidate is not None
    assert candidate["source_kind"] == "update_queue"
    assert candidate["array_cardinality_bucket"] == "over_sixteen"
    assert candidate["element_value_kind_counts"]["string"] == 32
    assert candidate["string_element_shape_counts"]["opaque_token"] == 32


def test_array_element_shape_v10_support_normalizes_exact_contract(monkeypatch) -> None:
    provider = ProductArtifactArrayElementShapeV10Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactArrayElementShapeV10CharacterizationSupported": True,
            "generatedArtifactArrayElementShapeV10CharacterizationSchemaVersion": ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "fiberGraphBounded": True,
            "attachmentRootsOnly": True,
            "nonemptyAttachmentRootsOnly": True,
            "opaqueArrayChildrenOnly": True,
            "arrayElementsBounded": True,
            "elementValueTypesOnly": True,
            "stringElementShapeClassificationOnly": True,
            "knownStructuralKeyWhitelistOnly": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rawAttachmentChildKeysExported": False,
            "rawArrayElementValuesExported": False,
            "rawStringValuesExported": False,
            "rawRootValuesExported": False,
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "reactStateValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support, diagnostic = provider.shape_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_array_element_shape_v10_snapshot_preserves_only_safe_shape(monkeypatch) -> None:
    provider = ProductArtifactArrayElementShapeV10Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": ARTIFACT_ARRAY_ELEMENT_SHAPE_SCHEMA,
            "runtimeTabPresent": True,
            "runtimeRouteKind": "conversation",
            "runtimeConversationIdPresent": True,
            "surfaceReady": True,
            "selectorKind": "conversation_testid",
            "visibleTurnCount": 2,
            "userProbeMarkerTurnCount": 1,
            "assistantCompletionMarkerTurnCount": 1,
            "orderedProbeTurnPairPresent": True,
            "probePlacementProven": True,
            "placementRoleEvidenceKinds": ["data_turn"],
            "fiberRootCount": 1,
            "scannedFiberCount": 495,
            "scannedSourceContainerCount": 23031,
            "nonemptyAttachmentRootCount": 1,
            "opaqueArrayChildCount": 2,
            "totalArrayElementsScannedCount": 20,
            "arrayWithObjectElementCount": 1,
            "arrayWithTokenStringElementCount": 1,
            "arrayWithIdentityKeySchemaCount": 1,
            "arrayWithLocatorKeySchemaCount": 0,
            "arrayCandidateSummaries": [
                {
                    "relationKind": "turn_descendant",
                    "fiberDepth": 25,
                    "componentName": "SMn",
                    "sourceKind": "update_queue",
                    "sourceNestedDepth": 5,
                    "sourceContainerKind": "object",
                    "artifactRootKeyName": "attachments",
                    "childKeyShape": "opaque_token",
                    "childKeyLengthBucket": "nine_to_sixteen",
                    "arrayCardinalityBucket": "two_to_four",
                    "elementsScannedCount": 3,
                    "elementValueKindCounts": {"object": 1, "string": 2},
                    "stringElementShapeCounts": {"opaque_token": 2},
                    "stringElementLengthBucketCounts": {"seventeen_to_thirty_two": 2},
                    "traversableObjectElementCount": 1,
                    "plainObjectElementCount": 1,
                    "knownStructuralElementKeyNames": ["id", "filename"],
                    "identityLikeElementKeyNames": ["id"],
                    "locatorLikeElementKeyNames": [],
                }
            ],
            "fiberGraphBounded": True,
            "attachmentRootsOnly": True,
            "nonemptyAttachmentRootsOnly": True,
            "opaqueArrayChildrenOnly": True,
            "arrayElementsBounded": True,
            "elementValueTypesOnly": True,
            "stringElementShapeClassificationOnly": True,
            "knownStructuralKeyWhitelistOnly": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rawAttachmentChildKeysExported": False,
            "rawArrayElementValuesExported": False,
            "rawStringValuesExported": False,
            "rawRootValuesExported": False,
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "reactStateValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
            "debuggerAttachedAfter": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    snapshot, diagnostic = provider.shape_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["opaque_array_child_count"] == 2
    assert snapshot["array_with_identity_key_schema_count"] == 1
    candidate = snapshot["array_candidate_summaries"][0]
    assert candidate["identity_like_element_key_names"] == ["id"]
    assert candidate["known_structural_element_key_names"] == ["filename", "id"]
    assert snapshot["raw_array_element_values_exported"] is False
    assert snapshot["raw_string_values_exported"] is False


def test_array_element_shape_v10_gate_has_zero_write_download_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_ATTACHMENT_ARRAY_IDENTITY_KEY_SCHEMA_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
