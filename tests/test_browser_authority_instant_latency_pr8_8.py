from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_instant_latency_pr8_8 import (
    InstantModeLatencyProvider,
    InstantModePhaseLatencyRunner,
)
from chatgpt_web_adapter.browser_authority_phase_cost_attribution_pr8_8 import (
    BrowserAuthorityPhaseTimingProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_instant_observability_layer_preserves_existing_extension_entrypoint_and_never_selects_model():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"

    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    instant = (root / "service_worker_instant_mode_pr8_8.js").read_text(encoding="utf-8")
    phase_import = 'importScripts("service_worker_phase_timing_pr8_8.js")'
    instant_import = 'importScripts("service_worker_instant_mode_pr8_8.js")'
    assert phase_import in observability
    assert instant_import in observability
    assert observability.index(phase_import) < observability.index(instant_import)
    for token in (
        "characterizeInstantModeSupport",
        "characterizeInstantSelectedMode",
        "characterizeInstantModeRecord",
        "requiredModelMode",
        "selectedModeBeforeWrite",
        "networkRouteStatus",
        "reasoningRouteObserved",
        "networkNoReasoningRouteProven",
    ):
        assert token in instant
    assert "Input.insertText" not in instant
    assert "Input.dispatchMouseEvent" not in instant
    assert ".click(" not in instant
    assert "raw SSE" in instant
    assert "request bodies, raw SSE" in instant


def test_provider_injects_instant_requirement_only_into_leased_product_turns(monkeypatch):
    provider = InstantModeLatencyProvider()
    calls = []

    def base_rpc(self, payload, *, timeout):
        calls.append(dict(payload))
        return {"ok": True}

    monkeypatch.setattr(BrowserAuthorityPhaseTimingProvider, "_rpc", base_rpc)
    provider._rpc(
        {
            "type": "turn",
            "text": "Reply exactly",
            "browserAuthorityLeaseId": "lease-1",
        },
        timeout=1.0,
    )
    provider._rpc({"type": "ping"}, timeout=1.0)

    assert calls[0]["requiredModelMode"] == "INSTANT"
    assert calls[0]["requireNoReasoningRoute"] is True
    assert "requiredModelMode" not in calls[1]
    assert "requireNoReasoningRoute" not in calls[1]


def test_provider_parses_lease_fenced_model_route_record(monkeypatch):
    provider = InstantModeLatencyProvider()

    def characterization(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == "lease-7"
        return {
            "instantModeSupported": True,
            "instantModeSchemaVersion": 1,
            "instantModeLeaseId": "lease-7",
            "requestedModelMode": "INSTANT",
            "requireNoReasoningRoute": True,
            "selectedModeBeforeWrite": "INSTANT",
            "selectedModeBeforeWriteProven": True,
            "selectedModeCandidateCount": 1,
            "selectedModeNearestDistancePx": 12,
            "selectedModeProofKind": "nearest_composer_mode_control",
            "conversationRequestObserved": True,
            "requestEvidence": {
                "modelIdentifiers": ["gpt-instant"],
                "modelModes": ["INSTANT"],
                "reasoningStates": [],
                "modelHintKeys": ["model"],
                "reasoningHintKeys": [],
            },
            "responseEvidence": {
                "modelIdentifiers": ["gpt-instant"],
                "modelModes": ["INSTANT"],
                "reasoningStates": ["OFF"],
                "modelHintKeys": ["model_slug"],
                "reasoningHintKeys": ["reasoning_effort"],
            },
            "networkRouteStatus": "INSTANT_MODEL_ROUTE_OBSERVED",
            "instantModelRouteObserved": True,
            "reasoningRouteObserved": False,
            "reasoningOffObserved": True,
            "networkNoReasoningRouteProven": True,
        }

    monkeypatch.setattr(provider, "_characterization_rpc", characterization)
    record = provider.instant_mode_for_lease("lease-7")
    assert record["selected_mode_before_write"] == "INSTANT"
    assert record["request_evidence"]["model_modes"] == ["INSTANT"]
    assert record["response_evidence"]["reasoning_states"] == ["OFF"]
    assert record["network_no_reasoning_route_proven"] is True



CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeSupport:
    def __init__(self, runtime_tab_id=None) -> None:
        self.supported = True
        self.resource_sampling_supported = True
        self.runtime_tab_release_supported = True
        self.runtime_tab_id = runtime_tab_id
        self.lease_id_present = False

    def to_dict(self):
        return {
            "supported": self.supported,
            "resource_sampling_supported": self.resource_sampling_supported,
            "runtime_tab_release_supported": self.runtime_tab_release_supported,
            "runtime_tab_id": self.runtime_tab_id,
            "lease_id_present": self.lease_id_present,
        }


class FakeProvider:
    def __init__(self) -> None:
        self.runtime_tab_id = None
        self.instant_supported = True
        self.phase_supported = True
        self.preflight_mode = "INSTANT"
        self.preflight_proven = True
        self.preflight_closed = True
        self.preflight_foreground = False
        self.reasoning_lease = None
        self.mode_change_lease = None
        self.network_proven = True
        self.status_calls = 0

    def instant_mode_support(self):
        return {
            "instant_mode_supported": self.instant_supported,
            "instant_mode_schema_version": 1 if self.instant_supported else None,
            "selected_mode_probe_supported": self.instant_supported,
            "request_route_observation_supported": self.instant_supported,
            "response_route_observation_supported": self.instant_supported,
        }

    def phase_timing_support(self):
        return {
            "phase_timing_supported": self.phase_supported,
            "phase_timing_schema_version": 1 if self.phase_supported else None,
        }

    def characterization_status(self):
        return FakeSupport(self.runtime_tab_id)

    def selected_mode_preflight(self, conversation):
        assert conversation == CONVERSATION
        if self.preflight_closed:
            self.runtime_tab_id = None
        else:
            self.runtime_tab_id = 777
        return {
            "conversation_id": conversation,
            "selected_mode": self.preflight_mode,
            "selected_mode_proven": self.preflight_proven,
            "candidate_count": 1,
            "nearest_distance_px": 20,
            "proof_kind": "nearest_composer_mode_control",
            "conversation_write_count": 0,
            "runtime_tab_id_during_probe": 700,
            "runtime_tab_id_after": None if self.preflight_closed else 777,
            "probe_tab_closed": self.preflight_closed,
            "tab_was_active": False,
            "tab_active_after": False,
            "tab_activated_during_probe": self.preflight_foreground,
            "foreground_activation_observed": self.preflight_foreground,
            "debugger_attached_after": False,
        }

    def status(self):
        self.status_calls += 1
        return SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=self.runtime_tab_id,
        )

    def phase_timing_for_lease(self, lease_id):
        number = int(lease_id.split("-")[-1])
        cold = (number - 1) % 3 == 0
        resolve = 1500 if cold else 1
        tab_ready = 3000 if cold else 1000
        delegated_native = 7000
        page = tab_ready + delegated_native
        return {
            "phase_timing_lease_id": lease_id,
            "phase_timing_schema_version": 1,
            "runtime_tab_resolve_call_count": 1,
            "runtime_tab_first_resolve_ms": resolve,
            "runtime_tab_resolve_total_ms": resolve,
            "runtime_tab_resolve_max_ms": resolve,
            "page_turn_elapsed_ms": page,
            "tab_ready_to_write_delegated_ms": tab_ready,
            "write_delegated_to_network_complete_ms": 2000,
            "network_complete_to_native_complete_ms": 5000,
            "write_delegated_to_native_complete_ms": delegated_native,
            "native_turn_elapsed_ms": resolve + page + 20,
            "other_native_overhead_ms": 20,
            "runtime_reloaded": False,
            "runtime_reload_ms": None,
        }

    def instant_mode_for_lease(self, lease_id):
        mode = "MEDIUM" if lease_id == self.mode_change_lease else "INSTANT"
        reasoning = lease_id == self.reasoning_lease
        return {
            "instant_mode_lease_id": lease_id,
            "instant_mode_schema_version": 1,
            "requested_model_mode": "INSTANT",
            "require_no_reasoning_route": True,
            "selected_mode_before_write": mode,
            "selected_mode_before_write_proven": True,
            "selected_mode_candidate_count": 1,
            "selected_mode_nearest_distance_px": 10,
            "selected_mode_proof_kind": "nearest_composer_mode_control",
            "conversation_request_observed": True,
            "request_evidence": {
                "model_identifiers": ["instant"] if self.network_proven else [],
                "model_modes": ["INSTANT"] if self.network_proven else [],
                "reasoning_states": [],
                "model_hint_keys": ["model"] if self.network_proven else [],
                "reasoning_hint_keys": [],
            },
            "response_evidence": {
                "model_identifiers": [],
                "model_modes": [],
                "reasoning_states": ["ON"] if reasoning else [],
                "model_hint_keys": [],
                "reasoning_hint_keys": ["reasoning_effort"] if reasoning else [],
            },
            "network_route_status": (
                "REASONING_ROUTE_OBSERVED"
                if reasoning
                else ("INSTANT_MODEL_ROUTE_OBSERVED" if self.network_proven else "INCONCLUSIVE")
            ),
            "instant_model_route_observed": self.network_proven,
            "reasoning_route_observed": reasoning,
            "reasoning_off_observed": False,
            "network_no_reasoning_route_proven": self.network_proven and not reasoning,
        }


class FakeRuntime:
    def __init__(self, provider: FakeProvider, clock: FakeClock) -> None:
        self.provider = provider
        self.clock = clock
        self.calls = []
        self.generation = 0

    def health(self, conversation):
        return SimpleNamespace(
            ready=True,
            canonical_status="completed",
            to_dict=lambda: {
                "ready": True,
                "canonical_status": "completed",
                "conversation_id": conversation,
            },
        )

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

    def send_text_observed(self, text, *, conversation, timeout, poll_interval, conversation_mode, **kwargs):
        self.generation += 1
        self.calls.append({"text": text, "conversation": conversation, **kwargs})
        created = self.provider.runtime_tab_id is None
        if created:
            self.provider.runtime_tab_id = 900 + self.generation
        tab_id = self.provider.runtime_tab_id
        issued = round(self.clock.monotonic() * 1000)
        self.clock.advance(0.2)
        released = round(self.clock.monotonic() * 1000)
        self.clock.advance(0.3)
        policy = kwargs.get("browser_authority_policy", "PERSISTENT")
        ttl_ms = kwargs.get("browser_authority_ttl_ms")
        if policy == "TURN_SCOPED":
            self.provider.runtime_tab_id = None
        lease_id = f"lease-{self.generation}"
        observation = SimpleNamespace(
            write_event_observed=True,
            runtime_tab_id=tab_id,
            runtime_tab_preexisting=not created,
            runtime_tab_created_for_turn=created,
            foreground_activation_observed=False,
            browser_authority_lease_id=lease_id,
            browser_authority_generation=self.generation,
            browser_authority_policy=policy,
            browser_authority_ttl_ms=ttl_ms,
            browser_authority_issued_at_ms=issued,
            browser_authority_released_at_ms=released,
            browser_authority_disposal_due_at_ms=released if policy == "TURN_SCOPED" else None,
            browser_authority_release_proven=True,
            browser_authority_disposal_action="CLOSE" if policy == "TURN_SCOPED" else "KEEP",
            turn_lifecycle_id=f"turn-{self.generation}",
            turn_lifecycle_state_at_write="WRITE_COMPLETED",
        )
        provenance = SimpleNamespace(
            completion=SimpleNamespace(completed=True, canonical_completion_proven=True),
            conversation_mode=SimpleNamespace(
                requested_conversation_mode=SimpleNamespace(value="NORMAL"),
                observed_conversation_mode=SimpleNamespace(value="NORMAL"),
                observed_mode_proven=True,
            ),
            transport="browser-owned",
            product_semantics="ordinary-chatgpt",
        )
        response = SimpleNamespace(conversation=SimpleNamespace(conversation_id=conversation))
        return SimpleNamespace(response=response, provenance=provenance, observation=observation)


def make_runner():
    clock = FakeClock()
    provider = FakeProvider()
    runtime = FakeRuntime(provider, clock)
    runner = InstantModePhaseLatencyRunner(runtime, provider=provider, monotonic=clock.monotonic, sleep=clock.sleep)
    return runner, runtime, provider


def run(runner, **kwargs):
    return runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
        conversation=CONVERSATION,
        replications=3,
        **kwargs,
    )


