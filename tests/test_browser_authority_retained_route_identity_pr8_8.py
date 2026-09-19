from __future__ import annotations

import json
from types import SimpleNamespace

from chatgpt_web_adapter.browser_authority_retained_route_identity_pr8_8 import (
    RetainedRouteIdentityProvider,
    RetainedRouteIdentityRunner,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"
OTHER_CONVERSATION = "11111111-2222-3333-4444-555555555555"
TAB_ID = 1949460340
LEASE_ID = "lease-route-identity"


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


def route_record(*, kind="ROOT", observed=None, status="ROOT_ROUTE", match=False):
    route = {
        "route_kind": kind,
        "observed_conversation_id": observed,
        "expected_conversation_id": CONVERSATION,
        "conversation_matches_expected": match,
        "route_identity_status": status,
        "raw_url_exported": False,
        "query_exported": False,
        "fragment_exported": False,
    }
    return {
        "conversation_id": CONVERSATION,
        "expected_runtime_tab_id": TAB_ID,
        "runtime_tab_id": TAB_ID,
        "runtime_tab_id_after": TAB_ID,
        "runtime_tab_retained": True,
        "browser_authority_lease_id": LEASE_ID,
        "lease_id_present": True,
        "zero_product_writes": True,
        "route_identity": route,
        "route_identity_after": dict(route),
        "route_identity_stable": True,
        "route_mismatch_characterized": not match,
        "dom_ax_inspection_performed": False,
        "conversation_write_guard_observed": False,
        "conversation_write_count": None,
        "tab_was_active": False,
        "tab_active_after": False,
        "tab_activated_during_probe": False,
        "foreground_activation_observed": False,
        "debugger_attached_before": False,
        "debugger_attached_after": False,
    }


class FakeProvider:
    def __init__(self):
        self.runtime_tab_id = TAB_ID
        self.lease_id_present = True
        self.route = route_record()
        self.surface_calls = 0
        self.release_calls = []

    def retained_route_identity_support(self):
        return {
            "retained_route_identity_supported": True,
            "retained_route_identity_schema_version": 1,
            "retained_existing_tab_route_probe_supported": True,
            "conversation_mismatch_characterization_supported": True,
            "route_mismatch_dom_ax_suppression_supported": True,
            "raw_route_redaction_supported": True,
            "exact_match_surface_forensics_delegation_supported": True,
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

    def retained_route_identity_forensics(self, conversation, *, expected_runtime_tab_id, timeout=10.0):
        assert conversation == CONVERSATION
        assert expected_runtime_tab_id == TAB_ID
        return dict(self.route)

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

    def retained_picker_surface_forensics(self, conversation, *, expected_runtime_tab_id, timeout=20.0):
        self.surface_calls += 1
        assert conversation == CONVERSATION
        assert expected_runtime_tab_id == TAB_ID
        return {
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
                "picker_control": {"mode": "HIGH"},
                "popup_surface_open": True,
                "popup_surfaces": [{}],
                "dom_candidates": [{}],
                "recognized_modes": ["HIGH", "INSTANT"],
                "instant_dom_candidate_count": 1,
                "scanned_visible_element_count": 100,
            },
            "accessibility_topology": {
                "candidate_count": 1,
                "instant_candidate_count": 1,
                "recognized_modes": ["INSTANT"],
                "candidates": [{}],
            },
        }

    def status(self):
        return SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=self.runtime_tab_id,
        )

    def release_runtime_tab(self, *, expected_runtime_tab_id, browser_authority_lease_id, timeout):
        self.release_calls.append((expected_runtime_tab_id, browser_authority_lease_id, timeout))
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
        self.canonical_status = "completed"
        self.write_calls = []

    def health(self, conversation):
        assert conversation == CONVERSATION
        return FakeHealth(
            ready=True,
            canonical_status=self.canonical_status,
            runtime_tab_id=self.provider.runtime_tab_id,
        )

    def send_text(self, *args, **kwargs):
        self.write_calls.append((args, kwargs))
        raise AssertionError("route forensics must never send product writes")

    send_text_observed = send_text


