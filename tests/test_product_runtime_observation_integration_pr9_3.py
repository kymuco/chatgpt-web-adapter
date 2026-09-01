from __future__ import annotations

from typing import Any

import pytest

from chatgpt_web_adapter import ChatGPTProductRuntime
from chatgpt_web_adapter.product_observations import (
    ProductObservationCollector,
    ProductObservationKind,
    ProductRequiredActionObservation,
)
from chatgpt_web_adapter.product_runtime_observation_gate import (
    gate_product_runtime_send_text_observed,
)
from chatgpt_web_adapter.product_transport import ProductRuntimeExecution
from chatgpt_web_adapter.types import ChatResponse


def _execution(*, observations=(), dropped: int = 0) -> ProductRuntimeExecution:
    return ProductRuntimeExecution(
        transport="browser-owned",
        response=ChatResponse(text="canonical answer"),
        observation={"write": "observation"},
        observations=observations,
        dropped_observation_event_count=dropped,
    )


def test_product_runtime_execution_observation_defaults_are_backward_compatible() -> None:
    execution = ProductRuntimeExecution(
        transport="browser-owned",
        response=ChatResponse(text="ok"),
        observation=None,
    )
    assert execution.observations == ()
    assert execution.dropped_observation_event_count == 0


def test_gate_collects_typed_events_and_overrides_transport_injected_observations() -> None:
    rogue = ProductRequiredActionObservation(
        observation_id="transport-injected",
        action_type="must-not-be-authority",
    )
    source_event = {
        "type": "product_source_observed",
        "observation_id": "source-observation:s1",
        "source_id": "s1",
        "url": "https://example.test/article#fragment",
        "title": "Example",
    }
    citation_event = {
        "type": "product_citation_observed",
        "observation_id": "citation-observation:c1",
        "citation_id": "c1",
        "source_id": "s1",
        "start_index": 2,
        "end_index": 7,
    }

    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert text == "hello"
            assert on_event is not None
            on_event(source_event)
            on_event(citation_event)
            on_event({"type": "assistant_text_snapshot", "text": "not observation authority"})
            return _execution(observations=(rogue,), dropped=99)

    caller_events: list[dict[str, Any]] = []
    result = Runtime().send_text_observed("hello", on_event=caller_events.append)

    assert caller_events[0] is source_event
    assert caller_events[1] is citation_event
    assert [item.kind for item in result.observations] == [
        ProductObservationKind.SOURCE,
        ProductObservationKind.CITATION,
    ]
    assert all(item.observation_id != "transport-injected" for item in result.observations)
    assert result.dropped_observation_event_count == 0
    assert result.observation == {"write": "observation"}
    assert result.response.text == "canonical answer"


def test_gate_exposes_policy_drops_without_turn_failure() -> None:
    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event(
                {
                    "type": "activity_text_snapshot",
                    "activity_id": "private:1",
                    "activity_kind": "reasoning",
                    "source_content_type": " THOUGHTS ",
                    "text": "private",
                }
            )
            on_event(
                {
                    "type": "product_source_observed",
                    "observation_id": "source:credential",
                    "source_id": "credential",
                    "url": "https://example.test/?client_secret=PRIVATE",
                }
            )
            return _execution()

    result = Runtime().send_text_observed("hello")
    assert result.observations == ()
    assert result.dropped_observation_event_count == 2
    assert result.response.text == "canonical answer"


def test_gate_contains_collector_exception_but_preserves_caller_callback(monkeypatch) -> None:
    def explode(self, event):
        raise RuntimeError("collector regression")

    monkeypatch.setattr(ProductObservationCollector, "consume", explode)

    event = {"type": "activity_started", "activity_id": "x"}

    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event(event)
            return _execution()

    caller_events: list[dict[str, Any]] = []
    result = Runtime().send_text_observed("hello", on_event=caller_events.append)
    assert caller_events == [event]
    assert result.observations == ()
    assert result.dropped_observation_event_count == 1


def test_gate_does_not_swallow_caller_callback_exception() -> None:
    class Runtime:
        @gate_product_runtime_send_text_observed
        def send_text_observed(self, text: str, *, on_event=None, **kwargs: Any):
            assert on_event is not None
            on_event({"type": "activity_started", "activity_id": "x"})
            return _execution()

    def fail_callback(event: dict[str, Any]) -> None:
        raise RuntimeError("caller callback failed")

    with pytest.raises(RuntimeError, match="caller callback failed"):
        Runtime().send_text_observed("hello", on_event=fail_callback)


def test_gate_is_idempotent_and_installed_on_primary_runtime() -> None:
    def raw(self, text: str, *, on_event=None):
        return _execution()

    once = gate_product_runtime_send_text_observed(raw)
    twice = gate_product_runtime_send_text_observed(once)
    assert twice is once
    assert getattr(
        ChatGPTProductRuntime.send_text_observed,
        "__pr93_product_observation_gate__",
        False,
    ) is True