def test_manual_auto_switch_confirmation_is_required_before_any_work():
    runner, runtime, _ = make_runner()
    with pytest.raises(ValueError):
        runner.run(
            acknowledge_live_writes=True,
            confirm_instant_auto_switch_disabled=False,
            conversation=CONVERSATION,
        )
    assert runtime.calls == []


def test_missing_extension_support_fails_with_zero_writes():
    runner, runtime, provider = make_runner()
    provider.instant_supported = False
    report = run(runner)
    assert report["ok"] is False
    assert report["failure_phase"] == "instant_preflight"
    assert report["write_attempts"] == 0
    assert runtime.calls == []


def test_exact_conversation_must_prove_instant_before_writes():
    runner, runtime, provider = make_runner()
    provider.preflight_mode = "MEDIUM"
    report = run(runner)
    assert report["ok"] is False
    assert report["failure_phase"] == "instant_selected_mode_exact_conversation_preflight"
    assert report["write_attempts"] == 0
    assert runtime.calls == []


def test_preflight_must_restore_closed_baseline():
    runner, runtime, provider = make_runner()
    provider.preflight_closed = False
    report = run(runner)
    assert report["ok"] is False
    assert report["write_attempts"] == 0
    assert runtime.calls == []


def test_reasoning_route_observation_stops_after_completed_first_write_without_retry():
    runner, runtime, provider = make_runner()
    provider.reasoning_lease = "lease-1"
    report = run(runner)
    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_instant_cold_persistent_send"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 1
    assert len(runtime.calls) == 1
    assert report["failure"]["automatic_retry_attempted"] is False


