from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_policy_replication_pr8_8 import (
    BrowserAuthorityPolicyReplicationRunner,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class _Status:
    available: bool = True
    extension_connected: bool = True
    runtime_tab_id: int | None = None


@dataclass
class _Support:
    supported: bool = True
    resource_sampling_supported: bool = True
    runtime_tab_release_supported: bool = True
    runtime_tab_id: int | None = None
    lease_id_present: bool = False

    def to_dict(self):
        return {
            "supported": self.supported,
            "resource_sampling_supported": self.resource_sampling_supported,
            "runtime_tab_release_supported": self.runtime_tab_release_supported,
            "runtime_tab_id": self.runtime_tab_id,
            "lease_id_present": self.lease_id_present,
        }


@dataclass
class _ResourceSample:
    runtime_tab_id: int
    requested_sample_ms: int
    observed_sample_ms: int
    task_duration_start_s: float = 10.0
    task_duration_end_s: float = 10.03
    task_duration_delta_s: float = 0.03
    task_time_fraction: float = 0.01
    js_heap_used_start_bytes: float = 90_000_000.0
    js_heap_used_end_bytes: float = 91_000_000.0
    js_heap_used_max_bytes: float = 92_000_000.0
    js_heap_total_start_bytes: float = 110_000_000.0
    js_heap_total_end_bytes: float = 110_000_000.0
    documents_start: int = 6
    documents_end: int = 6
    nodes_start: int = 9000
    nodes_end: int = 9010
    js_event_listeners_start: int = 1200
    js_event_listeners_end: int = 1201
    tab_was_active: bool = False
    tab_active_after: bool = False
    tab_activated_during_sample: bool = False
    foreground_activation_observed: bool = False
    debugger_attached_after: bool = False

    def to_dict(self):
        return dict(self.__dict__)


class _Provider:
    def __init__(
        self,
        clock: _Clock,
        *,
        initial_tab_id: int | None = None,
        debugger_leak: bool = False,
        sample_activates_tab: bool = False,
    ) -> None:
        self.clock = clock
        self.current_tab_id = initial_tab_id
        self.debugger_leak = debugger_leak
        self.sample_activates_tab = sample_activates_tab
        self.status_calls = 0
        self.resource_calls = 0

    def characterization_status(self):
        return _Support(runtime_tab_id=self.current_tab_id, lease_id_present=True)

    def status(self):
        self.status_calls += 1
        return _Status(runtime_tab_id=self.current_tab_id)

    def sample_runtime_tab_resources(self, *, sample_ms: int):
        self.resource_calls += 1
        assert self.current_tab_id is not None
        self.clock.sleep(sample_ms / 1000.0)
        return _ResourceSample(
            runtime_tab_id=self.current_tab_id,
            requested_sample_ms=sample_ms,
            observed_sample_ms=sample_ms,
            task_time_fraction=0.01 * self.resource_calls,
            js_heap_used_max_bytes=92_000_000.0 + self.resource_calls,
            tab_activated_during_sample=self.sample_activates_tab,
            foreground_activation_observed=self.sample_activates_tab,
            debugger_attached_after=self.debugger_leak,
        )


def _execution(
    clock: _Clock,
    *,
    conversation_id: str,
    tab_id: int,
    preexisting: bool,
    created: bool,
    generation: int,
    policy: str,
    ttl_ms: int | None,
    disposal_action: str,
    foreground: bool,
):
    returned_ms = int(round(clock.monotonic() * 1000))
    released_at = returned_ms - 5
    issued_at = released_at - 10
    due_at = released_at + ttl_ms if ttl_ms is not None else None
    observation = SimpleNamespace(
        write_event_observed=True,
        runtime_tab_id=tab_id,
        runtime_tab_preexisting=preexisting,
        runtime_tab_created_for_turn=created,
        foreground_activation_observed=foreground,
        browser_authority_lease_id=f"lease-{generation}",
        browser_authority_generation=generation,
        browser_authority_policy=policy,
        browser_authority_ttl_ms=ttl_ms,
        browser_authority_issued_at_ms=issued_at,
        browser_authority_released_at_ms=released_at,
        browser_authority_disposal_due_at_ms=due_at,
        browser_authority_release_proven=True,
        browser_authority_disposal_action=disposal_action,
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
            conversation=SimpleNamespace(conversation_id=conversation_id)
        ),
        provenance=provenance,
        observation=observation,
    )


