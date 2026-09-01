from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_fiber_state_v6_live_gate import (  # noqa: E402
    FIBER_STATE_SCHEMA,
    ProductArtifactFiberStateV6Provider,
    _EXPECTED_SUPPORT,
    _safe_hit,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_fiber_state_v6_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_fiber_state_v6_live_gate.py"


def test_fiber_state_v6_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_fiber_state_v6_loads_after_v5_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v5 = 'importScripts("service_worker_generated_artifact_action_v5_pr10_1.js");'
    v6 = 'importScripts("service_worker_generated_artifact_fiber_state_v6_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v5 in observability
    assert v6 in observability
    assert observability.index(v5) < observability.index(v6) < observability.index(patch)


def test_fiber_state_v6_requires_proven_assistant_probe_turn() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role === 'assistant'" in source


def test_fiber_state_v6_is_bounded_key_shape_only() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "MAX_FIBERS_PER_TURN" in source
    assert "MAX_CONTAINER_DEPTH" in source
    assert "MAX_CONTAINERS_PER_SOURCE" in source
    assert "Object.getOwnPropertyDescriptors(value)" in source
    assert "Object.prototype.hasOwnProperty.call(descriptor, 'value')" in source
    assert "fiber.stateNode" not in source
    assert "stateNode', 'return', 'child', 'sibling'" in source
    assert "artifactRelevantKeysOnly: true" in source
    assert "accessorPropertiesSkipped: true" in source
    assert "domStateNodeValuesExcluded: true" in source


def test_fiber_state_v6_exports_no_values_and_has_no_side_effects() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "getAttribute('href')" not in source
    assert 'getAttribute("href")' not in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "attributeValuesExported: false" in source
    assert "reactPropValuesExported: false" in source
    assert "reactStateValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_fiber_state_v6_support_normalizes_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactFiberStateV6Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactFiberStateV6CharacterizationSupported": True,
            "generatedArtifactFiberStateV6CharacterizationSchemaVersion": FIBER_STATE_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "fiberGraphBounded": True,
            "artifactRelevantKeysOnly": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
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
    support, diagnostic = provider.fiber_state_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_fiber_state_v6_hit_normalization_drops_values_and_generic_keys() -> None:
    hit = _safe_hit(
        {
            "index": 1,
            "relationKind": "turn_descendant",
            "fiberDepth": 8,
            "componentName": "FileCard",
            "sourceKind": "memoized_state",
            "nestedDepth": 2,
            "containerKind": "object",
            "identityLikeKeyNames": ["fileId", "bad value"],
            "artifactLikeKeyNames": ["fileId", "downloadUrl"],
            "locatorLikeKeyNames": ["downloadUrl"],
            "artifactContext": True,
            "artifactContextLocator": True,
            "fileIdValue": "file-secret",
            "downloadUrlValue": "https://example.invalid/private",
            "allKeyNames": ["privateUserField", "fileId"],
        }
    )
    assert hit is not None
    assert hit["component_name"] == "FileCard"
    assert hit["identity_like_key_names"] == ["fileId"]
    assert hit["artifact_like_key_names"] == ["downloadUrl", "fileId"]
    assert hit["locator_like_key_names"] == ["downloadUrl"]
    assert "file_id_value" not in hit
    assert "download_url_value" not in hit
    assert "all_key_names" not in hit


def test_fiber_state_v6_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactFiberStateV6Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": FIBER_STATE_SCHEMA,
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
            "scannedFiberCount": 120,
            "scannedContainerCount": 900,
            "identityKeyHitCount": 1,
            "artifactKeyHitCount": 1,
            "locatorKeyHitCount": 1,
            "artifactContextLocatorHitCount": 1,
            "artifactComponentFiberCount": 1,
            "artifactComponentNames": ["FileCard"],
            "hitSummaries": [
                {
                    "index": 0,
                    "relationKind": "turn_descendant",
                    "fiberDepth": 7,
                    "componentName": "FileCard",
                    "sourceKind": "memoized_props",
                    "nestedDepth": 1,
                    "containerKind": "object",
                    "identityLikeKeyNames": ["fileId"],
                    "artifactLikeKeyNames": ["fileId", "downloadUrl"],
                    "locatorLikeKeyNames": ["downloadUrl"],
                    "artifactContext": True,
                    "artifactContextLocator": True,
                }
            ],
            "fiberGraphBounded": True,
            "artifactRelevantKeysOnly": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
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
    snapshot, diagnostic = provider.fiber_state_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["fiber_root_count"] == 1
    assert snapshot["identity_key_hit_count"] == 1
    assert snapshot["artifact_component_names"] == ["FileCard"]
    assert snapshot["hit_summaries"][0]["identity_like_key_names"] == ["fileId"]
    assert snapshot["react_state_values_exported"] is False
    assert snapshot["locator_values_exported"] is False


def test_fiber_state_v6_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_REACT_STATE_IDENTITY_KEY_NAMES_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
