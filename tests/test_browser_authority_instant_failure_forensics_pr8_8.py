from __future__ import annotations

import json
from types import SimpleNamespace

from chatgpt_web_adapter.browser_authority_instant_failure_forensics_pr8_8 import (
    FreshInstantFailureForensicsRunner,
    InstantFailureForensicsProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"
TAB_ID = 1949460999
LEASE_ID = "lease-fresh-failure"


class FakeHealth:
    ready = True
    canonical_status = "completed"
    runtime_tab_id = None

    def to_dict(self):
        return {
            "ready": self.ready,
            "canonical_status": self.canonical_status,
            "runtime_tab_id": self.runtime_tab_id,
        }


class FakeLease:
    lease_id = LEASE_ID
    generation = 7
    state = SimpleNamespace(value="RELEASE_UNKNOWN")
    authority_release_proven = False


class FakeWriteError(Exception):
    failure_kind = "BROWSER_OWNED_WRITE_OUTCOME_UNKNOWN"
    write_may_have_been_submitted = True
    reconciliation_required = True
    automatic_retry_allowed = False
    manual_retry_safe_after_repair = False
    request_stage = "browser_owned_write"
    browser_authority_lease = FakeLease()


class FakeProvider:
    def __init__(self):
        self.after_write = False

    def instant_failure_forensics_support(self):
        return {
            "supported": True,
            "schema": 1,
            "failure_record_persistence_supported": True,
            "pre_input_failure_boundary_supported": True,
            "raw_error_redaction_supported": True,
            "lease_id_exported": False,
            "zero_product_writes": True,
            "automatic_retry": False,
        }

    def instant_selection_support(self):
        return {
            "instant_selection_repair_supported": True,
            "product_ui_selection_supported": True,
        }

    def characterization_status(self):
        return SimpleNamespace(
            runtime_tab_id=TAB_ID if self.after_write else None,
            lease_id_present=self.after_write,
            to_dict=lambda: {
                "runtime_tab_id": TAB_ID if self.after_write else None,
                "lease_id_present": self.after_write,
            },
        )

    def selected_mode_preflight(self, conversation, *, timeout):
        assert conversation == CONVERSATION
        return {
            "conversation_id": CONVERSATION,
            "selected_mode": "HIGH",
            "selected_mode_proven": True,
            "conversation_write_count": 0,
            "probe_tab_closed": True,
            "runtime_tab_id_after": None,
            "debugger_attached_after": False,
            "foreground_activation_observed": False,
        }

    def instant_failure_forensics_record(self, lease_id, *, timeout):
        assert lease_id == LEASE_ID
        return {
            "failure_captured": True,
            "failure_code": "OPTION_NOT_FOUND",
            "failure_reason": "instant_option_missing",
            "pre_input_failure_boundary_proven": True,
            "prompt_insertion_reached": False,
            "submit_reached": False,
            "raw_error_exported": False,
            "lease_id_exported": False,
            "zero_product_writes": True,
            "automatic_retry": False,
            "selection": {
                "conversation_write_count_during_selection": 0,
                "unexpected_conversation_write_before_selection_complete": False,
                "selected_mode_before_selection": "HIGH",
                "picker_candidate_count": 1,
                "instant_option_candidate_count": 0,
            },
        }



class FakeRuntime:
    def __init__(self, provider):
        self.provider = provider
        self.write_calls = 0

    def health(self, conversation):
        assert conversation == CONVERSATION
        health = FakeHealth()
        health.runtime_tab_id = TAB_ID if self.provider.after_write else None
        return health

    def send_text_observed(self, text, **kwargs):
        self.write_calls += 1
        assert kwargs["conversation"] == CONVERSATION
        self.provider.after_write = True
        raise FakeWriteError(
            "PR8_8_INSTANT_SELECTION_OPTION_NOT_FOUND:instant_option_missing"
        )


def make_runner():
    provider = FakeProvider()
    runtime = FakeRuntime(provider)
    return (
        FreshInstantFailureForensicsRunner(runtime, provider=provider),
        runtime,
        provider,
    )


def test_extension_failure_layer_is_additive_and_does_not_add_product_mutation():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    observability = (root / "service_worker_observability.js").read_text(
        encoding="utf-8"
    )
    worker = (root / "service_worker_instant_failure_forensics_pr8_8.js").read_text(
        encoding="utf-8"
    )
    selection = 'importScripts("service_worker_instant_selection_repair_pr8_8.js")'
    new = 'importScripts("service_worker_instant_failure_forensics_pr8_8.js")'
    assert selection in observability and new in observability
    assert observability.index(selection) < observability.index(new)
    for token in (
        "failureRecordPersistenceSupported",
        "preInputFailureBoundaryProven",
        "promptInsertionReached: false",
        "submitReached: false",
        "rawErrorExported: false",
        "leaseIdExported: false",
        "characterizeInstantFailureForensicsRecord",
    ):
        assert token in worker
    for forbidden in (
        "Input.insertText",
        "submitOfficialPageTurn(",
        "chrome.tabs.create(",
        "chrome.tabs.update(",
        "chrome.tabs.remove(",
        "chrome.debugger.attach(",
        "document.cookie",
        "Network.getResponseBody",
    ):
        assert forbidden not in worker


def test_provider_parses_redacted_failure_record(monkeypatch):
    provider = InstantFailureForensicsProvider()

    def rpc(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == LEASE_ID
        return {
            "failureCaptured": True,
            "failureCode": "OPTION_NOT_FOUND",
            "failureReason": "instant_option_missing",
            "preInputFailureBoundaryProven": True,
            "promptInsertionReached": False,
            "submitReached": False,
            "rawErrorExported": False,
            "leaseIdExported": False,
            "zeroProductWrites": True,
            "automaticRetry": False,
            "selection": {
                "selectedModeBeforeSelection": "HIGH",
                "selectedModeBeforeSelectionProven": True,
                "pickerCandidateCount": 1,
                "instantOptionCandidateCount": 0,
                "conversationWriteCountDuringSelection": 0,
                "unexpectedConversationWriteBeforeSelectionComplete": False,
            },
        }

    monkeypatch.setattr(provider, "_characterization_rpc", rpc)
    record = provider.instant_failure_forensics_record(LEASE_ID)
    assert record["failure_code"] == "OPTION_NOT_FOUND"
    assert record["pre_input_failure_boundary_proven"] is True
    assert record["lease_id_exported"] is False
    assert record["selection"]["selected_mode_before_selection"] == "HIGH"
    assert record["selection"]["conversation_write_count_during_selection"] == 0


def test_single_failure_is_characterized_without_post_failure_retained_probe():
    runner, runtime, provider = make_runner()
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation=CONVERSATION,
        timeout=1,
        forensics_timeout=1,
    )
    assert report["ok"] is True
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 0
    assert runtime.write_calls == 1
    assert report["target_failure_reproduced"] is True
    assert report["summary"]["pre_input_failure_boundary_proven"] is True
    assert report["summary"]["prompt_insertion_reached"] is False
    assert report["summary"]["submit_reached"] is False
    assert "route_forensics" not in report
    assert "picker_surface_forensics" not in report
    assert report["evidence_preservation"]["retained_tab_left_untouched"] is True
    assert report["automatic_write_retry"] is False


def test_conversation_write_during_selection_fails_closed_without_retry():
    runner, runtime, provider = make_runner()
    original = provider.instant_failure_forensics_record

    def contradicted(*args, **kwargs):
        record = original(*args, **kwargs)
        record["selection"]["conversation_write_count_during_selection"] = 1
        record["selection"][
            "unexpected_conversation_write_before_selection_complete"
        ] = True
        return record

    provider.instant_failure_forensics_record = contradicted
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation=CONVERSATION,
        timeout=1,
        forensics_timeout=1,
    )
    assert report["ok"] is False
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 0
    assert runtime.write_calls == 1
    assert "CONVERSATION_WRITE_DURING_SELECTION" in report["failure"]["message"]
    assert report["failure"]["automatic_retry_attempted"] is False


def test_dirty_initial_authority_stops_before_live_write():
    runner, runtime, provider = make_runner()
    provider.after_write = True
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation=CONVERSATION,
        timeout=1,
        forensics_timeout=1,
    )
    assert report["ok"] is False
    assert report["write_attempts"] == 0
    assert runtime.write_calls == 0
    assert "INITIAL_RUNTIME_TAB_PRESENT" in report["failure"]["message"]
