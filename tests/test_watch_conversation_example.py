from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "watch_conversation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("watch_conversation_example", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_live_fragments_reads_reasoning_from_raw_ws_event() -> None:
    module = _load_module()

    fragments = module._extract_live_fragments(
        {
            "type": "raw_ws_event",
            "parsed": {
                "v": [
                    {
                        "p": "/message/reasoning/summary",
                        "v": "Need to compare the two transport paths before replying.",
                    }
                ]
            },
        }
    )

    assert fragments == [
        {
            "kind": "reasoning",
            "key": "path:/message/reasoning/summary",
            "label": "reasoning",
            "text": "Need to compare the two transport paths before replying.",
        }
    ]


def test_extract_live_fragments_reads_tool_result_message() -> None:
    module = _load_module()

    fragments = module._extract_live_fragments(
        {
            "type": "raw_sse_event",
            "parsed": {
                "v": {
                    "message": {
                        "id": "tool-1",
                        "author": {"role": "tool", "name": "browser"},
                        "recipient": "browser",
                        "content": {"parts": ["Found 3 matching files."]},
                        "metadata": {},
                    }
                }
            },
        }
    )

    assert fragments == [
        {
            "kind": "tool_result",
            "key": "tool_result:tool-1",
            "label": "tool_result:browser",
            "text": "Found 3 matching files.",
        }
    ]
