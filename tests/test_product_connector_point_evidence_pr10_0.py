from __future__ import annotations

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorLifecycleCollector,
    ProductConnectorObservation,
    ProductRequiredActionLifecycleObservation,
)
from chatgpt_web_adapter.product_observations import ProductObservationPhase


def test_connector_point_evidence_remains_observed_without_fabricated_lifecycle() -> None:
    collector = ProductConnectorLifecycleCollector()
    observation = collector.consume(
        {
            "type": "product_connector_observed",
            "observation_id": "connector:message:1",
            "connector_activity_id": "connector-message:assistant-1",
            "connector_id": "connector_googlecalendar",
            "connector_name": "google_calendar",
            "operation": "search_events",
        }
    )

    assert isinstance(observation, ProductConnectorObservation)
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert observation.connector_activity_id == "connector-message:assistant-1"
    assert collector.dropped_event_count == 0


def test_required_action_point_with_explicit_action_id_upgrades_to_correlated_value() -> None:
    collector = ProductConnectorLifecycleCollector()
    observation = collector.consume(
        {
            "type": "product_required_action_observed",
            "observation_id": "required:message:1",
            "action_id": "action:1",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-message:assistant-1",
            "connector_id": "connector_googlecalendar",
        }
    )

    assert isinstance(observation, ProductRequiredActionLifecycleObservation)
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert observation.action_id == "action:1"
    assert observation.connector_activity_id == "connector-message:assistant-1"
    assert collector.dropped_event_count == 0
