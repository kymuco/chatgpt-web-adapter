from __future__ import annotations

from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import (
    ProductConnectorLifecycleCollector,
    ProductConnectorObservation,
    ProductRequiredActionLifecycleObservation,
    ProductRequiredActionSurfaceObservation,
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


def test_required_action_surface_materializes_as_uncorrelated_point_evidence() -> None:
    collector = ProductConnectorLifecycleCollector()
    observation = collector.consume(
        {
            "type": "product_required_action_surface_observed",
            "observation_id": (
                "required-action-surface:gmail:connector_authorization_required"
            ),
            "connector_name": "gmail",
            "action_type": "connector_authorization_required",
            "connect_control_present": True,
            "dismiss_control_present": True,
            "stable_action_id_present": False,
        }
    )

    assert isinstance(observation, ProductRequiredActionSurfaceObservation)
    assert observation.kind.value == "REQUIRED_ACTION"
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert observation.connector_name == "gmail"
    assert observation.action_type == "connector_authorization_required"
    assert observation.stable_action_id_present is False
    assert "action_id" not in observation.to_dict()
    assert collector.dropped_event_count == 0


def test_required_action_surface_rejects_fabricated_or_ambiguous_lifecycle_identity() -> None:
    for event in (
        {
            "type": "product_required_action_surface_observed",
            "observation_id": "surface:missing-dismiss",
            "connector_name": "gmail",
            "action_type": "connector_authorization_required",
            "connect_control_present": True,
            "dismiss_control_present": False,
            "stable_action_id_present": False,
        },
        {
            "type": "product_required_action_surface_observed",
            "observation_id": "surface:stable-without-id-contract",
            "connector_name": "gmail",
            "action_type": "connector_authorization_required",
            "connect_control_present": True,
            "dismiss_control_present": True,
            "stable_action_id_present": True,
        },
        {
            "type": "product_required_action_surface_observed",
            "observation_id": "surface:smuggled-action-id",
            "connector_name": "gmail",
            "action_type": "connector_authorization_required",
            "connect_control_present": True,
            "dismiss_control_present": True,
            "stable_action_id_present": False,
            "action_id": "invented-action-id",
        },
    ):
        collector = ProductConnectorLifecycleCollector()
        assert collector.consume(event) is None
        assert collector.observations == ()
        assert collector.dropped_event_count == 1
