from __future__ import annotations

from chatgpt_web_adapter.product_observations import (
    ProductActivityObservation,
    ProductCitationObservation,
    ProductObservationCollector,
    ProductObservationKind,
    ProductObservationPhase,
    ProductRequiredActionObservation,
    ProductSourceObservation,
)


def test_pr812_tool_sides_are_point_observations_without_fabricated_lifecycle() -> None:
    collector = ProductObservationCollector()

    started = collector.consume(
        {
            "type": "activity_started",
            "activity_id": "tool-web:assistant-message-1",
            "activity_kind": "web",
            "operation": "search_query",
            "tool_name": "web.run",
            "label": "Searching the web…",
            "sequence": 1,
            "observed_at_ms": 25,
            "arguments": {"q": "must not escape"},
            "result": {"raw": "must not escape"},
        }
    )
    completed = collector.consume(
        {
            "type": "activity_completed",
            "activity_id": "tool-result-web:tool-message-9",
            "activity_kind": "web",
            "operation": "search_query",
            "tool_name": "web.run",
            "label": "Web search complete",
            "sequence": 2,
            "observed_at_ms": 80,
        }
    )

    assert isinstance(started, ProductActivityObservation)
    assert started.kind is ProductObservationKind.SEARCH
    assert started.phase is ProductObservationPhase.OBSERVED
    assert started.operation == "search_query"
    assert started.to_dict() == {
        "observation_id": "tool-web:assistant-message-1",
        "kind": "SEARCH",
        "phase": "OBSERVED",
        "activity_kind": "web",
        "operation": "search_query",
        "tool_name": "web.run",
        "label": "Searching the web…",
        "text": None,
        "source_content_type": None,
        "sequence": 1,
        "observed_at_ms": 25,
    }

    assert isinstance(completed, ProductActivityObservation)
    assert completed.kind is ProductObservationKind.SEARCH
    assert completed.phase is ProductObservationPhase.OBSERVED
    assert completed.observation_id != started.observation_id
    assert completed.text is None


def test_non_tool_activity_can_keep_real_same_id_lifecycle() -> None:
    collector = ProductObservationCollector()
    started = collector.consume(
        {
            "type": "activity_started",
            "activity_id": "reasoning:1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary",
        }
    )
    completed = collector.consume(
        {
            "type": "activity_completed",
            "activity_id": "reasoning:1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary complete",
        }
    )
    assert isinstance(started, ProductActivityObservation)
    assert started.phase is ProductObservationPhase.STARTED
    assert isinstance(completed, ProductActivityObservation)
    assert completed.phase is ProductObservationPhase.COMPLETED


def test_tool_activity_is_separate_from_search_and_not_fake_lifecycle() -> None:
    collector = ProductObservationCollector()
    observation = collector.consume(
        {
            "type": "activity_started",
            "activity_id": "tool-code:calculator-request",
            "activity_kind": "tool",
            "operation": "calculator",
            "tool_name": "calculator",
            "label": "Calculating…",
        }
    )

    assert isinstance(observation, ProductActivityObservation)
    assert observation.kind is ProductObservationKind.TOOL
    assert observation.phase is ProductObservationPhase.OBSERVED


def test_activity_text_deltas_and_revisions_materialize_current_visible_text() -> None:
    collector = ProductObservationCollector()

    first = collector.consume(
        {
            "type": "activity_text_snapshot",
            "activity_id": "browse:1",
            "activity_kind": "browsing_display",
            "label": "Browsing update",
            "text": "Reading",
        }
    )
    second = collector.consume(
        {
            "type": "activity_text_delta",
            "activity_id": "browse:1",
            "activity_kind": "browsing_display",
            "label": "Browsing update",
            "delta": " sources",
        }
    )
    third = collector.consume(
        {
            "type": "activity_text_revision",
            "activity_id": "browse:1",
            "activity_kind": "browsing_display",
            "label": "Browsing update",
            "text": "Reading primary sources",
        }
    )

    assert isinstance(first, ProductActivityObservation)
    assert first.text == "Reading"
    assert isinstance(second, ProductActivityObservation)
    assert second.text == "Reading sources"
    assert isinstance(third, ProductActivityObservation)
    assert third.text == "Reading primary sources"
    assert all(item.kind is ProductObservationKind.SEARCH for item in collector.observations)


