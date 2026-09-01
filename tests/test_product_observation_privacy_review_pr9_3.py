from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from chatgpt_web_adapter.product_observations import ProductObservationCollector

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
        pytest.skip("Node.js is required for browser-extension privacy fixtures")

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


def test_browser_overlay_trims_private_content_type_before_source_scan() -> None:
    events = _observe_message(
        {
            "id": "private-thought-message",
            "content": {"content_type": " thoughts ", "parts": ["private"]},
            "metadata": {
                "content_references": [
                    {
                        "type": "webpage",
                        "start_idx": 0,
                        "end_idx": 7,
                        "items": [
                            {
                                "title": "Must not escape",
                                "url": "https://private.example/source",
                                "attribution": "Private",
                            }
                        ],
                    }
                ]
            },
        }
    )
    assert events == []


def test_browser_overlay_rejects_compound_oauth_credential_query_keys() -> None:
    for key in ("client_secret", "refresh_token", "id_token", "client_assertion", "code_verifier"):
        events = _observe_message(
            {
                "id": f"credential-{key}",
                "content": {
                    "content_type": "tether_quote",
                    "title": "Credential URL",
                    "url": f"https://example.test/source?{key}=PRIVATE",
                },
                "metadata": {},
            }
        )
        assert events == []


def test_python_collector_rejects_compound_oauth_credential_query_keys() -> None:
    collector = ProductObservationCollector()
    keys = ("client_secret", "refresh_token", "id_token", "client_assertion", "code_verifier")
    for index, key in enumerate(keys):
        assert collector.consume(
            {
                "type": "product_source_observed",
                "observation_id": f"source-observation:{index}",
                "source_id": f"source:{index}",
                "url": f"https://example.test/source?{key}=PRIVATE",
            }
        ) is None
    assert collector.observations == ()
    assert collector.dropped_event_count == len(keys)


def test_python_activity_privacy_check_already_trims_content_type() -> None:
    collector = ProductObservationCollector()
    assert collector.consume(
        {
            "type": "activity_text_snapshot",
            "activity_id": "thinking:trimmed-private",
            "activity_kind": "reasoning",
            "source_content_type": " thoughts ",
            "text": "private text",
        }
    ) is None
    assert collector.observations == ()
    assert collector.dropped_event_count == 1
