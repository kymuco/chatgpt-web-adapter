from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_root_key_shape_v9_live_gate import (  # noqa: E402
    ARTIFACT_ROOT_KEY_SHAPE_SCHEMA,
    ProductArtifactRootKeyShapeV9Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_root_key_shape_v9_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_root_key_shape_v9_live_gate.py"


def test_root_key_shape_v9_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"
    assert manifest["version"] == "0.1.13"


def test_root_key_shape_v9_loads_after_v8_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v8 = 'importScripts("service_worker_generated_artifact_root_shape_v8_pr10_1.js");'
    v9 = 'importScripts("service_worker_generated_artifact_root_key_shape_v9_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v8 in observability
    assert v9 in observability
    assert observability.index(v8) < observability.index(v9) < observability.index(patch)


def test_root_key_shape_v9_targets_only_nonempty_structural_artifact_roots() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "structuralArtifactRoot" in source
    assert "if (!isTraversableObject(childValue)) continue" in source
    assert "if (childEntries.length === 0) continue" in source
    assert "nonemptyRootsOnly:true" in source
    assert "text.includes('.')" in source
    assert "['svg', 'use', 'path']" in source


def test_root_key_shape_v9_classifies_keys_without_exporting_unknown_names() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "uuid_like" in source
    assert "file_prefixed_token" in source
    assert "artifact_prefixed_token" in source
    assert "hex_like" in source
    assert "opaque_token" in source
    assert "semantic_identifier" in source
    assert "keyLengthBucket" in source
    assert "knownStructuralName" in source
    assert "rawRootKeysExported:false" in source
    assert "rawRootValuesExported:false" in source
    assert "childValuesExported:false" in source
    assert "locatorValuesExported:false" in source


def test_root_key_shape_v9_skips_accessors_and_dom_state_node() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "Object.getOwnPropertyDescriptors(value)" in source
    assert "Object.prototype.hasOwnProperty.call(descriptor, 'value')" in source
    assert "'stateNode'" in source
    assert "accessorPropertiesSkipped:true" in source
    assert "domStateNodeValuesExcluded:true" in source


def test_root_key_shape_v9_python_boundary_drops_raw_keys_and_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 0,
            "relationKind": "turn_descendant",
            "fiberDepth": 25,
            "componentName": "SMn",
            "sourceKind": "update_queue",
            "sourceNestedDepth": 5,
            "sourceContainerKind": "object",
            "artifactRootKeyName": "attachments",
            "rootValueKind": "object",
            "rootCardinalityBucket": "two_to_four",
            "rootPlainObjectKind": "plain_object",
            "knownStructuralChildKeyNames": ["id", "state", "privateUnknownKey"],
            "keyShapeCounts": {"file_prefixed_token": 1, "semantic_identifier": 2},
            "childValueKindCounts": {"object": 1, "string": 2},
            "traversableChildCountBucket": "one",
            "childSummaries": [
                {
                    "keyShape": "file_prefixed_token",
                    "keyLengthBucket": "seventeen_to_thirty_two",
                    "knownStructuralKeyName": "privateUnknownKey",
                    "childValueKind": "object",
                    "childCardinalityBucket": "two_to_four",
                    "childPlainObjectKind": "plain_object",
                    "rawKey": "file_secret_identifier",
                    "childValue": {"secret": "value"},
                    "fileIdValue": "secret",
                    "urlValue": "https://example.invalid/private",
                }
            ],
            "rawRootKeys": ["file_secret_identifier"],
            "rootValue": {"file_secret_identifier": {"secret": "value"}},
        }
    )
    assert candidate is not None
    assert candidate["artifact_root_key_name"] == "attachments"
    assert candidate["known_structural_child_key_names"] == ["id", "state"]
    assert candidate["child_summaries"][0]["key_shape"] == "file_prefixed_token"
    assert candidate["child_summaries"][0]["known_structural_key_name"] is None
    serialized = json.dumps(candidate, sort_keys=True)
    assert "file_secret_identifier" not in serialized
    assert "example.invalid" not in serialized
    assert "privateUnknownKey" not in serialized
    assert "secret" not in serialized


def test_root_key_shape_v9_support_normalizes_exact_contract(monkeypatch) -> None:
    provider = ProductArtifactRootKeyShapeV9Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactRootKeyShapeV9CharacterizationSupported": True,
            "generatedArtifactRootKeyShapeV9CharacterizationSchemaVersion": ARTIFACT_ROOT_KEY_SHAPE_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "nonemptyRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "keyShapeClassificationOnly": True,
            "knownStructuralKeyWhitelistOnly": True,
            "rawRootKeysExported": False,
            "rawRootValuesExported": False,
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


def test_root_key_shape_v9_snapshot_preserves_only_shape(monkeypatch) -> None:
    provider = ProductArtifactRootKeyShapeV9Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": ARTIFACT_ROOT_KEY_SHAPE_SCHEMA,
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
            "nonemptyArtifactRootCount": 1,
            "nonemptyAttachmentRootCount": 1,
            "objectRootCount": 1,
            "arrayRootCount": 0,
            "identityAsKeyCandidateCount": 1,
            "knownStructuralKeyHitCount": 1,
            "recordLikeIdentityKeyChildCount": 1,
            "candidateSummaries": [
                {
                    "index": 0,
                    "relationKind": "turn_descendant",
                    "fiberDepth": 25,
                    "componentName": "SMn",
                    "sourceKind": "update_queue",
                    "sourceNestedDepth": 5,
                    "sourceContainerKind": "object",
                    "artifactRootKeyName": "attachments",
                    "rootValueKind": "object",
                    "rootCardinalityBucket": "two_to_four",
                    "rootPlainObjectKind": "plain_object",
                    "knownStructuralChildKeyNames": ["id"],
                    "keyShapeCounts": {"file_prefixed_token": 1, "known_structural": 1},
                    "childValueKindCounts": {"object": 1, "string": 1},
                    "traversableChildCountBucket": "one",
                    "childSummaries": [
                        {
                            "keyShape": "file_prefixed_token",
                            "keyLengthBucket": "seventeen_to_thirty_two",
                            "knownStructuralKeyName": None,
                            "childValueKind": "object",
                            "childCardinalityBucket": "two_to_four",
                            "childPlainObjectKind": "plain_object",
                        }
                    ],
                }
            ],
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "nonemptyRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "keyShapeClassificationOnly": True,
            "knownStructuralKeyWhitelistOnly": True,
            "rawRootKeysExported": False,
            "rawRootValuesExported": False,
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
    assert snapshot["identity_as_key_candidate_count"] == 1
    assert snapshot["record_like_identity_key_child_count"] == 1
    assert snapshot["candidate_summaries"][0]["key_shape_counts"]["file_prefixed_token"] == 1
    assert snapshot["raw_root_keys_exported"] is False
    assert snapshot["child_values_exported"] is False


def test_root_key_shape_v9_gate_has_zero_write_download_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_RECORD_LIKE_IDENTITY_AS_KEY_SHAPE_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