def make_runner():
    provider = FakeProvider()
    runtime = FakeRuntime(provider)
    return RetainedRouteIdentityRunner(runtime, provider=provider), runtime, provider


def test_extension_route_layer_is_additive_and_read_only():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"

    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    route_worker = (root / "service_worker_retained_route_identity_pr8_8.js").read_text(encoding="utf-8")
    old_import = 'importScripts("service_worker_retained_picker_forensics_pr8_8.js")'
    new_import = 'importScripts("service_worker_retained_route_identity_pr8_8.js")'
    assert old_import in observability and new_import in observability
    assert observability.index(old_import) < observability.index(new_import)
    for token in (
        "characterizeRetainedRouteIdentitySupport",
        "characterizeRetainedRouteIdentity",
        "EXPECTED_CONVERSATION_MATCH",
        "OTHER_CONVERSATION",
        "ROOT_ROUTE",
        "OTHER_CHATGPT_ROUTE",
        "domAxInspectionPerformed: false",
        "conversationWriteCount: null",
        "rawUrlExported: false",
        "queryExported: false",
        "fragmentExported: false",
    ):
        assert token in route_worker
    for forbidden in (
        "chrome.debugger.attach",
        "Runtime.evaluate",
        "Accessibility.getFullAXTree",
        "Input.dispatchMouseEvent",
        "Input.insertText",
        "submitOfficialPageTurn(",
        "chrome.tabs.update(",
        "chrome.tabs.remove(",
    ):
        assert forbidden not in route_worker


def test_provider_parses_safe_route_identity(monkeypatch):
    provider = RetainedRouteIdentityProvider()
    response = {
        "retainedRouteIdentitySupported": True,
        "retainedRouteIdentitySchemaVersion": 1,
        "conversationId": CONVERSATION,
        "expectedRuntimeTabId": TAB_ID,
        "runtimeTabId": TAB_ID,
        "runtimeTabIdAfter": TAB_ID,
        "runtimeTabRetained": True,
        "browserAuthorityLeaseId": LEASE_ID,
        "leaseIdPresent": True,
        "zeroProductWrites": True,
        "routeIdentity": {
            "routeKind": "CONVERSATION",
            "observedConversationId": OTHER_CONVERSATION,
            "expectedConversationId": CONVERSATION,
            "conversationMatchesExpected": False,
            "routeIdentityStatus": "OTHER_CONVERSATION",
            "rawUrlExported": False,
            "queryExported": False,
            "fragmentExported": False,
        },
        "routeIdentityAfter": {
            "routeKind": "CONVERSATION",
            "observedConversationId": OTHER_CONVERSATION,
            "expectedConversationId": CONVERSATION,
            "conversationMatchesExpected": False,
            "routeIdentityStatus": "OTHER_CONVERSATION",
            "rawUrlExported": False,
            "queryExported": False,
            "fragmentExported": False,
        },
        "routeIdentityStable": True,
        "routeMismatchCharacterized": True,
        "domAxInspectionPerformed": False,
        "conversationWriteGuardObserved": False,
        "conversationWriteCount": None,
        "tabWasActive": False,
        "tabActiveAfter": False,
        "tabActivatedDuringProbe": False,
        "foregroundActivationObserved": False,
        "debuggerAttachedBefore": False,
        "debuggerAttachedAfter": False,
    }
    monkeypatch.setattr(provider, "_characterization_rpc", lambda payload, *, timeout: response)
    record = provider.retained_route_identity_forensics(
        CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
    )
    assert record["route_identity"]["route_kind"] == "CONVERSATION"
    assert record["route_identity"]["observed_conversation_id"] == OTHER_CONVERSATION
    assert record["route_identity"]["raw_url_exported"] is False
    assert record["conversation_write_count"] is None
    assert record["dom_ax_inspection_performed"] is False


