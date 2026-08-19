from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_phase_cost_attribution_pr8_8 import (
    BrowserAuthorityPhaseCostAttributionRunner,
    BrowserAuthorityPhaseTimingProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus
from chatgpt_web_adapter.exceptions import RequestError


class Clock:
    def __init__(self):
        self.now = 100.0
    def monotonic(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds
    def advance(self, seconds):
        self.now += seconds


class Provider:
    def __init__(self, *, supported=True, missing=False, inconsistent=False):
        self.current_tab_id = None
        self.supported = supported
        self.missing = missing
        self.inconsistent = inconsistent
        self.records = {}

    def phase_timing_support(self):
        if not self.supported:
            raise RequestError("TEXT_REQUIRED", request_stage="browser_native_turn")
        return {"phase_timing_supported": True, "phase_timing_schema_version": 1}

    def characterization_status(self):
        return SimpleNamespace(
            supported=True,
            runtime_tab_release_supported=True,
            runtime_tab_id=self.current_tab_id,
            to_dict=lambda: {
                "supported": True,
                "runtime_tab_release_supported": True,
                "runtime_tab_id": self.current_tab_id,
            },
        )

    def phase_timing_for_lease(self, lease_id):
        if self.missing:
            raise RequestError("PR8_8_PHASE_TIMING_RECORD_NOT_AVAILABLE", request_stage="browser_authority_phase_timing")
        value = dict(self.records[lease_id])
        if self.inconsistent:
            value["page_turn_elapsed_ms"] += 100
        return value

    def status(self):
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=self.current_tab_id,
        )


@dataclass
class Health:
    ready: bool = True
    canonical_status: str = "completed"
    def to_dict(self):
        return {"ready": self.ready, "canonical_status": self.canonical_status}


def execution(*, tab_id, created, generation, policy, ttl_ms, disposal, released_at_ms):
    observation = SimpleNamespace(
        write_event_observed=True,
        runtime_tab_id=tab_id,
        runtime_tab_preexisting=not created,
        runtime_tab_created_for_turn=created,
        foreground_activation_observed=False,
        browser_authority_lease_id=f"lease-{generation}",
        browser_authority_generation=generation,
        browser_authority_policy=policy,
        browser_authority_ttl_ms=ttl_ms,
        browser_authority_issued_at_ms=released_at_ms - 1000,
        browser_authority_released_at_ms=released_at_ms,
        browser_authority_disposal_due_at_ms=(
            released_at_ms + ttl_ms if ttl_ms is not None else None
        ),
        browser_authority_release_proven=True,
        browser_authority_disposal_action=disposal,
        turn_lifecycle_id=f"turn-{generation}",
        turn_lifecycle_state_at_write="WRITE_COMPLETED",
    )
    provenance = SimpleNamespace(
        completion=SimpleNamespace(completed=True, canonical_completion_proven=True),
        conversation_mode=SimpleNamespace(
            requested_conversation_mode="NORMAL",
            observed_conversation_mode="NORMAL",
            observed_mode_proven=True,
        ),
        transport="browser-owned",
        product_semantics="ordinary-chatgpt",
    )
    return SimpleNamespace(
        response=SimpleNamespace(
            conversation=SimpleNamespace(conversation_id="conversation-fixed")
        ),
        observation=observation,
        provenance=provenance,
    )


class Runtime:
    def __init__(self, provider, clock):
        self.provider = provider
        self.clock = clock
        self.calls = []
        self.generation = 0
        self.next_tab = 200

    def health(self, conversation):
        return Health()

    def governance(self):
        return {
            "transport": "browser-owned",
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "browser_authority_effective_runtime_default_policy": "PERSISTENT",
            "browser_authority_effective_runtime_default_ttl_ms": None,
            "browser_authority_policy_contract_scope": "RESOURCE_LIFECYCLE_ONLY",
            "temporary_mode_production_enabled": False,
        }

    def send_text_observed(self, text, **kwargs):
        self.calls.append((text, kwargs))
        self.generation += 1
        position = (self.generation - 1) % 3
        created = self.provider.current_tab_id is None
        if created:
            self.next_tab += 1
            self.provider.current_tab_id = self.next_tab
        tab_id = self.provider.current_tab_id

        policy = "TURN_SCOPED" if position == 2 else "PERSISTENT"
        ttl_ms = 0 if position == 2 else None
        disposal = "CLOSE" if position == 2 else "KEEP"

        self.clock.advance(20)
        released = round((self.clock.now - 5) * 1000)
        lease_id = f"lease-{self.generation}"
        first = 800 if position == 0 else 5
        total = 805 if position == 0 else 10
        self.provider.records[lease_id] = {
            "phase_timing_lease_id": lease_id,
            "phase_timing_schema_version": 1,
            "runtime_tab_resolve_call_count": 2,
            "runtime_tab_first_resolve_ms": first,
            "runtime_tab_resolve_total_ms": total,
            "runtime_tab_resolve_max_ms": first,
            "page_turn_elapsed_ms": 10000,
            "tab_ready_to_write_delegated_ms": 1000,
            "write_delegated_to_network_complete_ms": 8500,
            "network_complete_to_native_complete_ms": 500,
            "write_delegated_to_native_complete_ms": 9000,
            "native_turn_elapsed_ms": total + 10100,
            "runtime_reloaded": False,
            "runtime_reload_ms": None,
            "other_native_overhead_ms": 100,
        }
        result = execution(
            tab_id=tab_id,
            created=created,
            generation=self.generation,
            policy=policy,
            ttl_ms=ttl_ms,
            disposal=disposal,
            released_at_ms=released,
        )
        if position == 2:
            self.provider.current_tab_id = None
        return result


def runner(runtime, provider, clock):
    return BrowserAuthorityPhaseCostAttributionRunner(
        runtime,
        provider=provider,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def test_extension_timing_layer_is_below_existing_observability_chain():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"

    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    phase = (root / "service_worker_phase_timing_pr8_8.js").read_text(encoding="utf-8")
    assert 'importScripts("service_worker_phase_timing_pr8_8.js")' in observability
    assert 'importScripts("service_worker_recovery.js")' in phase
    for token in (
        "characterizeBrowserAuthorityPhaseTimingSupport",
        "characterizeBrowserAuthorityPhaseTiming",
        "expectedBrowserAuthorityLeaseId",
        "phaseTimingLeaseId",
        "runtimeTabFirstResolveMs",
        "writeDelegatedToNetworkCompleteMs",
        "networkCompleteToNativeCompleteMs",
        "otherNativeOverheadMs",
    ):
        assert token in phase
    stored_record = phase.split("const record = {", 1)[1].split("};", 1)[0]
    assert "message.text" not in stored_record


def test_provider_parses_read_only_support_and_lease_fenced_timing(monkeypatch):
    provider = BrowserAuthorityPhaseTimingProvider()
    responses = [
        {"phaseTimingSupported": True, "phaseTimingSchemaVersion": 1},
        {
            "phaseTimingSupported": True,
            "phaseTimingSchemaVersion": 1,
            "phaseTimingLeaseId": "lease-1",
            "runtimeTabResolveCallCount": 2,
            "runtimeTabFirstResolveMs": 900,
            "runtimeTabResolveTotalMs": 905,
            "runtimeTabResolveMaxMs": 900,
            "pageTurnElapsedMs": 10000,
            "tabReadyToWriteDelegatedMs": 1000,
            "writeDelegatedToNetworkCompleteMs": 8500,
            "networkCompleteToNativeCompleteMs": 500,
            "writeDelegatedToNativeCompleteMs": 9000,
            "nativeTurnElapsedMs": 11005,
            "runtimeReloaded": False,
            "runtimeReloadMs": None,
            "otherNativeOverheadMs": 100,
        },
    ]
    calls = []
    def rpc(payload, *, timeout):
        calls.append(payload)
        return responses.pop(0)
    monkeypatch.setattr(provider, "_characterization_rpc", rpc)

    assert provider.phase_timing_support()["phase_timing_supported"] is True
    timing = provider.phase_timing_for_lease("lease-1")
    assert timing["runtime_tab_first_resolve_ms"] == 900
    assert calls[0]["characterizeBrowserAuthorityPhaseTimingSupport"] is True
    assert calls[1]["expectedBrowserAuthorityLeaseId"] == "lease-1"


def test_success_isolates_cold_acquisition_and_keeps_policy_decision_evidence_only():
    provider, clock = Provider(), Clock()
    runtime = Runtime(provider, clock)
    report = runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        conversation="conversation-fixed",
        replications=2,
        disposal_wait_timeout=1,
        closed_stability_ms=200,
    )
    assert report["ok"] is True
    assert report["write_attempts"] == report["write_completions"] == 6
    dist = report["phase_cost_characterization"]["distributions"]["runtime_tab_first_resolve_ms"]
    assert dist["cold"]["median"] == 800
    assert dist["warm"]["median"] == 5
    assert dist["cold_minus_warm"]["median"] == 795
    gov = report["policy_decision_governance"]
    assert gov["library_default_policy"] == "PERSISTENT"
    assert gov["library_default_change_performed"] is False
    assert gov["phase_cost_threshold_applied"] is False
    assert gov["decision_requires_human_review"] is True
    assert report["final_runtime_status"]["runtime_tab_id"] is None
    assert report["summary"]["automatic_write_retry_attempted"] is False
    for offset in (0, 3):
        assert "browser_authority_policy" not in runtime.calls[offset][1]
        assert "browser_authority_policy" not in runtime.calls[offset + 1][1]
        assert runtime.calls[offset + 2][1]["browser_authority_policy"] == "TURN_SCOPED"
        assert runtime.calls[offset + 2][1]["browser_authority_ttl_ms"] == 0


def test_unreloaded_extension_stops_before_first_write():
    provider, clock = Provider(supported=False), Clock()
    runtime = Runtime(provider, clock)
    report = runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        conversation="conversation-fixed",
        replications=2,
    )
    assert report["ok"] is False
    assert report["failure_phase"] == "phase_cost_preflight"
    assert report["write_attempts"] == report["write_completions"] == 0
    assert runtime.calls == []


