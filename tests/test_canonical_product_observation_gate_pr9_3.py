from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.canonical_product_observation_gate_pr9_3 import (
    _gate_send_browser_native,
    _gate_wait_for_new_final_assistant,
    canonical_product_observation_events,
)


def _payload(*, message_id: str = "assistant-final") -> dict[str, object]:
    return {
        "conversation_id": "conv-1",
        "current_node": "node-final",
        "mapping": {
            "node-final": {
                "id": "node-final",
                "parent": None,
                "message": {
                    "id": message_id,
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "text",
                        "parts": ["answer"],
                    },
                    "metadata": {
                        "content_references": [
                            {
                                "type": "grouped_webpages",
                                "start_idx": 5,
                                "end_idx": 12,
                                "sources": [
                                    {
                                        "title": "Official source",
                                        "url": "https://docs.python.org/3/library/pathlib.html",
                                        "attribution": "Python docs",
                                    }
                                ],
                            },
                            {
                                "type": "sources_footnote",
                                "start_idx": 13,
                                "end_idx": 14,
                                "sources": [
                                    {
                                        "title": "Footnote source",
                                        "url": "https://example.test/footnote",
                                    }
                                ],
                            },
                        ]
                    },
                },
            }
        },
    }


def test_canonical_payload_emits_inline_source_citation_and_footnote_source_only() -> None:
    events = canonical_product_observation_events(
        _payload(),
        message_id="assistant-final",
    )

    event_types = [event["type"] for event in events]
    assert event_types == [
        "product_source_observed",
        "product_citation_observed",
        "product_source_observed",
    ]

    first_source, citation, footnote_source = events
    assert first_source["url"] == "https://docs.python.org/3/library/pathlib.html"
    assert citation["source_id"] == first_source["source_id"]
    assert citation["start_index"] == 5
    assert citation["end_index"] == 12
    assert citation["reference_type"] == "grouped_webpages"
    assert footnote_source["source_origin"] == (
        "canonical_content_references.sources_footnote"
    )


def test_canonical_payload_requires_exact_visible_non_thought_assistant_message() -> None:
    assert canonical_product_observation_events(
        _payload(),
        message_id="different-message",
    ) == ()

    payload = _payload()
    message = payload["mapping"]["node-final"]["message"]
    message["content"]["content_type"] = " THOUGHTS "
    assert canonical_product_observation_events(
        payload,
        message_id="assistant-final",
    ) == ()


def test_canonical_payload_drops_sensitive_source_url() -> None:
    payload = _payload()
    message = payload["mapping"]["node-final"]["message"]
    message["metadata"]["content_references"] = [
        {
            "type": "webpage",
            "start_idx": 1,
            "end_idx": 2,
            "url": "https://example.test/page?client_secret=PRIVATE#fragment",
            "title": "unsafe",
        }
    ]

    assert canonical_product_observation_events(
        payload,
        message_id="assistant-final",
    ) == ()


def test_canonical_payload_reuses_existing_readback_without_another_read() -> None:
    payload = _payload()
    final_message = SimpleNamespace(message_id="assistant-final")
    wait_calls = 0

    def fake_wait(*args, **kwargs):
        nonlocal wait_calls
        wait_calls += 1
        assert kwargs["include_readback"] is True
        return final_message, payload, 1

    gated_wait = _gate_wait_for_new_final_assistant(fake_wait)

    def fake_send(self, prompt, *args, **kwargs):
        return gated_wait(
            self,
            "conv-1",
            baseline_assistant_ids=set(),
            timeout=1.0,
            interval=0.1,
            include_readback=True,
        )

    events: list[dict[str, object]] = []
    result = _gate_send_browser_native(fake_send)(
        object(),
        "prompt",
        on_event=events.append,
    )

    assert result[0] is final_message
    assert wait_calls == 1
    assert [event["type"] for event in events] == [
        "product_source_observed",
        "product_citation_observed",
        "product_source_observed",
    ]


def test_canonical_fallback_deduplicates_source_and_citation_seen_in_stream() -> None:
    payload = _payload()
    final_message = SimpleNamespace(message_id="assistant-final")

    def fake_wait(*args, **kwargs):
        return final_message, payload, 1

    gated_wait = _gate_wait_for_new_final_assistant(fake_wait)

    def fake_send(self, prompt, *args, **kwargs):
        callback = kwargs["on_event"]
        callback(
            {
                "type": "product_source_observed",
                "observation_id": "stream-source-observation",
                "source_id": "stream-source-1",
                "url": "https://docs.python.org/3/library/pathlib.html",
            }
        )
        callback(
            {
                "type": "product_citation_observed",
                "observation_id": "stream-citation-observation",
                "citation_id": "stream-citation-1",
                "source_id": "stream-source-1",
                "start_index": 5,
                "end_index": 12,
                "reference_type": "grouped_webpages",
            }
        )
        return gated_wait(
            self,
            "conv-1",
            baseline_assistant_ids=set(),
            timeout=1.0,
            interval=0.1,
            include_readback=True,
        )

    events: list[dict[str, object]] = []
    _gate_send_browser_native(fake_send)(
        object(),
        "prompt",
        on_event=events.append,
    )

    source_events = [
        event for event in events
        if event["type"] == "product_source_observed"
    ]
    citation_events = [
        event for event in events
        if event["type"] == "product_citation_observed"
    ]

    assert len(source_events) == 2
    assert {event["url"] for event in source_events} == {
        "https://docs.python.org/3/library/pathlib.html",
        "https://example.test/footnote",
    }
    assert len(citation_events) == 1
    assert citation_events[0]["source_id"] == "stream-source-1"


def test_no_callback_does_not_enable_streaming_callback_path() -> None:
    seen_on_event = object()

    def fake_send(self, prompt, *args, **kwargs):
        nonlocal seen_on_event
        seen_on_event = kwargs.get("on_event")
        return "ok"

    assert _gate_send_browser_native(fake_send)(object(), "prompt") == "ok"
    assert seen_on_event is None
