from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pr10_1_artifact_surface_live_gate import (  # noqa: E402
    PROBE_FILENAME,
    ProductArtifactSurfaceProvider,
    _EXPECTED_SURFACE_SUPPORT,
    _safe_name_list,
)


EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SURFACE_WORKER = EXTENSION / "service_worker_generated_artifact_surface_overlay_pr10_1.js"
OBSERVABILITY_WORKER = EXTENSION / "service_worker_observability.js"
MANIFEST = EXTENSION / "manifest.json"


def test_artifact_surface_preserves_historical_manifest_entrypoint() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert manifest["version"] == "0.1.13"


def test_surface_worker_is_additive_observability_overlay() -> None:
    source = SURFACE_WORKER.read_text(encoding="utf-8")
    observability = OBSERVABILITY_WORKER.read_text(encoding="utf-8")
    assert (
        'importScripts("service_worker_generated_artifact_surface_overlay_pr10_1.js");'
        in observability
    )
    assert "importScripts(" not in source
    assert "_pr101ArtifactSurfacePriorExecuteNativeTurn = executeNativeTurn" in source
    assert "return _pr101ArtifactSurfacePriorExecuteNativeTurn(message);" in source


def test_surface_worker_requires_assistant_owned_filename_match() -> None:
    source = SURFACE_WORKER.read_text(encoding="utf-8")
    assert PROBE_FILENAME in source
    assert "String(node.nodeValue || '').trim() !== probeFilename" in source
    assert "ownership.role === 'user'" in source
    assert "ownership.role !== 'assistant'" in source
    assert "userOwnedExactFilenameMatchCount" in source
    assert "roleUnprovenExactFilenameMatchCount" in source
    assert "assistantRoleEvidenceKinds" in source
    assert "assistantOwnershipRequired: true" in source
    assert "userTurnMatchesExcluded: true" in source
    assert "data-message-author-role" in source
    assert "data-turn" in source


def test_surface_worker_is_no_write_no_click_no_download() -> None:
    source = SURFACE_WORKER.read_text(encoding="utf-8")
    assert "clickPerformed: false" in source
    assert "downloadAttempted: false" in source
    assert "writePerformed: false" in source
    assert "rawDomExported: false" in source
    assert "rawTextExported: false" in source
    assert "locatorValuesExported: false" in source
    assert "attributeValuesExported: false" in source


def test_surface_worker_exports_locator_presence_not_locator_value() -> None:
    source = SURFACE_WORKER.read_text(encoding="utf-8")
    assert "hasAttribute('href')" in source
    assert "hasAttribute('download')" in source
    assert "hrefAttributePresent" in source
    assert "downloadAttributePresent" in source
    assert ".href" not in source
    assert "getAttribute('href')" not in source
    assert "hrefValue" not in source
    assert "downloadUrl" not in source
    assert "signedUrl" not in source


def test_surface_support_normalizes_exact_no_write_contract(monkeypatch) -> None:
    provider = ProductArtifactSurfaceProvider()

    def fake_rpc(_message, *, timeout):
        assert timeout > 0
        return {
            "request_id": _message["request_id"],
            "ok": True,
            "generatedArtifactSurfaceCharacterizationSupported": True,
            "generatedArtifactSurfaceCharacterizationSchemaVersion": 1,
            "fixedProbeFilename": PROBE_FILENAME,
            "assistantOwnershipRequired": True,
            "userTurnMatchesExcluded": True,
            "rawDomExported": False,
            "rawTextExported": False,
            "locatorValuesExported": False,
            "attributeValuesExported": False,
            "clickPerformed": False,
            "downloadAttempted": False,
            "writePerformed": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    support, diagnostic = provider.artifact_surface_support(timeout=1.0)
    assert support == _EXPECTED_SURFACE_SUPPORT
    assert support["assistant_ownership_required"] is True
    assert support["user_turn_matches_excluded"] is True
    assert diagnostic["failure_reason"] is None
    assert diagnostic["surface_support_fields_present"] is True


def test_surface_snapshot_exposes_role_counts_names_and_presence_only(monkeypatch) -> None:
    provider = ProductArtifactSurfaceProvider()

    def fake_rpc(_message, *, timeout):
        assert timeout > 0
        return {
            "request_id": _message["request_id"],
            "ok": True,
            "schema": 1,
            "fixedProbeFilename": PROBE_FILENAME,
            "runtimeTabPresent": True,
            "surfaceReady": True,
            "exactFilenameVisible": True,
            "exactFilenameMatchCount": 1,
            "anyExactFilenameMatchCount": 3,
            "userOwnedExactFilenameMatchCount": 1,
            "roleUnprovenExactFilenameMatchCount": 1,
            "assistantRoleEvidenceKinds": ["data_turn"],
            "candidateTagNames": ["span"],
            "candidateAttributeNames": ["data-testid", "bad value"],
            "ancestorAttributeNames": ["class", "data-testid"],
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
    snapshot, diagnostic = provider.artifact_surface_snapshot(timeout=1.0)
    assert diagnostic["snapshot_contract_ok"] is True
    assert diagnostic["failure_reason"] is None
    assert snapshot is not None
    assert snapshot["exact_filename_visible"] is True
    assert snapshot["exact_filename_match_count"] == 1
    assert snapshot["any_exact_filename_match_count"] == 3
    assert snapshot["user_owned_exact_filename_match_count"] == 1
    assert snapshot["role_unproven_exact_filename_match_count"] == 1
    assert snapshot["assistant_role_evidence_kinds"] == ["data_turn"]
    assert snapshot["candidate_attribute_names"] == ["data-testid"]
    assert snapshot["interactive_attribute_names"] == ["download", "href"]
    assert snapshot["href_attribute_present"] is True
    assert "href_value" not in snapshot
    assert "raw_dom" not in snapshot


def test_safe_name_list_is_ascii_bounded_and_rejects_smuggled_content() -> None:
    assert _safe_name_list(
        ["data-testid", "href", "hello world", "a/b", "token=value", "друг", 7]
    ) == ["data-testid", "href"]
