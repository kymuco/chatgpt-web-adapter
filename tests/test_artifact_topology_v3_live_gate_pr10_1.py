from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_topology_v3_live_gate import (  # noqa: E402
    PROBE_FILENAME,
    ProductArtifactTopologyV3Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_topology_v3_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_topology_v3_live_gate.py"


def test_topology_v3_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_topology_v3_loads_after_surface_v2_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v2 = 'importScripts("service_worker_generated_artifact_surface_v2_overlay_pr10_1.js");'
    v3 = 'importScripts("service_worker_generated_artifact_topology_v3_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v2 in observability
    assert v3 in observability
    assert observability.index(v2) < observability.index(v3) < observability.index(patch)


def test_topology_v3_requires_proven_assistant_probe_turn() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert PROBE_FILENAME in source
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role === 'assistant'" in source
    assert "assistantTurnAnchorRequired: true" in source
    assert "perCandidateStructuralOnly: true" in source


def test_topology_v3_is_per_candidate_and_nearby_interactive_bounded() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "candidates.length < 12" in source
    assert "candidateSummaries.length < 8" in source
    assert "depth <= 12" in source
    assert "depth <= 8" in source
    assert ".slice(0, 32)" in source
    assert "insidePre" in source
    assert "insideCode" in source
    assert "nearestInteractiveContainerDepth" in source
    assert "nearbyInteractiveCount" in source
    assert "reactPropNames" in source
    assert "identityLikeReactPropNames" in source
    assert "locatorLikeReactPropNames" in source


def test_topology_v3_exports_names_not_values() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "Object.keys(handles.props)" in source
    assert "Object.keys(memoized)" in source
    assert "getAttribute('href')" not in source
    assert "getAttribute(\"href\")" not in source
    assert ".href" not in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "attributeValuesExported: false" in source
    assert "reactPropValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_topology_v3_support_normalizes_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactTopologyV3Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactTopologyV3CharacterizationSupported": True,
            "generatedArtifactTopologyV3CharacterizationSchemaVersion": 3,
            "fixedProbeFilename": PROBE_FILENAME,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "perCandidateStructuralOnly": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support, diagnostic = provider.topology_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_topology_v3_candidate_normalization_drops_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 2,
            "tagName": "span",
            "candidateAttributeNames": ["class", "bad value"],
            "ancestorTagPath": ["div", "section"],
            "ancestorAttributeNames": ["data-testid", "style"],
            "ancestorDepthToTurn": 5,
            "insidePre": False,
            "insideCode": False,
            "insideBlockquote": False,
            "insideTable": False,
            "directInteractiveAncestorPresent": False,
            "nearestInteractiveContainerDepth": 2,
            "nearbyInteractiveCount": 1,
            "nearbyInteractiveKinds": ["button"],
            "nearbyInteractiveAttributeNames": ["aria-label", "href"],
            "nearbyHrefAttributePresent": True,
            "nearbyDownloadAttributePresent": False,
            "reactFiberPropertyPresent": True,
            "reactPropsPropertyPresent": True,
            "reactPropNames": ["children", "fileId", "downloadUrl", "token=value"],
            "identityLikeReactPropNames": ["fileId"],
            "locatorLikeReactPropNames": ["downloadUrl"],
            "hrefValue": "https://example.invalid/secret",
            "fileIdValue": "file-secret",
        }
    )
    assert candidate is not None
    assert candidate["tag_name"] == "span"
    assert candidate["candidate_attribute_names"] == ["class"]
    assert candidate["nearby_interactive_attribute_names"] == ["aria-label", "href"]
    assert candidate["react_prop_names"] == ["children", "downloadUrl", "fileId"]
    assert candidate["identity_like_react_prop_names"] == ["fileId"]
    assert candidate["locator_like_react_prop_names"] == ["downloadUrl"]
    assert "href_value" not in candidate
    assert "file_id_value" not in candidate


def test_topology_v3_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactTopologyV3Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": 3,
            "fixedProbeFilename": PROBE_FILENAME,
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
            "filenameCandidateCount": 1,
            "candidateSummaries": [
                {
                    "index": 0,
                    "tagName": "span",
                    "candidateAttributeNames": ["class"],
                    "ancestorTagPath": ["div"],
                    "ancestorAttributeNames": ["data-testid"],
                    "ancestorDepthToTurn": 4,
                    "insidePre": False,
                    "insideCode": False,
                    "insideBlockquote": False,
                    "insideTable": False,
                    "directInteractiveAncestorPresent": False,
                    "nearestInteractiveContainerDepth": 2,
                    "nearbyInteractiveCount": 1,
                    "nearbyInteractiveKinds": ["button"],
                    "nearbyInteractiveAttributeNames": ["aria-label"],
                    "nearbyHrefAttributePresent": False,
                    "nearbyDownloadAttributePresent": False,
                    "reactFiberPropertyPresent": True,
                    "reactPropsPropertyPresent": True,
                    "reactPropNames": ["children", "fileId"],
                    "identityLikeReactPropNames": ["fileId"],
                    "locatorLikeReactPropNames": [],
                }
            ],
            "rawDomExported": False,
            "rawTextExported": False,
            "attributeValuesExported": False,
            "reactPropValuesExported": False,
            "locatorValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
            "debuggerAttachedAfter": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    snapshot, diagnostic = provider.topology_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["probe_placement_proven"] is True
    assert snapshot["filename_candidate_count"] == 1
    assert snapshot["candidate_summaries"][0]["identity_like_react_prop_names"] == ["fileId"]
    assert snapshot["react_prop_values_exported"] is False
    assert snapshot["locator_values_exported"] is False


def test_topology_v3_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_TOPOLOGY_IDENTITY_KEY_NAMES_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
