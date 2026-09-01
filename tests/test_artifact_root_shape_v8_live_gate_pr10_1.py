from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_root_shape_v8_live_gate import (  # noqa: E402
    ARTIFACT_ROOT_SHAPE_SCHEMA,
    ProductArtifactRootShapeV8Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_root_shape_v8_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_root_shape_v8_live_gate.py"


def test_root_shape_v8_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"
    assert manifest["version"] == "0.1.13"


def test_root_shape_v8_loads_after_v7_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v7 = 'importScripts("service_worker_generated_artifact_subtree_v7_pr10_1.js");'
    v8 = 'importScripts("service_worker_generated_artifact_root_shape_v8_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v7 in observability
    assert v8 in observability
    assert observability.index(v7) < observability.index(v8) < observability.index(patch)


def test_root_shape_v8_requires_probe_placement_and_exact_structural_roots() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "structuralArtifactRoot" in source
    assert "text.includes('.')" in source
    assert "'attachment', 'attachments', 'file', 'files', 'artifact', 'artifacts'" in source
    assert "FileTile.removeFile" not in source


def test_root_shape_v8_exports_only_type_enum_and_cardinality_bucket() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "rootValueKind" in source
    assert "rootEmpty" in source
    assert "rootCardinalityBucket" in source
    assert "rootElementValueKinds" in source
    assert "cardinalityBucket" in source
    assert "rootValueTypesOnly: true" in source
    assert "rootCardinalityBucketOnly: true" in source
    assert "rootValuesExported: false" in source
    assert "childValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_root_shape_v8_skips_accessors_dom_state_node_and_svg_noise() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "Object.getOwnPropertyDescriptors(value)" in source
    assert "Object.prototype.hasOwnProperty.call(descriptor, 'value')" in source
    assert "'stateNode'" in source
    assert "['svg', 'use', 'path']" in source
    assert "domStateNodeValuesExcluded: true" in source
    assert "accessorPropertiesSkipped: true" in source


def test_root_shape_v8_support_normalizes_exact_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactRootShapeV8Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactRootShapeV8CharacterizationSupported": True,
            "generatedArtifactRootShapeV8CharacterizationSchemaVersion": ARTIFACT_ROOT_SHAPE_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rootValueTypesOnly": True,
            "rootCardinalityBucketOnly": True,
            "rootValuesExported": False,
            "childValuesExported": False,
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


def test_root_shape_v8_candidate_normalization_drops_all_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 0,
            "relationKind": "turn_descendant",
            "fiberDepth": 31,
            "componentName": "OEn",
            "sourceKind": "memoized_props",
            "sourceNestedDepth": 0,
            "sourceContainerKind": "object",
            "artifactRootKeyName": "attachments",
            "rootValueKind": "array",
            "rootEmpty": False,
            "rootCardinalityBucket": "one",
            "rootElementValueKinds": ["object"],
            "rootValue": [{"fileId": "secret"}],
            "fileIdValue": "secret",
            "urlValue": "https://example.invalid/private",
        }
    )
    assert candidate is not None
    assert candidate["artifact_root_key_name"] == "attachments"
    assert candidate["root_value_kind"] == "array"
    assert candidate["root_cardinality_bucket"] == "one"
    assert candidate["root_element_value_kinds"] == ["object"]
    assert "root_value" not in candidate
    assert "file_id_value" not in candidate
    assert "url_value" not in candidate


def test_root_shape_v8_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactRootShapeV8Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": ARTIFACT_ROOT_SHAPE_SCHEMA,
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
            "artifactRootHitCount": 2,
            "attachmentRootHitCount": 2,
            "nullOrUndefinedRootCount": 0,
            "emptyArrayRootCount": 1,
            "nonemptyArrayRootCount": 1,
            "emptyObjectRootCount": 0,
            "nonemptyObjectRootCount": 0,
            "scalarOrFunctionRootCount": 0,
            "candidateSummaries": [
                {
                    "index": 0,
                    "relationKind": "turn_descendant",
                    "fiberDepth": 31,
                    "componentName": "OEn",
                    "sourceKind": "memoized_props",
                    "sourceNestedDepth": 0,
                    "sourceContainerKind": "object",
                    "artifactRootKeyName": "attachments",
                    "rootValueKind": "array",
                    "rootEmpty": True,
                    "rootCardinalityBucket": "zero",
                    "rootElementValueKinds": [],
                },
                {
                    "index": 1,
                    "relationKind": "turn_descendant",
                    "fiberDepth": 25,
                    "componentName": "SMn",
                    "sourceKind": "update_queue",
                    "sourceNestedDepth": 5,
                    "sourceContainerKind": "object",
                    "artifactRootKeyName": "attachments",
                    "rootValueKind": "array",
                    "rootEmpty": False,
                    "rootCardinalityBucket": "one",
                    "rootElementValueKinds": ["object"],
                },
            ],
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rootValueTypesOnly": True,
            "rootCardinalityBucketOnly": True,
            "rootValuesExported": False,
            "childValuesExported": False,
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
    assert snapshot["artifact_root_hit_count"] == 2
    assert snapshot["empty_array_root_count"] == 1
    assert snapshot["nonempty_array_root_count"] == 1
    assert snapshot["candidate_summaries"][1]["root_element_value_kinds"] == ["object"]
    assert snapshot["root_values_exported"] is False
    assert snapshot["child_values_exported"] is False


def test_root_shape_v8_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_ARTIFACT_ROOT_VALUES_EMPTY_OR_NULL" in source
    assert "PROBE_ANCHORED_NONEMPTY_ARTIFACT_ROOT_SHAPE_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
