from __future__ import annotations

import json

import pytest

from chatgpt_web_adapter.browser_authority_instant_latency_pr8_8 import (
    InstantModePhaseLatencyRunner,
)
from chatgpt_web_adapter.browser_authority_instant_selection_repair_pr8_8 import (
    InstantSelectionRepairLatencyRunner,
    InstantSelectionRepairProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


class Provider:
    def __init__(self):
        self.supported = True
        self.selection_record = {
            "instant_selection_lease_id": "lease-1",
            "instant_selection_schema_version": 1,
            "requested_model_mode": "INSTANT",
            "selected_mode_before_selection": "HIGH",
            "selected_mode_before_selection_proven": True,
            "selected_mode_before_selection_proof_kind": "nearest_composer_mode_control",
            "selected_mode_before_selection_candidate_count": 1,
            "selection_performed": True,
            "selection_elapsed_ms": 900,
            "selection_mutation_elapsed_ms": 800,
            "picker_mode_before_click": "HIGH",
            "picker_candidate_count": 1,
            "picker_nearest_distance_px": 10,
            "instant_option_candidate_count": 1,
            "selected_mode_after_selection": "INSTANT",
            "selected_mode_after_selection_proven": True,
            "selected_mode_after_selection_proof_kind": "nearest_composer_mode_control",
            "selection_complete": True,
            "conversation_write_boundary_observed": True,
            "unexpected_conversation_write_before_selection_complete": False,
            "conversation_write_count_during_selection": 0,
            "network_request_count_during_selection": 2,
            "chatgpt_request_count_during_selection": 1,
            "chatgpt_mutating_non_conversation_request_count": 0,
            "setting_like_mutation_observed": False,
            "request_classes": ["CHATGPT_READ", "OTHER_ORIGIN"],
            "model_selection_materialization_status": "NO_CHATGPT_MUTATION_OBSERVED",
        }

    def instant_selection_support(self):
        return {
            "instant_selection_repair_supported": self.supported,
            "instant_selection_schema_version": 1 if self.supported else None,
            "product_ui_selection_supported": self.supported,
            "pre_submit_network_classification_supported": self.supported,
            "conversation_write_boundary_supported": self.supported,
        }

    def instant_selection_for_lease(self, lease_id):
        assert lease_id == "lease-1"
        return dict(self.selection_record)


def make_runner(provider=None):
    provider = provider or Provider()
    return InstantSelectionRepairLatencyRunner(object(), provider=provider), provider


def base_turn():
    return {
        "phase": "cold",
        "observation": {"browser_authority_lease_id": "lease-1"},
        "instant_mode": {
            "selected_mode_before_write": "INSTANT",
            "selected_mode_before_write_proven": True,
        },
    }


def base_success_report():
    selection = Provider().selection_record
    def turn(phase, before, performed):
        record = dict(selection)
        record["selected_mode_before_selection"] = before
        record["selection_performed"] = performed
        if not performed:
            record["selection_elapsed_ms"] = 1
            record["selection_mutation_elapsed_ms"] = 0
            record["conversation_write_boundary_observed"] = False
            record["network_request_count_during_selection"] = 0
            record["chatgpt_request_count_during_selection"] = 0
            record["request_classes"] = []
            record["model_selection_materialization_status"] = "NO_SELECTION_REQUIRED"
        return {
            "phase": phase,
            "instant_selection": record,
            "observation": {"browser_authority_lease_id": "lease-1"},
        }
    cycles = []
    for index in range(3):
        cycles.append({
            "cycle": index + 1,
            "cold_turn": turn("cold", "HIGH", True),
            "warm_turn": turn("warm", "INSTANT", False),
            "close_turn": turn("close", "INSTANT", False),
            "close_disposal": {"confirmed": True},
            "closed_window": {"confirmed": True},
        })
    return {
        "ok": True,
        "probe_context": "instant_mode_phase_level_latency_no_reasoning_baseline",
        "selected_mode_preflight": {
            "conversation_id": "conversation",
            "selected_mode": "HIGH",
            "selected_mode_proven": True,
            "conversation_write_count": 0,
            "probe_tab_closed": True,
            "runtime_tab_id_after": None,
            "foreground_activation_observed": False,
            "debugger_attached_after": False,
        },
        "cycles": cycles,
        "summary": {
            "exact_conversation_instant_preflight_proven": True,
            "automatic_write_retry_attempted": False,
        },
        "cross_mode_governance": {
            "library_default_change_performed": False,
            "hde_assembly_policy_change_performed": False,
        },
    }


def test_extension_selection_layer_preserves_manifest_and_import_order():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )

    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    phase_import = 'importScripts("service_worker_phase_timing_pr8_8.js")'
    instant_import = 'importScripts("service_worker_instant_mode_pr8_8.js")'
    repair_import = 'importScripts("service_worker_instant_selection_repair_pr8_8.js")'
    assert phase_import in observability
    assert instant_import in observability
    assert repair_import in observability
    assert (
        observability.index(phase_import)
        < observability.index(instant_import)
        < observability.index(repair_import)
    )


