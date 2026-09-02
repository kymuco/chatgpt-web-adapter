from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_action_v5_live_gate import (  # noqa: E402
    ACTION_SCHEMA,
    ProductArtifactActionV5Provider,
    _EXPECTED_SUPPORT,
    _safe_candidate,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_action_v5_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_action_v5_live_gate.py"


def test_action_v5_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_action_v5_loads_after_v4_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v4 = 'importScripts("service_worker_generated_artifact_noncode_v4_pr10_1.js");'
    v5 = 'importScripts("service_worker_generated_artifact_action_v5_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v4 in observability
    assert v5 in observability
    assert observability.index(v4) < observability.index(v5) < observability.index(patch)


def test_action_v5_excludes_code_and_svg_use_noise() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "querySelectorAll('a,button,[role=\"button\"],[role=\"link\"]')" in source
    assert "element.closest('pre,code,svg')" in source
    assert "preCodeSvgExcluded: true" in source
    assert "hostActionOnly: true" in source
    assert "querySelectorAll('*')" not in source
    assert "tagName: safeName(String(host.tagName" in source


def test_action_v5_requires_proven_assistant_probe_turn() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role === 'assistant'" in source


def test_action_v5_exports_names_not_values_and_has_no_side_effects() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "Object.keys(handles.props)" in source
    assert "Object.keys(memoized)" in source
    assert "getAttribute('href')" not in source
    assert 'getAttribute("href")' not in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "attributeValuesExported: false" in source
    assert "reactPropValuesExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_action_v5_support_normalizes_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactActionV5Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactActionV5CharacterizationSupported": True,
            "generatedArtifactActionV5CharacterizationSchemaVersion": ACTION_SCHEMA,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "preCodeSvgExcluded": True,
            "hostActionOnly": True,
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
    support, diagnostic = provider.action_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_action_v5_candidate_normalization_drops_values() -> None:
    candidate = _safe_candidate(
        {
            "index": 1,
            "tagName": "a",
            "depthToTurn": 5,
            "interactiveKind": "a",
            "hrefAttributePresent": True,
            "downloadAttributePresent": False,
            "hostAttributeNames": ["class", "href", "bad value"],
            "boundedAttributeNames": ["class", "data-testid"],
            "reactFiberPropertyPresent": True,
            "reactPropsPropertyPresent": True,
            "hostReactPropNames": ["children", "href"],
            "boundedReactPropNames": ["children", "href", "fileId", "token=value"],
            "identityLikeReactPropNames": ["fileId"],
            "locatorLikeReactPropNames": ["href"],
            "artifactLikeReactPropNames": ["fileId"],
            "boundedReactComponentNames": ["FileCard", "a"],
            "artifactLikeReactComponentNames": ["FileCard"],
            "artifactLikeAttributeNames": [],
            "identitySignal": True,
            "artifactSignal": True,
            "locatorSignal": True,
            "hrefValue": "https://example.invalid/private",
            "fileIdValue": "file-secret",
        }
    )
    assert candidate is not None
    assert candidate["tag_name"] == "a"
    assert candidate["host_attribute_names"] == ["class", "href"]
    assert candidate["bounded_react_prop_names"] == ["children", "fileId", "href"]
    assert candidate["identity_like_react_prop_names"] == ["fileId"]
    assert candidate["artifact_like_react_component_names"] == ["FileCard"]
    assert "href_value" not in candidate
    assert "file_id_value" not in candidate


def test_action_v5_snapshot_contract_and_shape(monkeypatch) -> None:
    provider = ProductArtifactActionV5Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": ACTION_SCHEMA,
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
            "actionHostCount": 1,
            "hrefActionHostCount": 1,
            "downloadActionHostCount": 0,
            "identitySignalActionCount": 1,
            "artifactSignalActionCount": 1,
            "locatorSignalActionCount": 1,
            "candidateSummaries": [
                {
                    "index": 0,
                    "tagName": "a",
                    "depthToTurn": 4,
                    "interactiveKind": "a",
                    "hrefAttributePresent": True,
                    "downloadAttributePresent": False,
                    "hostAttributeNames": ["href"],
                    "boundedAttributeNames": ["href"],
                    "reactFiberPropertyPresent": True,
                    "reactPropsPropertyPresent": True,
                    "hostReactPropNames": ["href"],
                    "boundedReactPropNames": ["href", "fileId"],
                    "identityLikeReactPropNames": ["fileId"],
                    "locatorLikeReactPropNames": ["href"],
                    "artifactLikeReactPropNames": ["fileId"],
                    "boundedReactComponentNames": ["FileCard", "a"],
                    "artifactLikeReactComponentNames": ["FileCard"],
                    "artifactLikeAttributeNames": [],
                    "identitySignal": True,
                    "artifactSignal": True,
                    "locatorSignal": True,
                }
            ],
            "preCodeSvgExcluded": True,
            "hostActionOnly": True,
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
    snapshot, diagnostic = provider.action_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["pre_code_svg_excluded"] is True
    assert snapshot["host_action_only"] is True
    assert snapshot["action_host_count"] == 1
    assert snapshot["candidate_summaries"][0]["identity_like_react_prop_names"] == ["fileId"]
    assert snapshot["react_prop_values_exported"] is False
    assert snapshot["locator_values_exported"] is False


def test_action_v5_gate_has_zero_write_download_and_click_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_ANCHORED_HTML_ACTION_IDENTITY_KEY_NAMES_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
