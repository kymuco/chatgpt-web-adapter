from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
LIVE_GATE = ROOT / "tools" / "pr10_0_connector_live_gate.py"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pr10_0_connector_live_gate", LIVE_GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_gate_safe_event_summary_drops_payload_and_text() -> None:
    gate = _load_gate()
    summary = gate._safe_event(
        {
            "type": "product_connector_observed",
            "sequence": 7,
            "connector_id": "connector_googlecalendar",
            "connector_activity_id": "connector-message:1",
            "operation": "search_events",
            "arguments": {"query": "private"},
            "result": {"private": "value"},
            "authorization": "Bearer secret",
            "cookies": "secret",
            "text": "private text",
            "delta": "private delta",
            "url": "https://example.test/?token=secret",
        }
    )

    assert summary == {
        "type": "product_connector_observed",
        "sequence": 7,
        "operation": "search_events",
        "connector_activity_id": "connector-message:1",
        "connector_id": "connector_googlecalendar",
    }


def test_live_gate_detects_private_thought_text_without_printing_it() -> None:
    gate = _load_gate()
    events = [
        {
            "type": "activity_text_snapshot",
            "source_content_type": "thoughts",
            "text": "must not leave the worker",
        }
    ]

    assert gate._private_thought_text_exported(events) is True
    assert gate._safe_event(events[0]) == {
        "type": "activity_text_snapshot",
        "source_content_type": "thoughts",
    }


def test_live_gate_has_one_write_budget_and_no_auto_approval_path() -> None:
    source = LIVE_GATE.read_text(encoding="utf-8")

    assert "PRODUCT_WRITE_BUDGET = 1" in source
    assert source.count("runtime.send_text_observed(") == 1
    assert "send_and_auto_approve" not in source
    assert "approve_pending_action" not in source
    assert "wait_and_approve" not in source
    assert "for attempt" not in source
    assert "while" not in source


def test_live_gate_default_prompt_is_read_only_and_redacts_non_marker_answer() -> None:
    gate = _load_gate()

    assert "read-only" in gate.DEFAULT_PROMPT
    assert "Do not create, edit, delete, send, upload, or modify anything" in gate.DEFAULT_PROMPT
    assert gate._SAFE_RESPONSE_MARKERS == {
        "CONNECTED_APP_READ_ONLY_DONE",
        "NO_CONNECTED_APP_AVAILABLE",
    }
