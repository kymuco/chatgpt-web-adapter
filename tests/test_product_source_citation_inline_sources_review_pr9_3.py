from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_JS = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_product_source_citations_pr9_3.js"
)


def _observe_message(message: dict[str, object]) -> list[dict[str, object]]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-extension source fixtures")

    harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const message = JSON.parse(process.argv[2]);
const events = [];
const sandbox = { URL, WeakMap, Map, Set, console, __events: events, __ctx: {}, __message: message };
const context = vm.createContext(sandbox);
vm.runInContext(`
var _pr812InspectMessage = function(context, state, message) {};
var _pr812Emit = function(context, event) { __events.push(event); };
`, context);
vm.runInContext(source, context);
vm.runInContext(`_pr812InspectMessage(__ctx, {}, __message);`, context);
process.stdout.write(JSON.stringify(events));
'''
    completed = subprocess.run(
        [node, "-e", harness, str(SOURCE_JS), json.dumps(message)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_inline_sources_container_emits_source_and_citation_relation() -> None:
    events = _observe_message(
        {
            "id": "assistant-inline-sources",
            "content": {"content_type": "text", "parts": ["answer"]},
            "metadata": {
                "content_references": [
                    {
                        "type": "grouped_webpages",
                        "start_idx": 3,
                        "end_idx": 11,
                        "sources": [
                            {
                                "title": "Inline source",
                                "url": "https://example.test/inline",
                                "attribution": "Example",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert [event["type"] for event in events] == [
        "product_source_observed",
        "product_citation_observed",
    ]
    source, citation = events
    assert source["url"] == "https://example.test/inline"
    assert citation["source_id"] == source["source_id"]
    assert citation["start_index"] == 3
    assert citation["end_index"] == 11
    assert citation["reference_type"] == "grouped_webpages"


def test_sources_footnote_sources_container_remains_source_only() -> None:
    events = _observe_message(
        {
            "id": "assistant-footnote-sources",
            "content": {"content_type": "text", "parts": ["answer"]},
            "metadata": {
                "content_references": [
                    {
                        "type": "sources_footnote",
                        "start_idx": 12,
                        "end_idx": 13,
                        "sources": [
                            {
                                "title": "Footnote source",
                                "url": "https://example.test/footnote",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert len(events) == 1
    assert events[0]["type"] == "product_source_observed"
    assert events[0]["url"] == "https://example.test/footnote"