def test_selected_mode_change_stops_after_completed_write_without_retry():
    runner, runtime, provider = make_runner()
    provider.mode_change_lease = "lease-2"
    report = run(runner)
    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_instant_warm_persistent_send"
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert len(runtime.calls) == 2


def test_network_metadata_may_be_inconclusive_when_manual_boundary_and_picker_remain_clean():
    runner, _, provider = make_runner()
    provider.network_proven = False
    report = run(runner)
    assert report["ok"] is True
    assert report["summary"]["positive_reasoning_route_observations"] == 0
    assert report["summary"]["network_route_inconclusive_count"] == 9
    assert report["summary"]["network_no_reasoning_route_proven_count"] == 0


def test_happy_path_replicates_three_cold_warm_close_cycles_and_keeps_policy_unchanged():
    runner, runtime, _ = make_runner()
    report = run(runner)
    assert report["ok"] is True
    assert report["write_budget"] == 9
    assert report["write_attempts"] == 9
    assert report["write_completions"] == 9
    assert len(report["cycles"]) == 3
    assert report["summary"]["instant_latency_characterization_completed"] is True
    assert report["summary"]["instant_selected_before_every_write"] is True
    assert report["summary"]["network_no_reasoning_route_proven_count"] == 9
    assert report["summary"]["all_cold_turns_created_new_runtime_tab"] is True
    assert report["summary"]["all_warm_turns_reused_same_runtime_tab"] is True
    assert report["summary"]["all_close_turns_reused_then_closed_runtime_tab"] is True
    assert report["summary"]["automatic_write_retry_attempted"] is False
    assert report["cross_mode_governance"]["library_default_change_performed"] is False
    assert report["cross_mode_governance"]["hde_assembly_policy_change_performed"] is False
    assert report["final_runtime_status"]["runtime_tab_id"] is None

    for cycle in report["cycles"]:
        assert cycle["cold_turn"]["observation"]["runtime_tab_created_for_turn"] is True
        assert cycle["warm_turn"]["observation"]["runtime_tab_preexisting"] is True
        assert cycle["close_turn"]["observation"]["browser_authority_policy"] == "TURN_SCOPED"
        assert cycle["close_disposal"]["confirmed"] is True
        assert cycle["closed_window"]["confirmed"] is True

    assert all("browser_authority_policy" not in runtime.calls[index] for index in (0, 1, 3, 4, 6, 7))
    assert all(runtime.calls[index]["browser_authority_policy"] == "TURN_SCOPED" for index in (2, 5, 8))