class _DelegatedError(RuntimeError):
    failure_kind = "AMBIGUOUS_WRITE_OUTCOME"
    write_may_have_been_submitted = True
    reconciliation_required = True
    automatic_retry_allowed = False
    manual_retry_safe_after_repair = False
    request_stage = "browser_owned_write"


class _Runtime:
    def __init__(
        self,
        provider: _Provider,
        clock: _Clock,
        *,
        bad_warm_reuse: bool = False,
        close_sticks: bool = False,
        raise_call: int | None = None,
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.bad_warm_reuse = bad_warm_reuse
        self.close_sticks = close_sticks
        self.raise_call = raise_call
        self.calls: list[tuple[str, dict]] = []
        self.generation = 0

    def governance(self):
        return {
            "transport": "browser-owned",
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "browser_authority_policy_high_level_surface": True,
            "browser_authority_selected_transport_policy_support": True,
            "browser_authority_effective_runtime_default_policy": "PERSISTENT",
            "browser_authority_effective_runtime_default_ttl_ms": None,
            "browser_authority_runtime_default_policy_source": "TRANSPORT_DEFAULT",
            "browser_authority_policy_contract_scope": "RESOURCE_LIFECYCLE_ONLY",
            "temporary_mode_production_enabled": False,
        }

    def send_text_observed(self, text, **kwargs):
        self.calls.append((text, kwargs))
        call = len(self.calls)
        if self.raise_call == call:
            raise _DelegatedError("delegated outcome ambiguous")

        cycle = (call - 1) // 3 + 1
        stage = (call - 1) % 3
        self.generation += 1
        conversation_id = "conversation-1"

        if stage == 0:
            assert self.provider.current_tab_id is None
            tab_id = 1000 + cycle
            self.provider.current_tab_id = tab_id
            self.clock.sleep(0.030 + cycle * 0.001)
            return _execution(
                self.clock,
                conversation_id=conversation_id,
                tab_id=tab_id,
                preexisting=False,
                created=True,
                generation=self.generation,
                policy="PERSISTENT",
                ttl_ms=None,
                disposal_action="KEEP",
                foreground=cycle % 2 == 1,
            )

        if stage == 1:
            assert self.provider.current_tab_id is not None
            tab_id = self.provider.current_tab_id
            if self.bad_warm_reuse:
                tab_id += 500
            self.clock.sleep(0.020 + cycle * 0.001)
            return _execution(
                self.clock,
                conversation_id=conversation_id,
                tab_id=tab_id,
                preexisting=True,
                created=False,
                generation=self.generation,
                policy="PERSISTENT",
                ttl_ms=None,
                disposal_action="KEEP",
                foreground=False,
            )

        assert self.provider.current_tab_id is not None
        tab_id = self.provider.current_tab_id
        self.clock.sleep(0.015)
        result = _execution(
            self.clock,
            conversation_id=conversation_id,
            tab_id=tab_id,
            preexisting=True,
            created=False,
            generation=self.generation,
            policy="TURN_SCOPED",
            ttl_ms=0,
            disposal_action="CLOSE",
            foreground=True,
        )
        if not self.close_sticks:
            self.provider.current_tab_id = None
        return result


def _runner(runtime: _Runtime, provider: _Provider, clock: _Clock):
    return BrowserAuthorityPolicyReplicationRunner(
        runtime,
        provider=provider,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def test_replication_requires_explicit_live_write_acknowledgement() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock)

    with pytest.raises(ValueError, match="real product writes"):
        _runner(runtime, provider, clock).run(
            acknowledge_live_writes=False,
            replications=3,
        )

    assert runtime.calls == []


def test_success_replicates_three_warm_cold_cycles_and_characterizes_costs() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=3,
        resource_sample_ms=1000,
        disposal_wait_timeout=0.5,
        closed_stability_ms=200,
    )

    assert report["ok"] is True
    assert report["write_budget"] == 9
    assert report["write_attempts"] == 9
    assert report["write_completions"] == 9
    assert len(report["cycles"]) == 3
    assert provider.resource_calls == 3
    assert report["final_runtime_status"]["runtime_tab_id"] is None
    assert report["final_conversation_id"] == "conversation-1"

    for cycle in report["cycles"]:
        cold = cycle["cold_turn"]
        warm = cycle["warm_turn"]
        close = cycle["close_turn"]
        assert cold["observation"]["runtime_tab_created_for_turn"] is True
        assert warm["observation"]["runtime_tab_preexisting"] is True
        assert warm["observation"]["runtime_tab_id"] == cold["observation"]["runtime_tab_id"]
        assert close["observation"]["runtime_tab_id"] == warm["observation"]["runtime_tab_id"]
        assert cycle["close_disposal"]["confirmed"] is True
        assert cycle["closed_window"]["confirmed"] is True

    cost = report["cost_characterization"]
    assert cost["cold_total_ms"]["count"] == 3
    assert cost["warm_total_ms"]["count"] == 3
    assert cost["cold_minus_warm_total_ms"]["median"] > 0
    assert cost["interpretation"] == "descriptive_only_no_default_policy_threshold_applied"

    resource = report["resource_characterization"]
    assert resource["sample_count"] == 3
    assert resource["stable_closed_window_count"] == 3
    assert resource["sample_tab_activation_count"] == 0
    assert resource["debugger_leak_count"] == 0

    foreground = report["foreground_characterization"]
    assert foreground["cold"]["observed_true"] == 2
    assert foreground["warm"]["observed_false"] == 3
    assert foreground["all_writes"]["turn_count"] == 9

    for call_index, (_, kwargs) in enumerate(runtime.calls, start=1):
        stage = (call_index - 1) % 3
        if stage in {0, 1}:
            assert "browser_authority_policy" not in kwargs
            assert "browser_authority_ttl_ms" not in kwargs
        else:
            assert kwargs["browser_authority_policy"] == "TURN_SCOPED"
            assert kwargs["browser_authority_ttl_ms"] == 0

    summary = report["summary"]
    assert summary["independent_replication_completed"] is True
    assert summary["replication_count"] == 3
    assert summary["lease_ids_unique"] is True
    assert summary["lease_generation_strictly_increasing"] is True
    assert summary["default_policy_change_performed"] is False
    assert summary["automatic_write_retry_attempted"] is False


