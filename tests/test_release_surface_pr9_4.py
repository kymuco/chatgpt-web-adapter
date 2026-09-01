from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter as adapter

from tools import installed_wheel_smoke, release_gate


def test_release_gate_requires_frozen_cwa_0_3_product_modules() -> None:
    required = release_gate.REQUIRED_WHEEL_FILES
    for path in (
        "chatgpt_web_adapter/product_runtime.py",
        "chatgpt_web_adapter/product_transport.py",
        "chatgpt_web_adapter/product_capabilities.py",
        "chatgpt_web_adapter/product_provenance.py",
        "chatgpt_web_adapter/product_observations.py",
        "chatgpt_web_adapter/public_surface.py",
        "chatgpt_web_adapter/product_rich_input_capability_gate_pr9_4.py",
        "chatgpt_web_adapter/product_web_search_capability_gate_pr9_3.py",
    ):
        assert path in required


def test_sdist_gate_requires_cwa_0_3_runtime_source_contract() -> None:
    required = release_gate.REQUIRED_SDIST_SUFFIXES
    for suffix in (
        "/CHANGELOG.md",
        "/src/chatgpt_web_adapter/product_runtime.py",
        "/src/chatgpt_web_adapter/product_observations.py",
        "/src/chatgpt_web_adapter/public_surface.py",
        "/src/chatgpt_web_adapter/product_rich_input_capability_gate_pr9_4.py",
    ):
        assert suffix in required


def test_manifest_in_explicitly_packages_release_changelog() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "MANIFEST.in").read_text(encoding="utf-8")
    assert "include CHANGELOG.md" in {
        line.strip()
        for line in manifest.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_installed_surface_validator_matches_frozen_source_public_surface() -> None:
    report = installed_wheel_smoke._validate_installed_0_3_surface(adapter)

    assert report["product_modules"] == len(
        installed_wheel_smoke.REQUIRED_PRODUCT_MODULES
    )
    assert report["primary_root_exports"] == len(
        installed_wheel_smoke.REQUIRED_PRIMARY_ROOT_EXPORTS
    )
    assert report["shared_root_exports"] == len(
        installed_wheel_smoke.REQUIRED_SHARED_ROOT_EXPORTS
    )


def test_internal_observation_collector_remains_outside_release_public_surface() -> None:
    assert "ProductObservationCollector" not in adapter.__all__
    assert adapter.public_surface_tier("ProductObservationCollector") is None
