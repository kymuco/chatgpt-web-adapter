from __future__ import annotations

from typing import Any

from chatgpt_web_adapter.product_artifact_observation_pr10_1 import ProductArtifactObservation
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


def test_runtime_materializes_artifact_point_evidence_without_download_authority() -> None:
    event = {
        "type": "product_artifact_observed",
        "observation_id": "pr10.1:artifact:file-123",
        "artifact_id": "file-123",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 1234,
        "download_available": True,
        "source_origin": "product_content_part",
    }

    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event(event)
            return _execution()

    forwarded: list[dict[str, Any]] = []
    result = Runtime().send_text_observed("create a report", on_event=forwarded.append)

    assert forwarded == [event]
    assert len(result.observations) == 1
    artifact = result.observations[0]
    assert isinstance(artifact, ProductArtifactObservation)
    assert artifact.artifact_id == "file-123"
    assert artifact.download_available is True
    assert "url" not in artifact.to_dict()
    assert "path" not in artifact.to_dict()
    assert result.dropped_observation_event_count == 0
    assert result.response.text == "canonical answer"
    assert result.observation == {"write": "completed"}


def test_runtime_drops_locator_bearing_artifact_without_invalidating_write() -> None:
    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event(
                {
                    "type": "product_artifact_observed",
                    "observation_id": "pr10.1:artifact:file-123",
                    "artifact_id": "file-123",
                    "filename": "report.pdf",
                    "download_available": True,
                    "source_origin": "product_message_metadata",
                    "download_url": "https://example.test/private-capability-url",
                }
            )
            return _execution()

    result = Runtime().send_text_observed("create a report")

    assert result.observations == ()
    assert result.dropped_observation_event_count == 1
    assert result.response.text == "canonical answer"
    assert result.observation == {"write": "completed"}
