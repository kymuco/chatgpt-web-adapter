from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.non_tab_product_execution_feasibility import (
    SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT,
    base_non_tab_feasibility_report,
    qualifying_surface_ids,
    run_current_write_surface_probe,
)


def test_supported_non_tab_product_verdict_is_negative_and_reopenable() -> None:
    report = base_non_tab_feasibility_report()
    assert report["verdict"] == (
        "SUPPORTED_NON_TAB_ORDINARY_CHATGPT_PRODUCT_EXECUTION_NOT_FOUND"
    )
    assert report["supported_non_tab_ordinary_chatgpt_product_execution_available"] is False
    assert report["qualifying_surface_ids"] == []
    assert qualifying_surface_ids() == []
    assert SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT == report["verdict"]
    assert report["governance"]["verdict_reopenable_if_new_supported_surface_appears"] is True


def test_surface_matrix_closes_non_qualifying_hidden_candidates() -> None:
    matrix = {
        row["gate"]: row
        for row in base_non_tab_feasibility_report()["surfaces"]
    }
    assert set(matrix) == {"N0", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"}
    assert matrix["N0"]["verdict"] == "PROVEN_BASELINE"
    assert matrix["N1"]["verdict"] == "REJECTED_NO_DOM_WINDOW"
    assert matrix["N2"]["verdict"] == "REJECTED_EXTENSION_URL_ONLY"
    assert matrix["N3"]["verdict"] == "DOES_NOT_MEET_TOP_LEVEL_PRODUCT_CONTRACT"
    assert matrix["N5"]["verdict"] == "ATTACHMENT_PRIMITIVE_NOT_EXECUTION_SURFACE"
    assert matrix["N7"]["verdict"] == SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT
    assert matrix["N8"]["verdict"] == "ONE_REUSABLE_INACTIVE_TAB"


def test_report_keeps_strict_product_semantics_and_safety_boundaries() -> None:
    governance = base_non_tab_feasibility_report()["governance"]
    assert governance["supported_browser_surfaces_only"] is True
    assert governance["ordinary_top_level_chatgpt_semantics_required"] is True
    assert governance["embedded_iframe_not_equated_with_top_level_product_runtime"] is True
    assert governance["direct_private_product_write"] is False
    assert governance["credential_extraction_or_replay"] is False
    assert governance["browser_protection_emulation"] is False
    assert governance["challenge_solver_expansion"] is False
    assert governance["non_tab_write_probe_performed"] is False
    assert governance["current_reusable_inactive_tab_baseline_preserved"] is True


def test_current_surface_probe_is_read_only_and_reports_existing_tab() -> None:
    calls = []

    class Provider:
        def status(self):
            calls.append("status")
            return SimpleNamespace(
                available=True,
                extension_connected=True,
                runtime_tab_id=17,
            )

        def send_text(self, *args, **kwargs):
            raise AssertionError("feasibility probe must not send a product turn")

    result = run_current_write_surface_probe(Provider()).to_dict()
    assert calls == ["status"]
    assert result == {
        "attempted": True,
        "bridge_available": True,
        "extension_connected": True,
        "runtime_tab_id": 17,
        "runtime_tab_present": True,
        "observed_surface": "REUSABLE_TAB_PRESENT",
    }


def test_current_surface_probe_reports_on_demand_baseline_without_tab() -> None:
    provider = SimpleNamespace(
        status=lambda: SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=None,
        )
    )
    result = run_current_write_surface_probe(provider)
    assert result.runtime_tab_present is False
    assert result.observed_surface == "TAB_ON_DEMAND_BASELINE"