def test_private_thought_text_event_is_dropped_even_if_upstream_regresses() -> None:
    collector = ProductObservationCollector()
    leaked = collector.consume(
        {
            "type": "activity_text_snapshot",
            "activity_id": "thinking:private",
            "activity_kind": "reasoning",
            "source_content_type": "thoughts",
            "label": "Thinking…",
            "text": "private chain text must never escape",
        }
    )
    assert leaked is None
    assert collector.observations == ()
    assert collector.dropped_event_count == 1

    completed = collector.consume(
        {
            "type": "activity_completed",
            "activity_id": "thinking:private",
            "activity_kind": "reasoning",
            "source_content_type": "thoughts",
            "label": "Thinking complete",
        }
    )
    assert isinstance(completed, ProductActivityObservation)
    assert completed.text is None


def test_source_and_citation_relationship_is_explicit_and_fail_closed() -> None:
    collector = ProductObservationCollector()

    orphan = collector.consume(
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:orphan",
            "citation_id": "citation:orphan",
            "source_id": "source:missing",
            "citation_index": 0,
        }
    )
    source = collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:1",
            "source_id": "source:1",
            "url": "https://example.test/article",
            "title": "Example Article",
            "domain": "example.test",
        }
    )
    citation = collector.consume(
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:1",
            "citation_id": "citation:1",
            "source_id": "source:1",
            "citation_index": 0,
            "display_text": "[1]",
        }
    )

    assert orphan is None
    assert collector.dropped_event_count == 1
    assert isinstance(source, ProductSourceObservation)
    assert source.kind is ProductObservationKind.SOURCE
    assert isinstance(citation, ProductCitationObservation)
    assert citation.kind is ProductObservationKind.CITATION
    assert citation.source_id == source.source_id


def test_conflicting_source_id_reuse_is_dropped_and_original_relation_remains_unambiguous() -> None:
    collector = ProductObservationCollector()
    first = collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:1",
            "source_id": "source:stable",
            "url": "https://one.example/article",
        }
    )
    conflict = collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:2",
            "source_id": "source:stable",
            "url": "https://two.example/different",
        }
    )
    citation = collector.consume(
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:1",
            "citation_id": "citation:1",
            "source_id": "source:stable",
        }
    )

    assert isinstance(first, ProductSourceObservation)
    assert conflict is None
    assert collector.dropped_event_count == 1
    assert isinstance(citation, ProductCitationObservation)
    assert [
        item.url for item in collector.observations if isinstance(item, ProductSourceObservation)
    ] == ["https://one.example/article"]


def test_same_source_id_and_url_can_repeat_without_becoming_ambiguous() -> None:
    collector = ProductObservationCollector()
    assert collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:1",
            "source_id": "source:stable",
            "url": "https://one.example/article",
        }
    ) is not None
    assert collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:2",
            "source_id": "source:stable",
            "url": "https://one.example/article",
            "title": "Updated visible title",
        }
    ) is not None
    assert collector.dropped_event_count == 0


def test_required_action_is_observation_not_execution_authority() -> None:
    collector = ProductObservationCollector()
    observation = collector.consume(
        {
            "type": "product_required_action_observed",
            "observation_id": "required:1",
            "action_type": "user_confirmation",
            "label": "Confirmation required",
        }
    )

    assert isinstance(observation, ProductRequiredActionObservation)
    assert observation.kind is ProductObservationKind.REQUIRED_ACTION
    assert observation.phase is ProductObservationPhase.OBSERVED
    assert observation.action_type == "user_confirmation"


def test_assistant_text_and_canonical_finality_are_outside_observation_authority() -> None:
    collector = ProductObservationCollector()

    assert (
        collector.consume(
            {
                "type": "assistant_text_snapshot",
                "message_id": "assistant:1",
                "sequence": 1,
                "text": "provisional",
            }
        )
        is None
    )
    assert (
        collector.consume(
            {
                "type": "canonical_text_finalized",
                "message_id": "assistant:1",
                "text": "canonical",
            }
        )
        is None
    )
    assert collector.observations == ()
    assert collector.dropped_event_count == 0


def test_malformed_structured_observations_drop_without_raising() -> None:
    collector = ProductObservationCollector()

    assert collector.consume({"type": "activity_started"}) is None
    assert (
        collector.consume(
            {
                "type": "product_source_observed",
                "observation_id": "source:bad",
                "source_id": "source:bad",
            }
        )
        is None
    )
    assert collector.consume({"type": "product_required_action_observed"}) is None

    assert collector.observations == ()
    assert collector.dropped_event_count == 3
