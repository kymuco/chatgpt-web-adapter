from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chatgpt_web_adapter"
EXT = SRC / "browser_native_extension"
OBSERVABILITY = EXT / "service_worker_observability.js"


def test_pr88_selection_forensics_are_not_shipped_or_loaded() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")

    retired_workers = (
        "service_worker_retained_picker_forensics_pr8_8.js",
        "service_worker_retained_route_identity_pr8_8.js",
        "service_worker_instant_failure_forensics_pr8_8.js",
        "service_worker_instant_popup_subtree_forensics_pr8_8.js",
        "service_worker_picker_trigger_identity_pr8_8.js",
        "service_worker_picker_trigger_poll_timeline_pr8_8.js",
        "service_worker_picker_trigger_persistence_pr8_8.js",
        "service_worker_reasoning_effort_slider_topology_pr8_8.js",
        "service_worker_reasoning_effort_slider_governance_pr8_8.js",
        "service_worker_reasoning_effort_slider_geometry_pr8_8.js",
    )
    for name in retired_workers:
        assert name not in source
        assert not (EXT / name).exists()


def test_base_instant_selection_repair_remains_in_production() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")
    selection = EXT / "service_worker_instant_selection_repair_pr8_8.js"
    effort = EXT / "service_worker_instant_effort_selection.js"

    assert (
        'importScripts("service_worker_instant_selection_repair_pr8_8.js");' in source
    )
    assert 'importScripts("service_worker_instant_effort_selection.js");' in source
    assert selection.exists()
    assert effort.exists()

    base_code = selection.read_text(encoding="utf-8")
    effort_code = effort.read_text(encoding="utf-8")
    assert "async function _pr88SelectionPoint(" in base_code
    assert "function _pr88SelectionInstallNetworkWindow(" in base_code
    assert "async function _pr88SelectionEnsureInstant(" not in base_code
    assert "async function _pr88SelectionRawClick(" not in base_code
    assert "async function _pr88SelectionWaitForInstantOption(" not in base_code
    assert "async function _pr88SelectionEnsureInstant(" in effort_code
    assert "_pr88SelectionEnsureInstant =" not in effort_code


def test_retired_python_forensics_are_not_in_shipping_package() -> None:
    for name in (
        "browser_authority_retained_picker_forensics_pr8_8.py",
        "browser_authority_retained_route_identity_pr8_8.py",
        "browser_authority_instant_failure_forensics_pr8_8.py",
        "browser_authority_instant_failure_forensics_support_pr8_8.py",
        "browser_authority_picker_trigger_timeline_pr8_8.py",
        "browser_authority_reasoning_effort_slider_pr8_8.py",
    ):
        assert not (SRC / name).exists()
