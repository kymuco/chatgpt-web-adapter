from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_surface_v2_live_gate import (  # noqa: E402
    PROBE_FILENAME,
    ProductArtifactSurfaceV2Provider,
    _EXPECTED_SUPPORT,
    _safe_name_list,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WORKER = EXTENSION / "service_worker_generated_artifact_surface_v2_overlay_pr10_1.js"
OBSERVABILITY = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"
GATE = TOOLS / "pr10_1_artifact_surface_v2_live_gate.py"


def test_v2_surface_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_v2_surface_overlay_loads_after_v1_without_replacing_chain() -> None:
    observability = OBSERVABILITY.read_text(encoding="utf-8")
    v1 = 'importScripts("service_worker_generated_artifact_surface_overlay_pr10_1.js");'
    v2 = 'importScripts("service_worker_generated_artifact_surface_v2_overlay_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert v1 in observability
    assert v2 in observability
    assert observability.index(v1) < observability.index(v2) < observability.index(patch)


def test_v2_surface_requires_ordered_probe_pair_and_assistant_anchor() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert PROBE_FILENAME in source
    assert "CWA_PR10_1_ARTIFACT_PROBE" in source
    assert "ARTIFACT_PROBE_CREATED" in source
    assert "orderedProbeTurnPairPresent" in source
    assert "probePlacementProven" in source
    assert "targetAssistantTurns" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role === 'assistant'" in source
    assert "userPromptCannotBecomeArtifactEvidence: true" in source
    assert "assistantTurnAnchorRequired: true" in source


def test_v2_filename_search_is_assistant_target_bounded_and_substring_capable() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "for (const targetTurn of targetAssistantTurns.slice(0, 8))" in source
    assert "value.includes(probeFilename)" in source
    assert "interactiveText.includes(probeFilename)" in source
    assert "targetTurn.querySelectorAll('a,button,[role=\"button\"]')" in source
    assert ".slice(0, 256)" in source
    assert "matchedInteractiveElements" in source
    assert "matchedNonInteractiveElements" in source


def test_v2_exports_locator_presence_but_never_locator_value() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "hasAttribute('href')" in source
    assert "hasAttribute('download')" in source
    assert "hrefAttributePresent" in source
    assert "downloadAttributePresent" in source
    assert "getAttribute('href')" not in source
    assert "hrefValue" not in source
    assert "downloadUrl" not in source
    assert "signedUrl" not in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "attributeValuesExported: false" in source
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source


def test_v2_support_normalizes_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactSurfaceV2Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "generatedArtifactSurfaceV2CharacterizationSupported": True,
            "generatedArtifactSurfaceV2CharacterizationSchemaVersion": 2,
            "fixedProbeFilename": PROBE_FILENAME,
            "orderedProbePairRequired": True,
            "assistantTurnAnchorRequired": True,
            "userPromptCannotBecomeArtifactEvidence": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "locatorValuesExported": False,
            "attributeValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support, diagnostic = provider.surface_support(timeout=1.0)
    assert support == _EXPECTED_SUPPORT
    assert diagnostic["failure_reason"] is None
    assert diagnostic["support_fields_present"] is True


def test_v2_snapshot_exposes_placement_and_shape_only(monkeypatch) -> None:
    provider = ProductArtifactSurfaceV2Provider()

    def fake_rpc(message, *, timeout):
        assert timeout > 0
        return {
            "request_id": message["request_id"],
            "ok": True,
            "schema": 2,
            "fixedProbeFilename": PROBE_FILENAME,
            "runtimeTabPresent": True,
            "runtimeRouteKind": "conversation",
            "runtimeConversationIdPresent": True,
            "surfaceReady": True,
            "selectorKind": "conversation_testid",
            "visibleTurnCount": 2,
            "userTurnCount": 1,
            "assistantTurnCount": 1,
            "roleUnprovenTurnCount": 0,
            "userProbeMarkerTurnCount": 1,
            "assistantCompletionMarkerTurnCount": 1,
            "orderedProbeTurnPairPresent": True,
            "probePlacementProven": True,
            "placementRoleEvidenceKinds": ["data_turn"],
            "assistantFilenameSubstringMatchCount": 1,
            "assistantInteractiveFilenameMatchCount": 1,
            "assistantNonInteractiveFilenameMatchCount": 0,
            "filenameMatchSurfaces": ["text_node_substring", "aria_label"],
            "candidateTagNames": ["span"],
            "candidateAttributeNames": ["class", "bad value"],
            "ancestorAttributeNames": ["data-testid"],
            "interactiveKinds": ["a"],
            "interactiveAttributeNames": ["href", "download"],
            "hrefAttributePresent": True,
            "downloadAttributePresent": False,
            "conversationTurnAncestorPresent": True,
            "reactFiberPropertyPresent": True,
            "reactPropsPropertyPresent": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "locatorValuesExported": False,
            "attributeValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
            "debuggerAttachedAfter": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    snapshot, diagnostic = provider.surface_snapshot(timeout=1.0)
    assert snapshot is not None
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot["runtime_route_kind"] == "conversation"
    assert snapshot["runtime_conversation_id_present"] is True
    assert snapshot["probe_placement_proven"] is True
    assert snapshot["user_probe_marker_turn_count"] == 1
    assert snapshot["assistant_completion_marker_turn_count"] == 1
    assert snapshot["assistant_filename_substring_match_count"] == 1
    assert snapshot["assistant_interactive_filename_match_count"] == 1
    assert snapshot["candidate_attribute_names"] == ["class"]
    assert snapshot["interactive_attribute_names"] == ["download", "href"]
    assert snapshot["href_attribute_present"] is True
    assert "href_value" not in snapshot
    assert "raw_dom" not in snapshot


def test_v2_safe_name_list_is_ascii_bounded() -> None:
    assert _safe_name_list(
        ["data-testid", "href", "hello world", "a/b", "token=value", "друг", 7]
    ) == ["data-testid", "href"]


def test_v2_gate_has_zero_write_and_zero_download_paths() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "PRODUCT_WRITE_BUDGET = 0" in source
    assert "SURFACE_READ_BUDGET = 1" in source
    assert "DOWNLOAD_BUDGET = 0" in source
    assert "LOCAL_WRITE_BUDGET = 0" in source
    assert "send_text_observed(" not in source
    assert "run_gate(" in source
    assert "--acknowledge-live-read" in source
    assert "PROBE_TURN_PROVEN_NO_FRONTEND_FILENAME_SURFACE_OBSERVED" in source
    assert 'report["ok"] = placement_proven' in source
