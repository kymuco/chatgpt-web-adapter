from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

FILES = (
    "service_worker_generated_artifact_shape_pr10_1.js",
    "service_worker_generated_artifact_surface_overlay_pr10_1.js",
    "service_worker_generated_artifact_surface_v2_overlay_pr10_1.js",
    "service_worker_generated_artifact_topology_v3_pr10_1.js",
    "service_worker_generated_artifact_noncode_v4_pr10_1.js",
    "service_worker_generated_artifact_action_v5_pr10_1.js",
    "service_worker_generated_artifact_fiber_state_v6_pr10_1.js",
    "service_worker_generated_artifact_subtree_v7_pr10_1.js",
    "service_worker_generated_artifact_root_shape_v8_pr10_1.js",
    "service_worker_generated_artifact_root_key_shape_v9_pr10_1.js",
    "service_worker_generated_artifact_array_element_shape_v10_pr10_1.js",
)

OWNER = FILES[-1]

EXPECTED_HANDLER_ORDER = (
    "_pr101ExecuteNativeTurnWithArtifactArrayElementShapeV10(message)",
    "_pr101ExecuteNativeTurnWithArtifactRootKeyShapeV9(message)",
    "_pr101ExecuteNativeTurnWithArtifactRootShapeV8(message)",
    "_pr101ExecuteNativeTurnWithArtifactSubtreeV7(message)",
    "_pr101ExecuteNativeTurnWithArtifactFiberStateV6(message)",
    "_pr101ExecuteNativeTurnWithArtifactActionV5(message)",
    "_pr101ExecuteNativeTurnWithArtifactNonCodeV4(message)",
    "_pr101ExecuteNativeTurnWithArtifactTopologyV3(message)",
    "_pr101ExecuteNativeTurnWithArtifactSurfaceV2(message)",
    "_pr101ExecuteNativeTurnWithArtifactSurfaceProbe(message)",
    "_pr101ArtifactShapeSupportOverlay(message)",
)


def _source(name: str) -> str:
    return (EXTENSION / name).read_text(encoding="utf-8")


def test_generated_artifact_modules_do_not_own_ordinary_turn_dispatch() -> None:
    for name in FILES:
        source = _source(name)
        assert "executeNativeTurn = async function" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_generated_artifact_characterization_has_one_explicit_owner() -> None:
    owner = _source(OWNER)
    assert 'registerNativeTurnDiagnosticHandler(' in owner
    assert '"generated-artifact-characterization"' in owner
    assert "_cwaGeneratedArtifactCharacterizationMatches" in owner
    assert "_cwaHandleGeneratedArtifactCharacterization" in owner

    for name in FILES[:-1]:
        source = _source(name)
        assert '"generated-artifact-characterization"' not in source


def test_generated_artifact_owner_preserves_historical_outer_to_inner_precedence() -> None:
    owner = _source(OWNER)
    positions = [owner.index(marker) for marker in EXPECTED_HANDLER_ORDER]
    assert positions == sorted(positions)


def test_generated_artifact_owner_claims_characterization_only() -> None:
    owner = _source(OWNER)
    matches_start = owner.index("function _cwaGeneratedArtifactCharacterizationMatches")
    handle_start = owner.index("async function _cwaHandleGeneratedArtifactCharacterization")
    matches = owner[matches_start:handle_start]

    assert "message?.text" not in matches
    assert "message?.conversationId" not in matches
    assert "message?.attachmentPaths" not in matches
    assert "characterizeGeneratedArtifact" in matches
    assert "=== true" in matches


def test_observability_keeps_generated_artifact_module_order() -> None:
    observability = _source("service_worker_observability.js")
    positions = [
        observability.index(f'importScripts("{name}");')
        for name in FILES
    ]
    assert positions == sorted(positions)
