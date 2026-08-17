from __future__ import annotations

import json
from types import SimpleNamespace

from chatgpt_web_adapter.browser_authority_retained_picker_forensics_pr8_8 import (
    RetainedPickerForensicsProvider,
    RetainedPickerForensicsRunner,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"
TAB_ID = 1949460340
LEASE_ID = "lease-retained-forensics"


class FakeHealth:
    def __init__(self, *, ready=True, canonical_status="completed", runtime_tab_id=TAB_ID):
        self.ready = ready
        self.canonical_status = canonical_status
        self.runtime_tab_id = runtime_tab_id

    def to_dict(self):
        return {
            "ready": self.ready,
            "canonical_status": self.canonical_status,
            "runtime_tab_id": self.runtime_tab_id,
        }


class FakeProvider:
    def __init__(self):
        self.runtime_tab_id = TAB_ID
        self.lease_id_present = True
        self.release_calls = []
        self.forensic = {
            "conversation_id": CONVERSATION,
            "expected_runtime_tab_id": TAB_ID,
            "runtime_tab_id": TAB_ID,
            "runtime_tab_id_after": TAB_ID,
            "runtime_tab_retained": True,
            "browser_authority_lease_id": LEASE_ID,
            "lease_id_present": True,
            "zero_product_writes": True,
            "conversation_write_count": 0,
            "tab_was_active": False,
            "tab_active_after": False,
            "tab_activated_during_probe": False,
            "foreground_activation_observed": False,
            "debugger_attached_before": False,
            "debugger_attached_after": False,
            "picker_surface_open": True,
            "instant_dom_candidate_count": 1,
            "instant_ax_candidate_count": 1,
            "recognized_modes": ["HIGH", "INSTANT"],
            "dom_topology": {
                "composer_ready": True,
                "picker_control": {"tag": "BUTTON", "mode": "HIGH"},
                "popup_surface_open": True,
                "popup_surfaces": [{"tag": "DIV", "role": "menu"}],
                "dom_candidates": [
                    {
                        "tag": "DIV",
                        "role": "menuitemradio",
                        "modes": ["INSTANT"],
                        "modeEvidence": "SUBTREE",
                    }
                ],
                "recognized_modes": ["HIGH", "INSTANT"],
                "instant_dom_candidate_count": 1,
                "scanned_visible_element_count": 120,
            },
            "accessibility_topology": {
                "candidate_count": 2,
                "instant_candidate_count": 1,
                "recognized_modes": ["HIGH", "INSTANT"],
                "candidates": [
                    {
                        "role": "menuitemradio",
                        "mode": "INSTANT",
                        "modeEvidence": "NAME",
                        "backendDOMNodeIdPresent": True,
                    }
                ],
            },
        }

    def retained_picker_forensics_support(self):
        return {
            "retained_picker_forensics_supported": True,
            "retained_picker_forensics_schema_version": 1,
            "retained_existing_tab_probe_supported": True,
            "dom_topology_supported": True,
            "accessibility_topology_supported": True,
            "conversation_write_guard_supported": True,
            "fenced_reconciliation_close_supported": True,
            "zero_product_writes": True,
        }

    def characterization_status(self):
        return SimpleNamespace(
            supported=True,
            runtime_tab_release_supported=True,
            runtime_tab_id=self.runtime_tab_id,
            lease_id_present=self.lease_id_present,
            to_dict=lambda: {
                "supported": True,
                "runtime_tab_release_supported": True,
                "runtime_tab_id": self.runtime_tab_id,
                "lease_id_present": self.lease_id_present,
            },
        )

    def retained_picker_surface_forensics(self, conversation, *, expected_runtime_tab_id, timeout=20.0):
        assert conversation == CONVERSATION
        assert expected_runtime_tab_id == TAB_ID
        return dict(self.forensic)

    def status(self):
        return SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=self.runtime_tab_id,
        )

    def release_runtime_tab(self, *, expected_runtime_tab_id, browser_authority_lease_id, timeout):
        self.release_calls.append((expected_runtime_tab_id, browser_authority_lease_id, timeout))
        assert expected_runtime_tab_id == TAB_ID
        assert browser_authority_lease_id == LEASE_ID
        self.runtime_tab_id = None
        self.lease_id_present = False
        return SimpleNamespace(
            released=True,
            already_absent=False,
            runtime_tab_id=TAB_ID,
            browser_authority_lease_id=LEASE_ID,
        )


class FakeRuntime:
    def __init__(self, provider):
        self.provider = provider
        self.health_calls = 0
        self.write_calls = []
        self.canonical_status = "completed"

    def health(self, conversation):
        self.health_calls += 1
        assert conversation == CONVERSATION
        return FakeHealth(
            ready=True,
            canonical_status=self.canonical_status,
            runtime_tab_id=self.provider.runtime_tab_id,
        )

    def send_text(self, *args, **kwargs):
        self.write_calls.append((args, kwargs))
        raise AssertionError("forensics must never send product writes")

    send_text_observed = send_text


def make_runner():
    provider = FakeProvider()
    runtime = FakeRuntime(provider)
    return RetainedPickerForensicsRunner(runtime, provider=provider), runtime, provider


