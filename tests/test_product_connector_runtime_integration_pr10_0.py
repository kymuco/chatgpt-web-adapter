from __future__ import annotations

from typing import Any

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorObservation,
    ProductRequiredActionLifecycleObservation,
)
from chatgpt_web_adapter.product_observations import ProductObservationKind
from chatgpt_web_adapter.product_runtime_observation_gate import (
    gate_product_runtime_send_text_observed,
)
from chatgpt_web_adapter.product_transport import ProductRuntimeExecution
from chatgpt_web_adapter.types import ChatResponse


def _execution() -> ProductRuntimeExecution:
    return ProductRuntimeExecution(
        transport="browser-owned",
        response=ChatResponse(text="canonical answer"),
        observation={"write": "completed"},
    )


def test_runtime_collects_connector_required_action_and_continuation_in_order() -> None:
    events = [
        {
            "type": "product_connector_started",
            "observation_id": "connector:1:start",
            "connector_activity_id": "connector-activity:1",
            "connector_id": "calendar",
            "connector_name": "Calendar",
            "operation": "search_events",
        },
        {
            "type": "product_required_action_started",
            "observation_id": "action:1:start",
            "action_id": "action:1",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:1",
            "connector_id": "calendar",
        },
        {
            "type": "product_required_action_completed",
            "observation_id": "action:1:complete",
            "action_id": "action:1",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:1",
            "connector_id": "calendar",
        },
        {
            "type": "product_connector_completed",
            "observation_id": "connector:1:complete",
            "connector_activity_id": "connector-activity:1",
            "connector_id": "calendar",
            "operation": "search_events",
            "action_id": "action:1",
        },
    ]

    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            for event in events:
                on_event(event)
            return _execution()

    forwarded: list[dict[str, Any]] = []
    result = Runtime().send_text_observed("hello", on_event=forwarded.append)

    assert forwarded == events
    assert [item.kind for item in result.observations] == [
        ProductObservationKind.CONNECTOR,
        ProductObservationKind.REQUIRED_ACTION,
        ProductObservationKind.REQUIRED_ACTION,
        ProductObservationKind.CONNECTOR,
    ]
    assert isinstance(result.observations[0], ProductConnectorObservation)
    assert isinstance(result.observations[1], ProductRequiredActionLifecycleObservation)
    assert result.dropped_observation_event_count == 0
    assert result.response.text == "canonical answer"
    assert result.observation == {"write": "completed"}


def test_runtime_drops_conflicting_action_correlation_without_invalidating_write() -> None:
    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event(
                {
                    "type": "product_required_action_started",
                    "observation_id": "action:start",
                    "action_id": "action:stable",
                    "action_type": "user_authorization",
                    "connector_activity_id": "connector-activity:one",
                }
            )
            on_event(
                {
                    "type": "product_required_action_updated",
                    "observation_id": "action:conflict",
                    "action_id": "action:stable",
                    "action_type": "user_authorization",
                    "connector_activity_id": "connector-activity:two",
                }
            )
            return _execution()

    result = Runtime().send_text_observed("hello")

    assert len(result.observations) == 1
    assert result.observations[0].observation_id == "action:start"
    assert result.dropped_observation_event_count == 1
    assert result.response.text == "canonical answer"
