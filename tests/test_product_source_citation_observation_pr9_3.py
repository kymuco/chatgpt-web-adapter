from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from chatgpt_web_adapter.product_observations import (
    ProductCitationObservation,
    ProductObservationCollector,
    ProductSourceObservation,
)

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SOURCE_JS = EXT / "service_worker_product_source_citations_pr9_3.js"
SCHEMA7_LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"


def _run_node_fixture(message_expressions: list[str]) -> list[dict[str, object]]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension behavior fixtures")

    harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const messages = JSON.parse(process.argv[2]);
const events = [];
const sandbox = { URL, WeakMap, Map, Set, console, __events: events, __ctx: {} };
const context = vm.createContext(sandbox);
vm.runInContext(`
var _pr812InspectMessage = function(context, state, message) {};
var _pr812Emit = function(context, event) { __events.push(event); };
`, context);
vm.runInContext(source, context);
for (const message of messages) {
  context.__message = message;
  vm.runInContext(`_pr812InspectMessage(__ctx, {}, __message);`, context);
}
process.stdout.write(JSON.stringify(events));
'''
    messages = [json.loads(expression) for expression in message_expressions]
    completed = subprocess.run(
        [node, "-e", harness, str(SOURCE_JS), json.dumps(messages)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_pr93_overlay_is_loaded_after_schema29_without_changing_manifest_entrypoint() -> None:
    source = SCHEMA7_LOADER.read_text(encoding="utf-8")
    schema29 = 'importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");'
    pr93 = 'importScripts("service_worker_product_source_citations_pr9_3.js");'
    assert schema29 in source
    assert pr93 in source
    assert source.index(schema29) < source.index(pr93)


def test_pr93_source_citation_overlay_exports_only_bounded_provenance_fields() -> None:
    source = SOURCE_JS.read_text(encoding="utf-8")
    for required in (
        '"product_source_observed"',
        '"product_citation_observed"',
        "content_references",
        "metadata?.citations",
        "metadata?._cite_metadata?.metadata_list",
        'content.content_type !== "tether_quote"',
        'content.content_type === "thoughts"',
        "PR93_SENSITIVE_QUERY_KEYS",
        'parsed.hash = ""',
        "endIndex < startIndex",
    ):
        assert required in source

    for forbidden in (
        "evidence_text",
        "Network.getResponseBody",
        "Fetch.enable",
        "requestHeaders",
        "requestPostData",
        "document.cookie",
        "chrome.cookies",
    ):
        assert forbidden not in source


def test_current_content_references_emit_sources_and_inline_relations_but_not_footnote_citations() -> None:
    events = _run_node_fixture(
        [
            json.dumps(
                {
                    "id": "assistant-1",
                    "content": {"content_type": "text", "parts": ["answer"]},
                    "metadata": {
                        "content_references": [
                            {
                                "type": "grouped_webpages",
                                "start_idx": 10,
                                "end_idx": 20,
                                "matched_text": "PRIVATE_MARKER",
                                "items": [
                                    {
                                        "title": "Alpha",
                                        "url": "https://example.com/a#private-fragment",
                                        "attribution": "Example",
                                        "supporting_websites": [
                                            {
                                                "title": "Support",
                                                "url": "https://support.example/x",
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "type": "sources_footnote",
                                "start_idx": 21,
                                "end_idx": 22,
                                "sources": [
                                    {"title": "Foot", "url": "https://foot.example/f"}
                                ],
                            },
                        ]
                    },
                }
            )
        ]
    )
    sources = [event for event in events if event["type"] == "product_source_observed"]
    citations = [event for event in events if event["type"] == "product_citation_observed"]

    assert [event["url"] for event in sources] == [
        "https://example.com/a",
        "https://support.example/x",
        "https://foot.example/f",
    ]
    assert len(citations) == 2
    assert {event["source_id"] for event in citations} == {
        sources[0]["source_id"],
        sources[1]["source_id"],
    }
    assert all(event["start_index"] == 10 for event in citations)
    assert all(event["end_index"] == 20 for event in citations)
    assert all(event["reference_type"] == "grouped_webpages" for event in citations)
    serialized = json.dumps(events)
    assert "PRIVATE_MARKER" not in serialized
    assert "private-fragment" not in serialized


def test_incomplete_stream_reference_is_source_only_until_complete_range_arrives_once() -> None:
    incomplete = json.dumps(
        {
            "id": "assistant-stream",
            "content": {"content_type": "text"},
            "metadata": {
                "content_references": [
                    {
                        "type": "webpage",
                        "items": [{"title": "One", "url": "https://one.example/a"}],
                    }
                ]
            },
        }
    )
    complete = json.dumps(
        {
            "id": "assistant-stream",
            "content": {"content_type": "text"},
            "metadata": {
                "content_references": [
                    {
                        "type": "webpage",
                        "start_idx": 4,
                        "end_idx": 9,
                        "items": [{"title": "One", "url": "https://one.example/a"}],
                    }
                ]
            },
        }
    )
    events = _run_node_fixture([incomplete, complete, complete])
    assert [event["type"] for event in events] == [
        "product_source_observed",
        "product_citation_observed",
    ]
    assert events[1]["start_index"] == 4
    assert events[1]["end_index"] == 9


def test_reversed_reference_range_never_enters_raw_turn_event_stream() -> None:
    events = _run_node_fixture(
        [
            json.dumps(
                {
                    "id": "assistant-bad-range",
                    "content": {"content_type": "text"},
                    "metadata": {
                        "content_references": [
                            {
                                "type": "webpage",
                                "start_idx": 9,
                                "end_idx": 2,
                                "items": [
                                    {"title": "One", "url": "https://one.example/a"}
                                ],
                            }
                        ]
                    },
                }
            )
        ]
    )
    assert [event["type"] for event in events] == ["product_source_observed"]


def test_legacy_citation_emits_relation_without_exporting_evidence_or_metadata_text() -> None:
    events = _run_node_fixture(
        [
            json.dumps(
                {
                    "id": "assistant-legacy",
                    "content": {"content_type": "text", "parts": ["answer"]},
                    "metadata": {
                        "citations": [
                            {
                                "start_ix": 30,
                                "end_ix": 35,
                                "citation_format_type": "tether_og",
                                "metadata": {
                                    "title": "Legacy",
                                    "url": "https://legacy.example/z",
                                    "text": "RAW_SOURCE_TEXT",
                                    "extra": {"evidence_text": "SECRET_EVIDENCE"},
                                },
                            }
                        ],
                        "_cite_metadata": {
                            "metadata_list": [
                                {
                                    "title": "Meta",
                                    "url": "https://meta.example/m",
                                    "text": "RAW_METADATA_TEXT",
                                }
                            ]
                        },
                    },
                }
            )
        ]
    )
    serialized = json.dumps(events)
    assert "SECRET_EVIDENCE" not in serialized
    assert "RAW_SOURCE_TEXT" not in serialized
    assert "RAW_METADATA_TEXT" not in serialized

    citations = [event for event in events if event["type"] == "product_citation_observed"]
    assert len(citations) == 1
    assert citations[0]["start_index"] == 30
    assert citations[0]["end_index"] == 35
    assert citations[0]["reference_type"] == "tether_og"


def test_tether_quote_is_source_evidence_only_and_credential_urls_are_not_exported() -> None:
    events = _run_node_fixture(
        [
            json.dumps(
                {
                    "id": "quote-1",
                    "content": {
                        "content_type": "tether_quote",
                        "title": "Quote",
                        "url": "https://quote.example/q#anchor",
                        "text": "RAW_QUOTE_TEXT",
                    },
                    "metadata": {},
                }
            ),
            json.dumps(
                {
                    "id": "hidden",
                    "content": {"content_type": "text"},
                    "metadata": {
                        "is_visually_hidden_from_conversation": True,
                        "content_references": [
                            {
                                "type": "webpage",
                                "start_idx": 1,
                                "end_idx": 2,
                                "items": [
                                    {"title": "Hidden", "url": "https://hidden.example/"}
                                ],
                            }
                        ],
                    },
                }
            ),
            json.dumps(
                {
                    "id": "credentials-userinfo",
                    "content": {
                        "content_type": "tether_quote",
                        "title": "Credential URL",
                        "url": "https://user:pass@example.com/private",
                    },
                    "metadata": {},
                }
            ),
            json.dumps(
                {
                    "id": "credentials-query",
                    "content": {
                        "content_type": "tether_quote",
                        "title": "Signed URL",
                        "url": "https://example.com/private?access_token=secret",
                    },
                    "metadata": {},
                }
            ),
            json.dumps(
                {
                    "id": "credentials-aws",
                    "content": {
                        "content_type": "tether_quote",
                        "title": "Signed AWS URL",
                        "url": "https://example.com/private?X-Amz-Signature=secret",
                    },
                    "metadata": {},
                }
            ),
        ]
    )
    assert len(events) == 1
    assert events[0]["type"] == "product_source_observed"
    assert events[0]["url"] == "https://quote.example/q"
    serialized = json.dumps(events)
    assert "RAW_QUOTE_TEXT" not in serialized
    assert "secret" not in serialized


def test_repeated_complete_stream_message_processing_deduplicates_source_and_citation_events() -> None:
    message = json.dumps(
        {
            "id": "assistant-repeat",
            "content": {"content_type": "text"},
            "metadata": {
                "content_references": [
                    {
                        "type": "webpage",
                        "start_idx": 1,
                        "end_idx": 4,
                        "items": [{"title": "One", "url": "https://one.example/a"}],
                    }
                ]
            },
        }
    )
    events = _run_node_fixture([message, message, message])
    assert [event["type"] for event in events] == [
        "product_source_observed",
        "product_citation_observed",
    ]


def test_collector_preserves_safe_source_and_citation_relationship_fields() -> None:
    collector = ProductObservationCollector()
    source = collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:s1",
            "source_id": "s1",
            "url": "https://example.com/a#fragment",
            "title": "Example",
            "domain": "example.com",
            "attribution": "Example News",
            "source_origin": "content_references",
            "sequence": 1,
        }
    )
    assert isinstance(source, ProductSourceObservation)
    assert source.url == "https://example.com/a"
    assert source.attribution == "Example News"
    assert source.source_origin == "content_references"

    citation = collector.consume(
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:c1",
            "citation_id": "c1",
            "source_id": "s1",
            "citation_index": 0,
            "start_index": 8,
            "end_index": 16,
            "reference_type": "webpage",
            "display_text": "Example News",
            "sequence": 2,
        }
    )
    assert isinstance(citation, ProductCitationObservation)
    assert citation.start_index == 8
    assert citation.end_index == 16
    assert citation.reference_type == "webpage"


def test_collector_drops_missing_or_malformed_citation_ranges_without_affecting_source_evidence() -> None:
    collector = ProductObservationCollector()
    assert collector.consume(
        {
            "type": "product_source_observed",
            "observation_id": "source-observation:s1",
            "source_id": "s1",
            "url": "https://example.com/a",
        }
    ) is not None

    for citation in (
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:missing",
            "citation_id": "missing",
            "source_id": "s1",
        },
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:partial",
            "citation_id": "partial",
            "source_id": "s1",
            "start_index": 1,
        },
        {
            "type": "product_citation_observed",
            "observation_id": "citation-observation:reversed",
            "citation_id": "reversed",
            "source_id": "s1",
            "start_index": 20,
            "end_index": 10,
        },
    ):
        assert collector.consume(citation) is None
    assert collector.dropped_event_count == 3
    assert len(collector.observations) == 1
