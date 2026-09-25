from __future__ import annotations

from tools.browser_worker_ownership_closure_gate import (
    RETIRED_HISTORICAL_WORKERS,
    production_ownership_debt,
    production_worker_graph,
    source_ownership_debt,
)


def test_production_worker_graph_reaches_reviewed_shipping_owners() -> None:
    graph = set(production_worker_graph())

    assert "service_worker_temporary_chat_route_reopen_probe.js" in graph
    assert "service_worker_runtime.js" in graph
    assert "service_worker_observability.js" in graph
    assert "service_worker_selection_preparation.js" in graph
    assert "service_worker_ui_compat_pr11_7.js" in graph


def test_retired_temporary_characterization_stays_out_of_production_graph() -> None:
    graph = set(production_worker_graph())

    assert graph.isdisjoint(RETIRED_HISTORICAL_WORKERS)


def test_production_worker_surface_has_zero_ownership_debt() -> None:
    assert production_ownership_debt() == ()


def test_gate_detects_top_level_rebinding_and_captured_historical_alias() -> None:
    source = """const _exampleHistoricalOwner = publicOwner;
publicOwner =
  async function wrappedOwner() {
    return _exampleHistoricalOwner();
  };

function ordinaryHelper() {
  localValue = 1;
}
"""

    assert source_ownership_debt("fixture.js", source) == (
        "fixture.js:1:captured-historical-alias:_exampleHistoricalOwner->publicOwner",
        "fixture.js:2:top-level-rebinding:publicOwner",
    )


def test_normal_function_declarations_and_indented_state_updates_are_allowed() -> None:
    source = """async function publicOwner() {
  runtimeState = 1;
}

const helper = async () => true;
"""

    assert source_ownership_debt("fixture.js", source) == ()
