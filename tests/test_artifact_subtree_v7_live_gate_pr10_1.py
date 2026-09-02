from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_subtree_v7_live_gate import (  # noqa: E402
    ARTIFACT_SUBTREE_SCHEMA,
    ProductArtifactSubtreeV7Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_subtree_v7_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_subtree_v7_live_gate.py"


def test_subtree_v7_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_subtree_v7_loads_after_v6_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v6 = 'importScripts("service_worker_generated_artifact_fiber_state_v6_pr10_1.js");'
    v7 = 'importScripts("service_worker_generated_artifact_subtree_v7_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v6 in observability
    assert v7 in observability
    assert observability.index(v6) < observability.index(v7) < observability.index(patch)


def test_subtree_v7_requires_probe_placement_and_narrow_structural_roots() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "structuralArtifactRoot" in source
    assert "text.includes('.')" in source
    assert "'attachment', 'attachments', 'file', 'files', 'artifact', 'artifacts'" in source
    assert "FileTile.removeFile" not in source
    assert "FileDataView.fileDescFile" not in source


def test_subtree_v7_excludes_svg_use_and_skips_accessors_dom_state_node() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "excludedFiberComponent" in source
    assert "['svg', 'use', 'path']" in source
    assert "Object.getOwnPropertyDescriptors(value)" in source
    assert "Object.prototype.hasOwnProperty.call(descriptor, 'value')" in source
    assert "'stateNode'" in source
    assert "domStateNodeValuesExcluded: true" in source
    assert "accessorPropertiesSkipped: true" in source


def test_subtree_v7_prioritizes_strong_candidates_and_exports_no_values() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "[...strongCandidates, ...weakCandidates]" in source
    assert "MAX_CANDIDATES = 32" in source
    assert "artifactSubtreeValuesExported: false" in source
    assert "reactPropValuesExported: false" in source
    assert "reactStateValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source
    assert "getAttribute('href')" not in source
    assert 'getAttribute("href")' not in source


def test_subtree_v7_support_normalizes_exact_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactSubtreeV7Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactSubtreeV7CharacterizationSupported": True,
            "generatedArtifactSubtreeV7CharacterizationSchemaVersion": ARTIFACT_SUBTREE_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "reactStateValuesExported": False,
            "artifactSubtreeValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support, diagnostic = provider.subtree_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_subtree_v7_candidate_normalization_drops_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 0,
            "relationKind": "turn_descendant",
            "fiberDepth": 31,
            "componentName": "OEn",
            "sourceKind": "memoized_props",
            "sourceNestedDepth": 0,
            "sourceContainerKind": "object",
            "artifactRootKeyNames": ["attachments"],
            "sameContainerIdentityLikeKeyNames": [],
            "sameContainerLocatorLikeKeyNames": [],
            "subtreeContainerCount": 3,
            "subtreeIdentityLikeKeyNames": ["fileId"],
            "subtreeLocatorLikeKeyNames": ["url"],
            "subtreeStructuralArtifactKeyNames": ["file"],
            "subtreeIdentityMinDepth": 1,
            "subtreeLocatorMinDepth": 1,
            "strongCandidate": True,
            "fileIdValue": "file-secret",
            "urlValue": "https://example.invalid/private",
            "attachmentValue": {"secret": True},
        }
    )
    assert candidate is not None
    assert candidate["artifact_root_key_names"] == ["attachments"]
    assert candidate["subtree_identity_like_key_names"] == ["fileId"]
    assert candidate["subtree_locator_like_key_names"] == ["url"]
    assert candidate["strong_candidate"] is True
    assert "file_id_value" not in candidate
    assert "url_value" not in candidate
    assert "attachment_value" not in candidate


def test_subtree_v7_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactSubtreeV7Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": ARTIFACT_SUBTREE_SCHEMA,
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
            "scannedFiberCount": 100,
            "scannedSourceContainerCount": 500,
            "artifactRootHitCount": 1,
            "attachmentRootHitCount": 1,
            "artifactSubtreeIdentityHitCount": 1,
            "artifactSubtreeLocatorHitCount": 1,
            "sameContainerIdentityHitCount": 0,
            "sameContainerLocatorHitCount": 0,
            "strongCandidateCount": 1,
            "candidateSummaries": [
                {
                    "index": 0,
                    "relationKind": "turn_descendant",
                    "fiberDepth": 31,
                    "componentName": "OEn",
                    "sourceKind": "memoized_props",
                    "sourceNestedDepth": 0,
                    "sourceContainerKind": "object",
                    "artifactRootKeyNames": ["attachments"],
                    "sameContainerIdentityLikeKeyNames": [],
                    "sameContainerLocatorLikeKeyNames": [],
                    "subtreeContainerCount": 3,
                    "subtreeIdentityLikeKeyNames": ["fileId"],
                    "subtreeLocatorLikeKeyNames": ["url"],
                    "subtreeStructuralArtifactKeyNames": ["file"],
                    "subtreeIdentityMinDepth": 1,
                    "subtreeLocatorMinDepth": 1,
                    "strongCandidate": True,
                }
            ],
            "fiberGraphBounded": True,
            "structuralArtifactRootsOnly": True,
            "dottedLocalizationKeysExcluded": True,
            "svgUseFibersExcluded": True,
            "accessorPropertiesSkipped": True,
            "domStateNodeValuesExcluded": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "reactStateValuesExported": False,
            "artifactSubtreeValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
            "debuggerAttachedAfter": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    snapshot, diagnostic = provider.subtree_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["artifact_root_hit_count"] == 1
    assert snapshot["candidate_summaries"][0]["subtree_identity_like_key_names"] == ["fileId"]
    assert snapshot["artifact_subtree_values_exported"] is False
    assert snapshot["locator_values_exported"] is False


def test_subtree_v7_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_ARTIFACT_SUBTREE_IDENTITY_KEY_NAMES_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
