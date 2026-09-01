from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_noncode_v4_live_gate import (  # noqa: E402
    ProductArtifactNonCodeV4Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_noncode_v4_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_noncode_v4_live_gate.py"


def test_noncode_v4_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_noncode_v4_loads_after_topology_v3_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v3 = 'importScripts("service_worker_generated_artifact_topology_v3_pr10_1.js");'
    v4 = 'importScripts("service_worker_generated_artifact_noncode_v4_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v3 in observability
    assert v4 in observability
    assert observability.index(v3) < observability.index(v4) < observability.index(patch)


def test_noncode_v4_requires_proven_assistant_turn_and_excludes_pre_code() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role === 'assistant'" in source
    assert "element.closest('pre,code')" in source
    assert "targetTurn.contains(codeAncestor)" in source
    assert "preCodeExcluded: true" in source
    assert "structuralKeyNamesOnly: true" in source


def test_noncode_v4_is_bounded_and_structural() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert ".slice(0, 2048)" in source
    assert "summaries.length >= 24" in source
    assert "depth < 6" in source
    assert "Object.keys(handles.props)" in source
    assert "Object.keys(memoized)" in source
    assert "identityLikeReactPropNames" in source
    assert "locatorLikeReactPropNames" in source
    assert "artifactLikeReactPropNames" in source
    assert "artifactLikeReactComponentNames" in source
    assert "candidateReasonKinds" in source


def test_noncode_v4_does_not_export_values_or_click() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "getAttribute('href')" not in source
    assert 'getAttribute("href")' not in source
    assert "element.href" not in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "attributeValuesExported: false" in source
    assert "reactPropValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_noncode_v4_support_normalizes_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactNonCodeV4Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactNonCodeV4CharacterizationSupported": True,
            "generatedArtifactNonCodeV4CharacterizationSchemaVersion": 4,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "preCodeExcluded": True,
            "structuralKeyNamesOnly": True,
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
    support, diagnostic = provider.noncode_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_noncode_v4_candidate_normalization_drops_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 3,
            "tagName": "a",
            "depthToTurn": 4,
            "interactiveKind": "a",
            "hrefAttributePresent": True,
            "downloadAttributePresent": False,
            "attributeNames": ["class", "href", "bad value"],
            "artifactLikeAttributeNames": [],
            "reactFiberPropertyPresent": True,
            "reactPropsPropertyPresent": True,
            "reactPropNames": ["children", "fileId", "downloadUrl", "token=value"],
            "identityLikeReactPropNames": ["fileId"],
            "locatorLikeReactPropNames": ["downloadUrl"],
            "artifactLikeReactPropNames": ["fileId", "downloadUrl"],
            "reactComponentNames": ["FileCard", "ForwardRef"],
            "artifactLikeReactComponentNames": ["FileCard"],
            "candidateReasonKinds": ["identity_react_key", "href_attribute_present"],
            "hrefValue": "https://example.invalid/secret",
            "fileIdValue": "file-secret",
        }
    )
    assert candidate is not None
    assert candidate["tag_name"] == "a"
    assert candidate["attribute_names"] == ["class", "href"]
    assert candidate["react_prop_names"] == ["children", "downloadUrl", "fileId"]
    assert candidate["identity_like_react_prop_names"] == ["fileId"]
    assert candidate["locator_like_react_prop_names"] == ["downloadUrl"]
    assert candidate["artifact_like_react_component_names"] == ["FileCard"]
    assert "href_value" not in candidate
    assert "file_id_value" not in candidate


def test_noncode_v4_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactNonCodeV4Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": 4,
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
            "scannedNonCodeElementCount": 40,
            "structuralCandidateCount": 1,
            "identityCandidateCount": 1,
            "artifactKeywordCandidateCount": 1,
            "locatorOnlyCandidateCount": 0,
            "candidateSummaries": [
                {
                    "index": 0,
                    "tagName": "a",
                    "depthToTurn": 4,
                    "interactiveKind": "a",
                    "hrefAttributePresent": True,
                    "downloadAttributePresent": False,
                    "attributeNames": ["class", "href"],
                    "artifactLikeAttributeNames": [],
                    "reactFiberPropertyPresent": True,
                    "reactPropsPropertyPresent": True,
                    "reactPropNames": ["children", "fileId", "href"],
                    "identityLikeReactPropNames": ["fileId"],
                    "locatorLikeReactPropNames": ["href"],
                    "artifactLikeReactPropNames": ["fileId"],
                    "reactComponentNames": ["FileCard"],
                    "artifactLikeReactComponentNames": ["FileCard"],
                    "candidateReasonKinds": ["identity_react_key", "href_attribute_present"],
                }
            ],
            "preCodeExcluded": True,
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
    snapshot, diagnostic = provider.noncode_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["probe_placement_proven"] is True
    assert snapshot["pre_code_excluded"] is True
    assert snapshot["structural_candidate_count"] == 1
    assert snapshot["candidate_summaries"][0]["identity_like_react_prop_names"] == ["fileId"]
    assert snapshot["react_prop_values_exported"] is False
    assert snapshot["locator_values_exported"] is False


def test_noncode_v4_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_NONCODE_IDENTITY_KEY_NAMES_OBSERVED" in source
    assert "PROBE_ANCHORED_NONCODE_ARTIFACT_STRUCTURAL_KEY_NAMES_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source