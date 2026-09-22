from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chatgpt_web_adapter"
EXT = SRC / "browser_native_extension"


def test_retained_picker_and_route_forensics_are_not_shipped() -> None:
    observability = (EXT / "service_worker_observability.js").read_text(
        encoding="utf-8"
    )

    for name in (
        "service_worker_retained_picker_forensics_pr8_8.js",
        "service_worker_retained_route_identity_pr8_8.js",
    ):
        assert name not in observability
        assert not (EXT / name).exists()

    for name in (
        "browser_authority_retained_picker_forensics_pr8_8.py",
        "browser_authority_retained_route_identity_pr8_8.py",
    ):
        assert not (SRC / name).exists()


def test_failure_and_reasoning_providers_attach_to_selection_provider_directly() -> None:
    failure = (
        SRC / "browser_authority_instant_failure_forensics_support_pr8_8.py"
    ).read_text(encoding="utf-8")
    reasoning = (
        SRC / "browser_authority_reasoning_effort_slider_pr8_8.py"
    ).read_text(encoding="utf-8")

    assert "RetainedRouteIdentityProvider" not in failure
    assert "RetainedPickerForensicsProvider" not in reasoning
    assert "InstantSelectionRepairProvider" in failure
    assert "InstantSelectionRepairProvider" in reasoning


def test_instant_failure_support_no_longer_claims_retained_forensics() -> None:
    worker = (
        EXT / "service_worker_instant_failure_forensics_pr8_8.js"
    ).read_text(encoding="utf-8")
    support = (
        SRC / "browser_authority_instant_failure_forensics_support_pr8_8.py"
    ).read_text(encoding="utf-8")

    for token in (
        "retainedRouteForensicsCompositionSupported",
        "retainedPickerForensicsCompositionSupported",
        "retained_route_forensics_composition_supported",
        "retained_picker_forensics_composition_supported",
    ):
        assert token not in worker
        assert token not in support
