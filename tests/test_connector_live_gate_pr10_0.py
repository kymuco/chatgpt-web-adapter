from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LIVE_GATE = ROOT / "tools" / "pr10_0_connector_live_gate.py"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pr10_0_connector_live_gate", LIVE_GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_support() -> dict[str, Any]:
    return {
        "supported": True,
        "schema": 1,
        "explicit_connector_identity_required": True,
        "explicit_lifecycle_correlation_required": True,
        "generic_tool_activity_implies_connector": False,
        "raw_connector_payload_exported": False,
        "grants_approval_authority": False,
        "changes_canonical_finality": False,
        "changes_retry_authority": False,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "write_performed": False,
    }


def _valid_diagnostic() -> dict[str, Any]:
    return {
        "request_id_matches": True,
        "response_ok": True,
        "support_fields_present": True,
        "failure_reason": None,
    }


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


def test_live_gate_has_one_write_budget_no_auto_approval_and_explicit_ack() -> None:
    source = LIVE_GATE.read_text(encoding="utf-8")

    assert "PRODUCT_WRITE_BUDGET = 1" in source
    assert source.count("runtime.send_text_observed(") == 1
    assert 'parser.add_argument("--acknowledge-live-write", action="store_true")' in source
    assert 'parser.add_argument("--preflight-only", action="store_true")' in source
    assert 'parser.add_argument("--expected-head", required=True)' in source
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


def test_connector_support_probe_maps_only_safe_contract_fields() -> None:
    gate = _load_gate()

    class _Provider(gate.ProductConnectorLiveProvider):
        def __init__(self) -> None:
            pass

        def _rpc(self, payload, *, timeout, on_event=None):
            return {
                "request_id": payload["request_id"],
                "ok": True,
                "connectorObservationSupported": True,
                "connectorObservationSchemaVersion": 1,
                "explicitConnectorIdentityRequired": True,
                "explicitLifecycleCorrelationRequired": True,
                "genericToolActivityImpliesConnector": False,
                "rawConnectorPayloadExported": False,
                "connectorObservationGrantsApprovalAuthority": False,
                "connectorObservationChangesCanonicalFinality": False,
                "connectorObservationChangesRetryAuthority": False,
                "automaticWriteRetry": False,
                "fallbackTransport": None,
                "writePerformed": False,
                "authorization": "Bearer secret",
                "rawMetadata": {"private": "value"},
            }

    support, diagnostic = _Provider().connector_observation_support(timeout=1.0)

    assert support == _valid_support()
    assert diagnostic == _valid_diagnostic()
    gate._validate_support(support)
    rendered = repr((support, diagnostic))
    assert "Bearer secret" not in rendered
    assert "rawMetadata" not in rendered


def test_support_probe_reports_worker_error_without_exporting_error_text() -> None:
    gate = _load_gate()

    class _Provider(gate.ProductConnectorLiveProvider):
        def __init__(self) -> None:
            pass

        def _rpc(self, payload, *, timeout, on_event=None):
            return {
                "request_id": payload["request_id"],
                "ok": False,
                "error": "private worker detail must not be exported",
            }

    support, diagnostic = _Provider().connector_observation_support(timeout=1.0)

    assert support is None
    assert diagnostic == {
        "request_id_matches": True,
        "response_ok": False,
        "support_fields_present": False,
        "failure_reason": "WORKER_RETURNED_ERROR",
    }
    assert "private worker detail" not in repr(diagnostic)


def test_support_contract_rejects_any_authority_or_write_widening() -> None:
    gate = _load_gate()
    support = _valid_support()
    support["grants_approval_authority"] = True

    try:
        gate._validate_support(support)
    except RuntimeError as exc:
        assert str(exc) == "PR10_0_CONNECTOR_SUPPORT_CONTRACT_NOT_PROVEN"
    else:
        raise AssertionError("authority-widening support contract must fail closed")


def test_failed_support_probe_returns_before_runtime_assembly_or_write(monkeypatch) -> None:
    gate = _load_gate()
    assembled = False

    class _Provider:
        def connector_observation_support(self, *, timeout: float):
            return None, {
                "request_id_matches": True,
                "response_ok": False,
                "support_fields_present": False,
                "failure_reason": "WORKER_RETURNED_ERROR",
            }

    def _assemble(*args, **kwargs):
        nonlocal assembled
        assembled = True
        raise AssertionError("runtime must not be assembled when support is unproven")

    monkeypatch.setattr(gate, "_git_output", lambda *args: "head-1")
    monkeypatch.setattr(gate, "_tracked_clean", lambda: True)
    monkeypatch.setattr(gate, "ProductConnectorLiveProvider", _Provider)
    monkeypatch.setattr(gate, "assemble_product_runtime", _assemble)

    report = gate.run_gate(prompt="safe", expected_head="head-1", timeout=1.0)

    assert report["support_probe_attempted"] is True
    assert report["support_probe_proven"] is False
    assert report["write_attempted"] is False
    assert report["preflight_error"] == "CONNECTOR_OBSERVATION_SUPPORT_NOT_PROVEN"
    assert report["support_probe_diagnostic"]["failure_reason"] == "WORKER_RETURNED_ERROR"
    assert assembled is False


def test_preflight_only_proves_support_without_runtime_assembly_or_write(monkeypatch) -> None:
    gate = _load_gate()
    assembled = False

    class _Provider:
        def connector_observation_support(self, *, timeout: float):
            return _valid_support(), _valid_diagnostic()

    def _assemble(*args, **kwargs):
        nonlocal assembled
        assembled = True
        raise AssertionError("preflight-only must not assemble the product runtime")

    monkeypatch.setattr(gate, "_git_output", lambda *args: "head-1")
    monkeypatch.setattr(gate, "_tracked_clean", lambda: True)
    monkeypatch.setattr(gate, "ProductConnectorLiveProvider", _Provider)
    monkeypatch.setattr(gate, "assemble_product_runtime", _assemble)

    report = gate.run_gate(
        prompt="safe",
        expected_head="head-1",
        timeout=1.0,
        preflight_only=True,
    )

    assert report["ok"] is True
    assert report["product_write_budget"] == 0
    assert report["support_probe_proven"] is True
    assert report["write_attempted"] is False
    assert report["characterization"] == "SUPPORT_PREFLIGHT_ONLY_PROVEN"
    assert assembled is False


def test_live_gate_orders_support_probe_before_runtime_and_product_write() -> None:
    source = LIVE_GATE.read_text(encoding="utf-8")

    support_call = source.index("provider.connector_observation_support(")
    runtime_assembly = source.index("runtime = assemble_product_runtime(")
    product_write = source.index("execution = runtime.send_text_observed(")

    assert support_call < runtime_assembly < product_write
