from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OBSERVABILITY = EXT / "service_worker_observability.js"


def test_orphan_lease_research_surface_is_not_shipped_or_loaded() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    assert "service_worker_orphan_lease_reconciliation_pr8_8.js" not in source
    assert "orphan-lease-reconciliation" not in source
    assert "reconcileOrphanedBrowserAuthorityLease" not in source
    assert not (EXT / "service_worker_orphan_lease_reconciliation_pr8_8.js").exists()
    assert not (
        ROOT
        / "src"
        / "chatgpt_web_adapter"
        / "browser_authority_orphan_lease_reconciliation_pr8_8.py"
    ).exists()


def test_closed_artifact_characterization_has_no_dormant_runtime_imports() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    assert "PR101_ARTIFACT_CHARACTERIZATION_ENABLED" not in source
    for worker in (
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
    ):
        assert worker not in source
        assert not (EXT / worker).exists()


def test_live_generated_artifact_observation_remains_in_runtime() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")
    owner = EXT / "service_worker_product_observation.js"

    assert 'importScripts("service_worker_product_observation.js");' in source
    assert "service_worker_generated_artifact_pr10_1.js" not in source
    owner_source = owner.read_text(encoding="utf-8")
    assert 'const PR101_ARTIFACT_EVENT = "product_artifact_observed";' in owner_source
    assert "function _pr101GeneratedArtifactInspectMessageLayer(" in owner_source