def test_root_route_mismatch_is_success_and_suppresses_surface_forensics():
    runner, runtime, provider = make_runner()
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is True
    assert report["route_identity_summary"]["route_kind"] == "ROOT"
    assert report["route_identity_summary"]["route_identity_status"] == "ROOT_ROUTE"
    assert report["route_identity_summary"]["conversation_matches_expected"] is False
    assert report["surface_forensics_performed"] is False
    assert provider.surface_calls == 0
    assert provider.runtime_tab_id == TAB_ID
    assert provider.release_calls == []
    assert runtime.write_calls == []


def test_other_conversation_mismatch_preserves_only_safe_identity():
    runner, runtime, provider = make_runner()
    provider.route = route_record(
        kind="CONVERSATION",
        observed=OTHER_CONVERSATION,
        status="OTHER_CONVERSATION",
        match=False,
    )
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is True
    assert report["route_identity_summary"]["observed_conversation_id"] == OTHER_CONVERSATION
    assert report["route_identity_summary"]["raw_url_exported"] is False
    assert report["route_identity_summary"]["query_exported"] is False
    assert report["route_identity_summary"]["fragment_exported"] is False
    assert provider.surface_calls == 0
    assert runtime.write_calls == []


def test_route_mismatch_explicit_close_fails_closed_and_preserves_specimen():
    runner, runtime, provider = make_runner()
    report = runner.run(
        conversation=CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
        reconcile_close_after_forensics=True,
    )
    assert report["ok"] is False
    assert report["failure_phase"] == "route_mismatch_close_guard"
    assert report["failure"]["message"] == "PR8_8_ROUTE_MISMATCH_CLOSE_FORBIDDEN"
    assert provider.surface_calls == 0
    assert provider.release_calls == []
    assert provider.runtime_tab_id == TAB_ID
    assert runtime.write_calls == []


def test_exact_conversation_match_delegates_to_existing_surface_forensics():
    runner, runtime, provider = make_runner()
    provider.route = route_record(
        kind="CONVERSATION",
        observed=CONVERSATION,
        status="EXPECTED_CONVERSATION_MATCH",
        match=True,
    )
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is True
    assert report["route_identity_summary"]["conversation_matches_expected"] is True
    assert report["surface_forensics_performed"] is True
    assert report["surface_forensics"]["ok"] is True
    assert provider.surface_calls == 1
    assert provider.runtime_tab_id == TAB_ID
    assert runtime.write_calls == []


def test_exact_match_explicit_close_reuses_existing_fenced_surface_close():
    runner, runtime, provider = make_runner()
    provider.route = route_record(
        kind="CONVERSATION",
        observed=CONVERSATION,
        status="EXPECTED_CONVERSATION_MATCH",
        match=True,
    )
    report = runner.run(
        conversation=CONVERSATION,
        expected_runtime_tab_id=TAB_ID,
        reconcile_close_after_forensics=True,
    )
    assert report["ok"] is True
    assert provider.surface_calls == 1
    assert provider.release_calls == [(TAB_ID, LEASE_ID, 10.0)]
    assert provider.runtime_tab_id is None
    assert report["reconcile_close_performed"] is True
    assert runtime.write_calls == []


def test_non_completed_canonical_state_fails_before_route_probe():
    runner, runtime, provider = make_runner()
    runtime.canonical_status = "in_progress"
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is False
    assert report["failure_phase"] == "retained_runtime_preflight"
    assert provider.surface_calls == 0
    assert runtime.write_calls == []


def test_route_privacy_violation_is_rejected_and_does_not_delegate():
    runner, runtime, provider = make_runner()
    provider.route["route_identity"]["raw_url_exported"] = True
    report = runner.run(conversation=CONVERSATION, expected_runtime_tab_id=TAB_ID)
    assert report["ok"] is False
    assert report["failure_phase"] == "retained_route_identity_forensics"
    assert provider.surface_calls == 0
    assert runtime.write_calls == []
