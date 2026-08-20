from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

import chatgpt_web_adapter.cli as cli
from chatgpt_web_adapter.revision_safe_streaming_pr8_9 import (
    ACTIVITY_STARTED,
    ACTIVITY_TEXT_SNAPSHOT,
)
from chatgpt_web_adapter.standalone_send import RevisionSafeTerminalRenderer


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_final_only_renders_only_explicit_final_channel() -> None:
    stream = StringIO()
    renderer = RevisionSafeTerminalRenderer(stream, final_answer_only=True)

    events = [
        {
            "type": "assistant_text_snapshot",
            "sequence": 1,
            "message_id": "commentary-1",
            "channel": "commentary",
            "text": "I’ll verify this first.",
        },
        {
            "type": ACTIVITY_STARTED,
            "sequence": 1,
            "activity_id": "web-1",
            "activity_kind": "web",
            "label": "Using the web…",
        },
        {
            "type": ACTIVITY_TEXT_SNAPSHOT,
            "sequence": 2,
            "activity_id": "reasoning-1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary",
            "text": "Checked several sources.",
        },
        {
            "type": "assistant_text_snapshot",
            "sequence": 2,
            "message_id": "final-1",
            "channel": "final",
            "text": "Final",
        },
        {
            "type": "assistant_text_delta",
            "sequence": 3,
            "message_id": "final-1",
            "channel": "final",
            "delta": " answer",
        },
    ]
    for event in events:
        renderer.on_event(event)
    renderer.finish("Final answer")

    assert stream.getvalue() == "Final answer\n"


def test_final_only_falls_back_to_new_message_after_activity_when_channel_absent() -> None:
    stream = StringIO()
    renderer = RevisionSafeTerminalRenderer(stream, final_answer_only=True)

    renderer.on_event(
        {
            "type": "assistant_text_snapshot",
            "sequence": 1,
            "message_id": "commentary-1",
            "text": "I’ll verify this first.",
        }
    )
    renderer.on_event(
        {
            "type": ACTIVITY_STARTED,
            "sequence": 1,
            "activity_id": "web-1",
            "activity_kind": "web",
            "label": "Using the web…",
        }
    )
    renderer.on_event(
        {
            "type": "assistant_text_snapshot",
            "sequence": 2,
            "message_id": "final-1",
            "text": "Final",
        }
    )
    renderer.on_event(
        {
            "type": "assistant_text_delta",
            "sequence": 3,
            "message_id": "final-1",
            "delta": " answer",
        }
    )
    renderer.finish("Final answer")

    assert stream.getvalue() == "Final answer\n"


def test_final_only_cli_flag_requires_stream() -> None:
    args = cli._build_parser().parse_args(["send", "hello", "--stream", "--final-only"])
    assert args.stream is True
    assert args.final_only is True

    args = cli._build_parser().parse_args(["send", "hello", "--final-only"])
    with pytest.raises(ValueError, match="--final-only requires --stream"):
        cli._run_send(args)


def test_answer_channel_overlay_is_loaded_and_delivery_is_bounded() -> None:
    observability = (EXTENSION / "service_worker_observability.js").read_text(encoding="utf-8")
    delivery = (
        EXTENSION / "service_worker_revision_safe_text_delivery_pr8_9.js"
    ).read_text(encoding="utf-8")
    overlay = (
        EXTENSION / "service_worker_answer_channel_pr8_12.js"
    ).read_text(encoding="utf-8")

    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    channel = 'importScripts("service_worker_answer_channel_pr8_12.js");'
    assert patch in observability and channel in observability
    assert observability.index(patch) < observability.index(channel)
    assert 'channel,' in delivery
    assert 'normalized === "final" || normalized === "commentary"' in overlay
    assert "metadata.output_channel" in overlay
    assert "metadata.message_channel" in overlay
