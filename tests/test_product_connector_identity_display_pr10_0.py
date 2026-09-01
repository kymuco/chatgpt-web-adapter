from __future__ import annotations

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorLifecycleCollector,
    ProductConnectorObservation,
)


def test_connector_display_name_can_change_without_rebinding_identity() -> None:
    collector = ProductConnectorLifecycleCollector()

    first = collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "connector:start",
            "connector_activity_id": "connector-activity:stable",
            "connector_id": "connector_googlecalendar",
            "connector_name": "google_calendar",
            "operation": "search_events",
        }
    )
    second = collector.consume(
        {
            "type": "product_connector_updated",
            "observation_id": "connector:update",
            "connector_activity_id": "connector-activity:stable",
            "connector_id": "connector_googlecalendar",
            "connector_name": "google_calendar_localized",
            "operation": "search_events",
        }
    )

    assert isinstance(first, ProductConnectorObservation)
    assert isinstance(second, ProductConnectorObservation)
    assert second.connector_name == "google_calendar_localized"
    assert collector.dropped_event_count == 0
