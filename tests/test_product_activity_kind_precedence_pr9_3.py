from __future__ import annotations

import pytest

from chatgpt_web_adapter.product_observations import (
    ProductObservationCollector,
    ProductObservationKind,
    ProductObservationPhase,
)


@pytest.mark.parametrize("operation", ["calculator", "weather", "finance", "sports", "time"])
def test_explicit_non_search_operation_beats_coarse_web_activity_kind(operation: str) -> None:
    collector = ProductObservationCollector()

    observation = collector.consume(
        {
            "type": "activity_started",
            "activity_id": f"typed-web:{operation}",
            "activity_kind": "web",
            "tool_name": "web.run",
            "operation": operation,
            "label": "Using product tool",
        }
    )

    assert observation is not None
    assert observation.kind is ProductObservationKind.TOOL
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert observation.operation == operation
    assert observation.activity_kind == "web"
    assert observation.tool_name == "web.run"


@pytest.mark.parametrize(
    "operation",
    [
        "search_query",
        "open",
        "click",
        "find",
        "screenshot",
        "image_query",
        "product_query",
        "businesses_query",
        "availability_query",
    ],
)
def test_explicit_search_operation_remains_search(operation: str) -> None:
    collector = ProductObservationCollector()

    observation = collector.consume(
        {
            "type": "activity_started",
            "activity_id": f"typed-tool:{operation}",
            "activity_kind": "tool",
            "operation": operation,
        }
    )

    assert observation is not None
    assert observation.kind is ProductObservationKind.SEARCH
    assert observation.phase is ProductObservationPhase.OBSERVED


def test_coarse_web_without_operation_remains_search() -> None:
    collector = ProductObservationCollector()

    observation = collector.consume(
        {
            "type": "activity_started",
            "activity_id": "tool-web:request",
            "activity_kind": "web",
            "tool_name": "web.run",
        }
    )

    assert observation is not None
    assert observation.kind is ProductObservationKind.SEARCH
    assert observation.phase is ProductObservationPhase.OBSERVED


def test_code_activity_without_operation_remains_tool() -> None:
    collector = ProductObservationCollector()

    observation = collector.consume(
        {
            "type": "activity_started",
            "activity_id": "code:request",
            "activity_kind": "code",
        }
    )

    assert observation is not None
    assert observation.kind is ProductObservationKind.TOOL