def test_extension_forensics_layer_is_additive_and_contains_no_product_ui_mutation():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"

    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    worker = (root / "service_worker_retained_picker_forensics_pr8_8.js").read_text(encoding="utf-8")
    imports = [
        'importScripts("service_worker_phase_timing_pr8_8.js")',
        'importScripts("service_worker_instant_mode_pr8_8.js")',
        'importScripts("service_worker_instant_selection_repair_pr8_8.js")',
        'importScripts("service_worker_retained_picker_forensics_pr8_8.js")',
    ]
    assert all(token in observability for token in imports)
    assert [observability.index(token) for token in imports] == sorted(observability.index(token) for token in imports)
    for token in (
        "characterizeRetainedPickerForensicsSupport",
        "characterizeRetainedPickerSurfaceForensics",
        "Accessibility.getFullAXTree",
        "conversationWriteCount",
        "instantDomCandidateCount",
        "instantAxCandidateCount",
    ):
        assert token in worker
    for forbidden in (
        "Input.dispatchMouseEvent",
        "Input.insertText",
        "submitOfficialPageTurn(",
        "chrome.tabs.remove(",
    ):
        assert forbidden not in worker


def test_provider_parses_bounded_dom_and_ax_topology(monkeypatch):
    provider = RetainedPickerForensicsProvider()
    response = {
        "retainedPickerForensicsSupported": True,
        "retainedPickerForensicsSchemaVersion": 1,
        "conversationId": CONVERSATION,
        "expectedRuntimeTabId": TAB_ID,
        "runtimeTabId": TAB_ID,
        "runtimeTabIdAfter": TAB_ID,
        "runtimeTabRetained": True,
        "browserAuthorityLeaseId": LEASE_ID,
        "leaseIdPresent": True,
        "zeroProductWrites": True,
        "conversationWriteCount": 0,
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "debuggerAttachedBefore": False,
        "debuggerAttachedAfter": False,
        "pickerSurfaceOpen": True,
        "instantDomCandidateCount": 0,
        "instantAxCandidateCount": 1,
        "recognizedModes": ["HIGH", "INSTANT"],
        "domTopology": {
            "composerReady": True,
            "pickerControl": {"tag": "BUTTON", "mode": "HIGH"},
            "popupSurfaceOpen": True,
            "popupSurfaces": [],
            "domCandidates": [],
            "recognizedModes": ["HIGH"],
            "instantDomCandidateCount": 0,
            "scannedVisibleElementCount": 100,
        },
        "accessibilityTopology": {
            "candidateCount": 1,
            "instantCandidateCount": 1,
            "recognizedModes": ["INSTANT"],
            "candidates": [{"role": "menuitemradio", "mode": "INSTANT"}],
        },
    }
    monkeypatch.setattr(provider, "_characterization_rpc", lambda payload, *, timeout: response)
    record = provider.retained_picker_surface_forensics(
        CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
    )
    assert record["instant_dom_candidate_count"] == 0
    assert record["instant_ax_candidate_count"] == 1
    assert record["accessibility_topology"]["candidates"][0]["role"] == "menuitemradio"
    assert record["conversation_write_count"] == 0


def test_zero_write_forensics_leaves_retained_tab_untouched_by_default():
    runner, runtime, provider = make_runner()
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is True
    assert report["product_write_budget"] == 0
    assert report["write_attempts"] == report["write_completions"] == 0
    assert runtime.write_calls == []
    assert provider.runtime_tab_id == TAB_ID
    assert provider.release_calls == []
    assert report["summary"]["retained_tab_left_untouched"] is True
    assert report["topology_summary"]["instant_dom_candidate_count"] == 1
    assert report["topology_summary"]["instant_ax_candidate_count"] == 1


def test_explicit_fenced_reconciliation_close_is_zero_write_and_closes_exact_tab():
    runner, runtime, provider = make_runner()
    report = runner.run(
        conversation=CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
        reconcile_close_after_forensics=True,
    )
    assert report["ok"] is True
    assert runtime.write_calls == []
    assert report["write_attempts"] == report["write_completions"] == 0
    assert provider.release_calls == [(TAB_ID, LEASE_ID, 10.0)]
    assert provider.runtime_tab_id is None
    assert report["reconcile_close_performed"] is True
    assert report["summary"]["fenced_reconciliation_close_performed"] is True


def test_tab_mismatch_fails_before_forensics_and_without_close():
    runner, runtime, provider = make_runner()
    provider.runtime_tab_id = TAB_ID + 1
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is False
    assert report["failure_phase"] == "retained_runtime_preflight"
    assert runtime.write_calls == []
    assert provider.release_calls == []


def test_non_completed_canonical_state_fails_before_forensics_and_close():
    runner, runtime, provider = make_runner()
    runtime.canonical_status = "in_progress"
    report = runner.run(
        conversation=CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
        reconcile_close_after_forensics=True,
    )
    assert report["ok"] is False
    assert report["failure_phase"] == "retained_runtime_preflight"
    assert runtime.write_calls == []
    assert provider.release_calls == []


def test_unexpected_conversation_write_in_forensic_record_fails_and_does_not_close():
    runner, runtime, provider = make_runner()
    provider.forensic["conversation_write_count"] = 1
    provider.forensic["zero_product_writes"] = False
    report = runner.run(
        conversation=CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
        reconcile_close_after_forensics=True,
    )
    assert report["ok"] is False
    assert report["failure_phase"] == "retained_picker_surface_forensics"
    assert runtime.write_calls == []
    assert provider.release_calls == []