def test_selection_worker_mutates_only_picker_before_prompt_and_tracks_network_boundary():
    root = browser_native_extension_dir()
    text = (root / "service_worker_instant_selection_repair_pr8_8.js").read_text(
        encoding="utf-8"
    )
    for token in (
        "characterizeInstantSelectionRepairSupport",
        "characterizeInstantSelectionRecord",
        "selectedModeBeforeSelection",
        "selectedModeAfterSelection",
        "conversationWriteBoundaryObserved",
        "settingLikeMutationObserved",
        "modelSelectionMaterializationStatus",
        "CHATGPT_SETTING_LIKE_MUTATION",
        "NO_CHATGPT_MUTATION_OBSERVED",
    ):
        assert token in text
    assert "Input.insertText" not in text
    assert "submitOfficialPageTurn" not in text
    assert 'chrome.debugger.sendCommand(debuggee, "Input.dispatchMouseEvent"' in text
    assert 'await sendCommand(debuggee, "Input.dispatchMouseEvent"' not in text
    assert "raw request/response payloads" in text


def test_provider_parses_lease_fenced_selection_record(monkeypatch):
    provider = InstantSelectionRepairProvider()

    def rpc(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == "lease-1"
        return {
            "instantSelectionRepairSupported": True,
            "instantSelectionSchemaVersion": 1,
            "instantSelectionLeaseId": "lease-1",
            "requestedModelMode": "INSTANT",
            "selectedModeBeforeSelection": "HIGH",
            "selectedModeBeforeSelectionProven": True,
            "selectedModeBeforeSelectionProofKind": "nearest_composer_mode_control",
            "selectedModeBeforeSelectionCandidateCount": 1,
            "selectionPerformed": True,
            "selectionElapsedMs": 900,
            "selectionMutationElapsedMs": 800,
            "pickerModeBeforeClick": "HIGH",
            "pickerCandidateCount": 1,
            "pickerNearestDistancePx": 10,
            "instantOptionCandidateCount": 1,
            "selectedModeAfterSelection": "INSTANT",
            "selectedModeAfterSelectionProven": True,
            "selectedModeAfterSelectionProofKind": "nearest_composer_mode_control",
            "selectionComplete": True,
            "conversationWriteBoundaryObserved": True,
            "unexpectedConversationWriteBeforeSelectionComplete": False,
            "conversationWriteCountDuringSelection": 0,
            "networkRequestCountDuringSelection": 2,
            "chatgptRequestCountDuringSelection": 1,
            "chatgptMutatingNonConversationRequestCount": 0,
            "settingLikeMutationObserved": False,
            "requestClasses": ["CHATGPT_READ", "OTHER_ORIGIN"],
            "modelSelectionMaterializationStatus": "NO_CHATGPT_MUTATION_OBSERVED",
        }

    monkeypatch.setattr(provider, "_characterization_rpc", rpc)
    record = provider.instant_selection_for_lease("lease-1")
    assert record["selected_mode_before_selection"] == "HIGH"
    assert record["selected_mode_after_selection"] == "INSTANT"
    assert record["selection_performed"] is True
    assert record["conversation_write_count_during_selection"] == 0
    assert record["model_selection_materialization_status"] == (
        "NO_CHATGPT_MUTATION_OBSERVED"
    )


def test_fresh_tab_high_is_valid_preflight_evidence_not_failure():
    record = {
        "conversation_id": "conversation",
        "selected_mode": "HIGH",
        "selected_mode_proven": True,
        "conversation_write_count": 0,
        "probe_tab_closed": True,
        "runtime_tab_id_after": None,
        "debugger_attached_after": False,
        "foreground_activation_observed": False,
    }
    InstantSelectionRepairLatencyRunner._validate_preflight_mode(
        record, "conversation"
    )


def test_preflight_still_fails_closed_when_mode_is_not_proven():
    record = {
        "conversation_id": "conversation",
        "selected_mode": "HIGH",
        "selected_mode_proven": False,
        "conversation_write_count": 0,
        "probe_tab_closed": True,
        "runtime_tab_id_after": None,
        "debugger_attached_after": False,
        "foreground_activation_observed": False,
    }
    with pytest.raises(RuntimeError, match="MODE_NOT_PROVEN"):
        InstantSelectionRepairLatencyRunner._validate_preflight_mode(
            record, "conversation"
        )


def test_completed_turn_requires_instant_materialized_without_selection_write(monkeypatch):
    runner, provider = make_runner()

    def parent_turn(self, *args, **kwargs):
        return "conversation", base_turn()

    monkeypatch.setattr(InstantModePhaseLatencyRunner, "_turn", parent_turn)
    _, record = runner._turn(
        report={},
        cycle=1,
        phase="cold",
        conversation="conversation",
        timeout=1,
        poll_interval=0.1,
    )
    assert record["instant_selection"]["selected_mode_before_selection"] == "HIGH"
    assert record["instant_selection"]["selected_mode_after_selection"] == "INSTANT"
    assert record["instant_selection"]["conversation_write_count_during_selection"] == 0


def test_selection_conversation_write_contradiction_fails_after_completed_turn(monkeypatch):
    runner, provider = make_runner()
    provider.selection_record["unexpected_conversation_write_before_selection_complete"] = True
    provider.selection_record["conversation_write_count_during_selection"] = 1

    def parent_turn(self, *args, **kwargs):
        return "conversation", base_turn()

    monkeypatch.setattr(InstantModePhaseLatencyRunner, "_turn", parent_turn)
    with pytest.raises(RuntimeError, match="CONVERSATION_WRITE_OCCURRED_DURING_SELECTION"):
        runner._turn(
            report={},
            cycle=1,
            phase="cold",
            conversation="conversation",
            timeout=1,
            poll_interval=0.1,
        )


def test_new_support_failure_stops_before_parent_runner_and_zero_writes(monkeypatch):
    runner, provider = make_runner()
    provider.supported = False
    parent_called = False

    def parent_run(self, **kwargs):
        nonlocal parent_called
        parent_called = True
        return {"ok": True}

    monkeypatch.setattr(InstantModePhaseLatencyRunner, "run", parent_run)
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation="conversation",
    )
    assert report["ok"] is False
    assert report["write_attempts"] == 0
    assert report["write_completions"] == 0
    assert parent_called is False
    assert report["failure"]["automatic_retry_attempted"] is False