def test_preflight_requires_clean_closed_runtime_tab_without_writes() -> None:
    clock = _Clock()
    provider = _Provider(clock, initial_tab_id=77)
    runtime = _Runtime(provider, clock)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=2,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "replication_preflight"
    assert report["write_attempts"] == 0
    assert runtime.calls == []
    assert "INITIAL_RUNTIME_TAB_MUST_BE_ABSENT" in report["failure"]["message"]


def test_warm_reuse_mismatch_stops_before_resource_sample_and_close() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock, bad_warm_reuse=True)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=2,
        resource_sample_ms=1000,
        closed_stability_ms=200,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_warm_persistent_send"
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert len(runtime.calls) == 2
    assert provider.resource_calls == 0
    assert report["cycles"][0]["cold_turn"] is not None
    assert report["cycles"][0]["warm_turn"] is not None
    assert report["cycles"][0]["close_turn"] is None


def test_resource_sample_debugger_leak_stops_before_close_write() -> None:
    clock = _Clock()
    provider = _Provider(clock, debugger_leak=True)
    runtime = _Runtime(provider, clock)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=2,
        resource_sample_ms=1000,
        closed_stability_ms=200,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_retained_resource_sample"
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert len(runtime.calls) == 2
    assert report["cycles"][0]["retained_resource_sample"]["debugger_attached_after"] is True
    assert report["failure"]["automatic_retry_attempted"] is False


def test_unconfirmed_close_stops_before_next_cold_write() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock, close_sticks=True)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=2,
        resource_sample_ms=1000,
        disposal_wait_timeout=0.2,
        closed_stability_ms=200,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_close_disposal_wait"
    assert report["write_attempts"] == 3
    assert report["write_completions"] == 3
    assert len(runtime.calls) == 3
    assert report["cycles"][0]["close_disposal"]["confirmed"] is False
    assert report["failure"]["automatic_retry_attempted"] is False


def test_ambiguous_delegated_failure_never_advances_or_retries() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock, raise_call=2)

    report = _runner(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        replications=2,
        resource_sample_ms=1000,
        closed_stability_ms=200,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "cycle_01_warm_persistent_send"
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 1
    assert len(runtime.calls) == 2
    assert report["failure"]["write_may_have_been_submitted"] is True
    assert report["failure"]["reconciliation_required"] is True
    assert report["failure"]["automatic_retry_allowed"] is False
    assert report["failure"]["automatic_retry_attempted"] is False


def test_replication_count_is_bounded_before_any_write() -> None:
    clock = _Clock()
    provider = _Provider(clock)
    runtime = _Runtime(provider, clock)

    with pytest.raises(ValueError, match="between 2 and 5"):
        _runner(runtime, provider, clock).run(
            acknowledge_live_writes=True,
            replications=6,
        )

    assert runtime.calls == []
