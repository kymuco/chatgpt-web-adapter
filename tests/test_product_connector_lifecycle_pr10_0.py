from __future__ import annotations

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorLifecycleCollector,
    ProductConnectorObservation,
    ProductRequiredActionLifecycleObservation,
)
from chatgpt_web_adapter.product_observations import (
    ProductObservationKind,
    ProductObservationPhase,
    ProductSourceObservation,
)


def test_connector_lifecycle_preserves_explicit_product_correlation() -> None:
    collector = ProductConnectorLifecycleCollector()

    started = collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "connector-observation:1",
            "connector_activity_id": "connector-activity:calendar:1",
            "connector_id": "calendar",
            "connector_name": "Calendar",
            "operation": "search_events",
            "label": "Searching calendar",
            "sequence": 10,
            "observed_at_ms": 100,
        }
    )
    updated = collector.consume(
        {
            "type": "product_connector_updated",
            "observation_id": "connector-observation:2",
            "connector_activity_id": "connector-activity:calendar:1",
            "connector_id": "calendar",
            "operation": "search_events",
            "label": "Reading calendar results",
            "sequence": 11,
            "observed_at_ms": 120,
        }
    )
    completed = collector.consume(
        {
            "type": "product_connector_completed",
            "observation_id": "connector-observation:3",
            "connector_activity_id": "connector-activity:calendar:1",
            "connector_id": "calendar",
            "operation": "search_events",
            "sequence": 12,
            "observed_at_ms": 140,
        }
    )

    assert isinstance(started, ProductConnectorObservation)
    assert started.kind is ProductObservationKind.CONNECTOR
    assert started.phase is ProductObservationPhase.STARTED
    assert started.connector_activity_id == "connector-activity:calendar:1"
    assert isinstance(updated, ProductConnectorObservation)
    assert updated.phase is ProductObservationPhase.UPDATED
    assert isinstance(completed, ProductConnectorObservation)
    assert completed.phase is ProductObservationPhase.COMPLETED
    assert collector.dropped_event_count == 0


def test_required_action_lifecycle_can_reference_connector_without_granting_authority() -> None:
    collector = ProductConnectorLifecycleCollector()

    started = collector.consume(
        {
            "type": "product_required_action_started",
            "observation_id": "required-observation:1",
            "action_id": "required-action:calendar-auth:1",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:calendar:1",
            "connector_id": "calendar",
            "label": "Authorization required",
        }
    )
    completed = collector.consume(
        {
            "type": "product_required_action_completed",
            "observation_id": "required-observation:2",
            "action_id": "required-action:calendar-auth:1",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:calendar:1",
            "connector_id": "calendar",
            "label": "Authorization resolved",
        }
    )

    assert isinstance(started, ProductRequiredActionLifecycleObservation)
    assert started.kind is ProductObservationKind.REQUIRED_ACTION
    assert started.phase is ProductObservationPhase.STARTED
    assert started.action_id == "required-action:calendar-auth:1"
    assert started.connector_activity_id == "connector-activity:calendar:1"
    assert isinstance(completed, ProductRequiredActionLifecycleObservation)
    assert completed.phase is ProductObservationPhase.COMPLETED
    assert not hasattr(started, "approve")
    assert not hasattr(started, "execute")


def test_same_action_id_cannot_be_rebound_to_another_connector_activity() -> None:
    collector = ProductConnectorLifecycleCollector()

    assert collector.consume(
        {
            "type": "product_required_action_started",
            "observation_id": "required-observation:1",
            "action_id": "action:stable",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:one",
            "connector_id": "calendar",
        }
    ) is not None

    conflict = collector.consume(
        {
            "type": "product_required_action_updated",
            "observation_id": "required-observation:2",
            "action_id": "action:stable",
            "action_type": "user_authorization",
            "connector_activity_id": "connector-activity:two",
            "connector_id": "calendar",
        }
    )

    assert conflict is None
    assert collector.dropped_event_count == 1
    assert len(collector.observations) == 1