def test_success_relabels_high_fresh_preflight_and_summarizes_selection(monkeypatch):
    runner, _ = make_runner()

    def parent_run(self, **kwargs):
        return base_success_report()

    monkeypatch.setattr(InstantModePhaseLatencyRunner, "run", parent_run)
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation="conversation",
    )
    assert report["ok"] is True
    assert report["probe_context"] == (
        "instant_fresh_tab_selection_materialization_phase_latency"
    )
    assert report["summary"]["exact_conversation_instant_preflight_proven"] is False
    assert report["summary"]["fresh_tab_mode_preflight_proven"] is True
    assert report["summary"]["fresh_tab_mode_preflight_selected_mode"] == "HIGH"
    assert report["summary"]["cold_selection_performed_count"] == 3
    assert report["summary"]["warm_selection_performed_count"] == 0
    assert report["summary"]["conversation_writes_during_model_selection"] == 0
    assert report["summary"]["fresh_tab_picker_state_not_assumed_from_conversation"] is True
    selection = report["instant_selection_materialization"]
    assert selection["cold_fresh_tab_initial_mode_counts"] == {"HIGH": 3}
    assert selection["setting_like_mutation_observed_count"] == 0
    assert report["cross_mode_governance"]["library_default_change_performed"] is False
    assert report["cross_mode_governance"]["hde_assembly_policy_change_performed"] is False
