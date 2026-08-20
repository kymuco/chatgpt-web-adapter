from __future__ import annotations

from io import StringIO
from pathlib import Path

from chatgpt_web_adapter.revision_safe_streaming_pr8_9 import (
    ACTIVITY_COMPLETED,
    ACTIVITY_STARTED,
    ACTIVITY_TEXT_DELTA,
    ACTIVITY_TEXT_SNAPSHOT,
    RevisionSafeTextAccumulator,
)
from chatgpt_web_adapter.standalone_send import RevisionSafeTerminalRenderer


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
ACTIVITY_JS = EXTENSION / "service_worker_normalized_activity_stream_pr8_12.js"
PATCH_JS = EXTENSION / "service_worker_normalized_activity_patch_protocol_pr8_12.js"
OBSERVABILITY_JS = EXTENSION / "service_worker_observability.js"


def test_activity_events_pass_through_without_touching_answer_sequence() -> None:
    state = RevisionSafeTextAccumulator()
    event = {
        "type": ACTIVITY_STARTED,
        "sequence": 9,
        "activity_id": "web-1",
        "activity_kind": "web",
        "label": "Searching the web…",
    }
    assert state.apply(event) == event
    assert state.last_sequence == 0
    assert state.observation_count == 0
    assert state.text == ""

    answer = state.apply(
        {
            "type": "assistant_text_snapshot",
            "sequence": 1,
            "message_id": "assistant-1",
            "text": "Final",
        }
    )
    assert answer is not None
    assert state.last_sequence == 1
    assert state.observation_count == 1
    assert state.text == "Final"


def test_terminal_renderer_prints_activity_then_answer_without_mixing_planes() -> None:
    stream = StringIO()
    renderer = RevisionSafeTerminalRenderer(stream)

    events = [
        {
            "type": ACTIVITY_STARTED,
            "sequence": 1,
            "activity_id": "web-1",
            "activity_kind": "web",
            "label": "Searching the web…",
        },
        {
            "type": ACTIVITY_COMPLETED,
            "sequence": 2,
            "activity_id": "web-1",
            "activity_kind": "web",
            "label": "Web search complete",
        },
        {
            "type": ACTIVITY_STARTED,
            "sequence": 3,
            "activity_id": "reasoning-1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary",
        },
        {
            "type": ACTIVITY_TEXT_SNAPSHOT,
            "sequence": 4,
            "activity_id": "reasoning-1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary",
            "text": "I checked",
        },
        {
            "type": ACTIVITY_TEXT_DELTA,
            "sequence": 5,
            "activity_id": "reasoning-1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary",
            "delta": " sources.",
        },
        {
            "type": ACTIVITY_COMPLETED,
            "sequence": 6,
            "activity_id": "reasoning-1",
            "activity_kind": "reasoning",
            "label": "Reasoning summary complete",
        },
        {
            "type": "assistant_text_snapshot",
            "sequence": 1,
            "message_id": "assistant-1",
            "text": "Final answer",
        },
    ]
    for event in events:
        renderer.on_event(event)
    renderer.finish("Final answer")

    assert stream.getvalue() == (
        "[web] Searching the web…\n"
        "[web] Web search complete\n"
        "[reasoning] Reasoning summary\n"
        "[reasoning] I checked sources.\n"
        "Final answer\n"
    )


def test_extension_exports_only_normalized_activity_surface() -> None:
    source = ACTIVITY_JS.read_text(encoding="utf-8")
    for event_type in (
        '"activity_started"',
        '"activity_text_snapshot"',
        '"activity_text_delta"',
        '"activity_text_revision"',
        '"activity_completed"',
    ):
        assert event_type in source

    assert 'contentType === "reasoning_recap"' in source
    assert 'contentType === "tether_browsing_display"' in source
    assert 'contentType === "thoughts"' in source
    assert '"Thinking…"' in source
    assert "Classification-only. This string is never put into a turn_event." in source
    assert "Raw tool arguments/results" in source

    for forbidden in (
        "Network.getResponseBody",
        "Fetch.enable",
        "Fetch.fulfillRequest",
        "requestHeaders",
        "requestPostData",
        "document.cookie",
    ):
        assert forbidden not in source


def test_private_thoughts_text_is_never_selected_as_visible_activity_text() -> None:
    source = ACTIVITY_JS.read_text(encoding="utf-8")
    start = source.index("function _pr812VisibleActivityText")
    end = source.index("\nfunction _pr812RawTextForClassification", start)
    visible_text_reducer = source[start:end]
    assert 'contentType === "reasoning_recap"' in visible_text_reducer
    assert 'contentType === "tether_browsing_display"' in visible_text_reducer
    assert 'contentType === "thoughts"' not in visible_text_reducer


def test_compact_patch_protocol_keeps_stable_message_and_null_path_text() -> None:
    source = PATCH_JS.read_text(encoding="utf-8")
    assert "pr812-patch-" in source
    assert "path === null" in source
    assert 'typeof value === "string"' in source
    assert "state.currentPatchMessage" in source
    assert "_pr812InspectMessage(context, state, state.currentPatchMessage)" in source


def test_activity_stream_load_order_preserves_pr8111_then_patch_compatibility() -> None:
    source = OBSERVABILITY_JS.read_text(encoding="utf-8")
    repair = 'importScripts("service_worker_early_product_completion_repair_pr8_11_1.js");'
    activity = 'importScripts("service_worker_normalized_activity_stream_pr8_12.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'
    assert repair in source and activity in source and patch in source
    assert source.index(repair) < source.index(activity) < source.index(patch)