def test_missing_timing_after_completed_write_stops_without_retry():
    provider, clock = Provider(missing=True), Clock()
    runtime = Runtime(provider, clock)
    report = runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        conversation="conversation-fixed",
        replications=2,
    )
    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_cold_persistent_send"
    assert report["write_attempts"] == report["write_completions"] == 1
    assert len(runtime.calls) == 1
    assert report["failure"]["automatic_retry_attempted"] is False


def test_inconsistent_phase_accounting_stops_without_retry():
    provider, clock = Provider(inconsistent=True), Clock()
    runtime = Runtime(provider, clock)
    report = runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        conversation="conversation-fixed",
        replications=2,
    )
    assert report["ok"] is False
    assert report["write_attempts"] == report["write_completions"] == 1
    assert "PAGE_PHASES_DO_NOT_SUM" in report["failure"]["message"]
    assert report["failure"]["automatic_retry_attempted"] is False


def test_fixed_conversation_and_live_write_ack_are_required_before_dispatch():
    provider, clock = Provider(), Clock()
    runtime = Runtime(provider, clock)
    with pytest.raises(ValueError, match="real product writes"):
        runner(runtime, provider, clock).run(
            acknowledge_live_writes=False,
            conversation="conversation-fixed",
            replications=2,
        )
    with pytest.raises(ValueError, match="conversation is required"):
        runner(runtime, provider, clock).run(
            acknowledge_live_writes=True,
            conversation="",
            replications=2,
        )
    assert runtime.calls == []
