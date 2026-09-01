from __future__ import annotations

from chatgpt_web_adapter.product_artifact_observation_pr10_1 import (
    PRODUCT_ARTIFACT_OBSERVED,
    ProductArtifactObservation,
    ProductArtifactObservationCollector,
)
from chatgpt_web_adapter.product_connector_lifecycle_pr10_0 import ProductConnectorObservation
from chatgpt_web_adapter.product_observations import ProductObservationPhase


def _artifact_event(**overrides):
    event = {
        "type": PRODUCT_ARTIFACT_OBSERVED,
        "observation_id": "pr10.1:artifact:file-123",
        "artifact_id": "file-123",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 1234,
        "download_available": True,
        "source_origin": "product_message_metadata",
        "sequence": 7,
        "observed_at_ms": 42,
    }
    event.update(overrides)
    return event


def test_artifact_point_observation_materializes_without_locator():
    collector = ProductArtifactObservationCollector()

    value = collector.consume(_artifact_event())

    assert isinstance(value, ProductArtifactObservation)
    assert value.artifact_id == "file-123"
    assert value.filename == "report.pdf"
    assert value.media_type == "application/pdf"
    assert value.size_bytes == 1234
    assert value.download_available is True
    assert value.phase is ProductObservationPhase.OBSERVED
    assert value.to_dict()["kind"] == "ARTIFACT"
    assert "url" not in value.to_dict()
    assert "download_url" not in value.to_dict()
    assert collector.dropped_event_count == 0


def test_artifact_observation_requires_explicit_product_owned_id():
    collector = ProductArtifactObservationCollector()

    assert collector.consume(_artifact_event(artifact_id=None)) is None
    assert collector.dropped_event_count == 1
    assert collector.observations == ()


def test_artifact_observation_rejects_locator_even_when_other_fields_are_safe():
    for key in ("url", "href", "download_url", "signed_url", "access_token"):
        collector = ProductArtifactObservationCollector()
        assert collector.consume(_artifact_event(**{key: "https://example.test/private"})) is None
        assert collector.dropped_event_count == 1


def test_artifact_observation_rejects_filename_path_traversal():
    for filename in ("../report.pdf", "folder/report.pdf", r"folder\report.pdf", ".."):
        collector = ProductArtifactObservationCollector()
        assert collector.consume(_artifact_event(filename=filename)) is None
        assert collector.dropped_event_count == 1


def test_artifact_observation_rejects_malformed_optional_metadata():
    malformed = (
        {"media_type": "not a mime"},
        {"size_bytes": -1},
        {"size_bytes": True},
        {"download_available": "yes"},
        {"source_origin": "assistant_text"},
    )
    for overrides in malformed:
        collector = ProductArtifactObservationCollector()
        assert collector.consume(_artifact_event(**overrides)) is None
        assert collector.dropped_event_count == 1


def test_artifact_collector_preserves_pr10_connector_observations():
    collector = ProductArtifactObservationCollector()

    connector = collector.consume(
        {
            "type": "product_connector_observed",
            "observation_id": "pr10:connector:1",
            "connector_activity_id": "connector-message:m1",
            "connector_id": "gmail",
            "connector_name": "Gmail",
            "operation": "read",
        }
    )
    artifact = collector.consume(_artifact_event(sequence=2))

    assert isinstance(connector, ProductConnectorObservation)
    assert isinstance(artifact, ProductArtifactObservation)
    assert collector.observations == (connector, artifact)
    assert collector.dropped_event_count == 0