def test_same_connector_activity_id_cannot_change_connector_identity() -> None:
    collector = ProductConnectorLifecycleCollector()

    assert collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "connector-observation:1",
            "connector_activity_id": "connector-activity:stable",
            "connector_id": "calendar",
            "operation": "search_events",
        }
    ) is not None

    conflict = collector.consume(
        {
            "type": "product_connector_updated",
            "observation_id": "connector-observation:2",
            "connector_activity_id": "connector-activity:stable",
            "connector_id": "drive",
            "operation": "search_events",
        }
    )

    assert conflict is None
    assert collector.dropped_event_count == 1


def test_terminal_lifecycle_cannot_flip_outcome_or_resume() -> None:
    collector = ProductConnectorLifecycleCollector()

    assert collector.consume(
        {
            "type": "product_connector_completed",
            "observation_id": "connector-observation:complete",
            "connector_activity_id": "connector-activity:terminal",
            "connector_id": "calendar",
        }
    ) is not None

    assert collector.consume(
        {
            "type": "product_connector_failed",
            "observation_id": "connector-observation:failed",
            "connector_activity_id": "connector-activity:terminal",
            "connector_id": "calendar",
        }
    ) is None
    assert collector.consume(
        {
            "type": "product_connector_updated",
            "observation_id": "connector-observation:late-update",
            "connector_activity_id": "connector-activity:terminal",
            "connector_id": "calendar",
        }
    ) is None
    assert collector.dropped_event_count == 2


def test_sensitive_connector_payload_fields_never_escape_typed_observation() -> None:
    collector = ProductConnectorLifecycleCollector()
    observation = collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "connector-observation:private",
            "connector_activity_id": "connector-activity:private",
            "connector_id": "drive",
            "connector_name": "Drive",
            "operation": "search_files",
            "arguments": {"query": "private", "access_token": "secret"},
            "result": {"raw": "private result"},
            "authorization": "Bearer secret",
            "cookies": "secret",
            "signed_url": "https://example.test/file?X-Amz-Signature=secret",
        }
    )

    assert isinstance(observation, ProductConnectorObservation)
    payload = observation.to_dict()
    assert payload == {
        "observation_id": "connector-observation:private",
        "connector_activity_id": "connector-activity:private",
        "phase": "STARTED",
        "connector_id": "drive",
        "connector_name": "Drive",
        "operation": "search_files",
        "action_id": None,
        "label": None,
        "sequence": None,
        "observed_at_ms": None,
        "kind": "CONNECTOR",
    }
    rendered = repr(payload)
    assert "access_token" not in rendered
    assert "Bearer secret" not in rendered
    assert "private result" not in rendered
    assert "X-Amz-Signature" not in rendered


def test_pr93_observations_remain_in_order_through_pr100_collector() -> None:
    collector = ProductConnectorLifecycleCollector()

    source = collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:1",
            "source_id": "source:1",
            "url": "https://example.test/article",
        }
    )
    connector = collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "connector-observation:1",
            "connector_activity_id": "connector-activity:1",
            "connector_id": "calendar",
        }
    )

    assert isinstance(source, ProductSourceObservation)
    assert isinstance(connector, ProductConnectorObservation)
    assert collector.observations == (source, connector)
    assert collector.dropped_event_count == 0


def test_legacy_required_action_point_observation_remains_compatible() -> None:
    collector = ProductConnectorLifecycleCollector()
    observation = collector.consume(
        {
            "type": "product_required_action_observed",
            "observation_id": "required:legacy",
            "action_type": "user_confirmation",
            "label": "Confirmation required",
        }
    )

    assert observation is not None
    assert observation.kind is ProductObservationKind.REQUIRED_ACTION
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert collector.dropped_event_count == 0


def test_malformed_lifecycle_events_fail_closed_without_raising() -> None:
    collector = ProductConnectorLifecycleCollector()

    assert collector.consume(
        {
            "type": "product_connector_started",
            "observation_id": "missing-activity-id",
        }
    ) is None
    assert collector.consume(
        {
            "type": "product_required_action_started",
            "observation_id": "missing-action-id",
            "action_type": "user_authorization",
        }
    ) is None

    assert collector.observations == ()
    assert collector.dropped_event_count == 2
