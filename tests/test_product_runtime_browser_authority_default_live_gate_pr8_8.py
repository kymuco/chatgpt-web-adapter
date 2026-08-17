from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_runtime_browser_authority_default_live_gate import (
    ProductRuntimeDefaultIdleTtlLiveGate,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

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
    runtime_tab_id: int | None = 77
    lease_id_present: bool = False

    def to_dict(self):
        return {
            "supported": self.supported,
            "resource_sampling_supported": self.resource_sampling_supported,
            "runtime_tab_release_supported": self.runtime_tab_release_supported,
            "runtime_tab_id": self.runtime_tab_id,
            "lease_id_present": self.lease_id_present,
        }


class _Provider:
    def __init__(self) -> None:
        self.current_tab_id: int | None = 77
        self.support = _Support(runtime_tab_id=77)
        self.status_calls = 0

    def characterization_status(self):
        return self.support

    def status(self):
        self.status_calls += 1
        return _Status(runtime_tab_id=self.current_tab_id)


def _execution(
    *,
    conversation_id: str,
    tab_id: int,
    preexisting: bool,
    created: bool,
    generation: int,
    policy: str,
    ttl_ms: int | None,
    disposal_action: str,
):
    released_at = 10_000 * generation
    due_at = released_at + ttl_ms if ttl_ms is not None else None
    observation = SimpleNamespace(
        write_event_observed=True,
        runtime_tab_id=tab_id,
        runtime_tab_preexisting=preexisting,
        runtime_tab_created_for_turn=created,
        foreground_activation_observed=True,
        browser_authority_lease_id=f"lease-{generation}",
        browser_authority_generation=generation,
        browser_authority_policy=policy,
        browser_authority_ttl_ms=ttl_ms,
        browser_authority_issued_at_ms=released_at - 1000,
        browser_authority_released_at_ms=released_at,
        browser_authority_disposal_due_at_ms=due_at,
        browser_authority_release_proven=True,
        browser_authority_disposal_action=disposal_action,
        turn_lifecycle_id=f"turn-{generation}",
        turn_lifecycle_state_at_write="WRITE_COMPLETED",
    )
    provenance = SimpleNamespace(
        completion=SimpleNamespace(
            completed=True,
            canonical_completion_proven=True,
        ),
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


class _Runtime:
    def __init__(
        self,
        provider: _Provider,
        *,
        default_policy: str = "IDLE_TTL",
        default_ttl_ms: int = 5000,
        first_close: bool = True,
        persistent_retained: bool = True,
        restored_policy: str = "IDLE_TTL",
    ) -> None:
        self.provider = provider
        self.default_policy = default_policy
        self.default_ttl_ms = default_ttl_ms
        self.first_close = first_close
        self.persistent_retained = persistent_retained
        self.restored_policy = restored_policy
        self.calls = []

    def governance(self):
        return {
            "transport": "browser-owned",
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "browser_authority_policy_high_level_surface": True,
            "browser_authority_selected_transport_policy_support": True,
            "browser_authority_effective_runtime_default_policy": self.default_policy,
            "browser_authority_effective_runtime_default_ttl_ms": self.default_ttl_ms,
            "browser_authority_runtime_default_policy_source": "RUNTIME_DEFAULT",
            "browser_authority_policy_contract_scope": "RESOURCE_LIFECYCLE_ONLY",
            "temporary_mode_production_enabled": False,
        }

    def send_text_observed(self, text, **kwargs):
        self.calls.append((text, kwargs))
        call = len(self.calls)
        if call == 1:
            result = _execution(
                conversation_id="conversation-1",
                tab_id=77,
                preexisting=True,
                created=False,
                generation=1,
                policy="IDLE_TTL",
                ttl_ms=self.default_ttl_ms,
                disposal_action="CLOSE",
            )
            if self.first_close:
                self.provider.current_tab_id = None
            return result

        if call == 2:
            result = _execution(
                conversation_id="conversation-1",
                tab_id=202,
                preexisting=False,
                created=True,
                generation=2,
                policy="PERSISTENT",
                ttl_ms=None,
                disposal_action="KEEP",
            )
            self.provider.current_tab_id = 202 if self.persistent_retained else None
            return result

        if call == 3:
            if self.restored_policy == "IDLE_TTL":
                result = _execution(
                    conversation_id="conversation-1",
                    tab_id=202,
                    preexisting=True,
                    created=False,
                    generation=3,
                    policy="IDLE_TTL",
                    ttl_ms=self.default_ttl_ms,
                    disposal_action="CLOSE",
                )
            else:
                result = _execution(
                    conversation_id="conversation-1",
                    tab_id=202,
                    preexisting=True,
                    created=False,
                    generation=3,
                    policy=self.restored_policy,
                    ttl_ms=None,
                    disposal_action="KEEP",
                )
            self.provider.current_tab_id = None
            return result

        raise AssertionError("live gate exceeded three-write budget")


def _gate(runtime: _Runtime, provider: _Provider, clock: _Clock):
    return ProductRuntimeDefaultIdleTtlLiveGate(
        runtime,
        provider=provider,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def test_gate_requires_explicit_live_write_acknowledgement() -> None:
    provider = _Provider()
    runtime = _Runtime(provider)
    clock = _Clock()

    with pytest.raises(ValueError, match="three real product writes"):
        _gate(runtime, provider, clock).run(
            acknowledge_live_writes=False,
            expected_idle_ttl_ms=5000,
        )

    assert runtime.calls == []


def test_success_proves_runtime_default_override_precedence_and_restoration() -> None:
    provider = _Provider()
    runtime = _Runtime(provider)
    clock = _Clock()

    report = _gate(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        expected_idle_ttl_ms=5000,
        disposal_wait_timeout=1.0,
        retention_margin_seconds=1.0,
    )

    assert report["ok"] is True
    assert report["write_attempts"] == 3
    assert report["write_completions"] == 3
    assert report["failure"] is None
    assert report["runtime_default_initial_disposal"]["confirmed"] is True
    assert report["persistent_override_retention"]["confirmed"] is True
    assert (
        report["persistent_override_retention"]["observed_wait_ms"]
        >= 6000
    )
    assert report["runtime_default_restored_disposal"]["confirmed"] is True
    assert report["final_runtime_status"]["runtime_tab_id"] is None

    first_kwargs = runtime.calls[0][1]
    second_kwargs = runtime.calls[1][1]
    third_kwargs = runtime.calls[2][1]

    assert "browser_authority_policy" not in first_kwargs
    assert "browser_authority_ttl_ms" not in first_kwargs
    assert second_kwargs["browser_authority_policy"] == "PERSISTENT"
    assert "browser_authority_ttl_ms" not in second_kwargs
    assert "browser_authority_policy" not in third_kwargs
    assert "browser_authority_ttl_ms" not in third_kwargs

    summary = report["summary"]
    assert summary["runtime_default_idle_ttl_observed_on_initial_send"] is True
    assert summary["per_turn_override_precedence_proven"] is True
    assert summary["persistent_override_retained_beyond_runtime_ttl"] is True
    assert summary["runtime_default_restored_after_override"] is True
    assert summary["restored_default_reused_retained_runtime_tab"] is True
    assert summary["write_budget_respected"] is True
    assert summary["automatic_write_retry_attempted"] is False


def test_preflight_rejects_wrong_runtime_default_before_any_write() -> None:
    provider = _Provider()
    runtime = _Runtime(provider, default_policy="PERSISTENT")
    clock = _Clock()

    report = _gate(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        expected_idle_ttl_ms=5000,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "high_level_runtime_default_preflight"
    assert report["write_attempts"] == 0
    assert report["write_completions"] == 0
    assert runtime.calls == []


def test_unconfirmed_initial_idle_ttl_close_stops_before_override_write() -> None:
    provider = _Provider()
    runtime = _Runtime(provider, first_close=False)
    clock = _Clock()

    report = _gate(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        expected_idle_ttl_ms=5000,
        disposal_wait_timeout=0.2,
        retention_margin_seconds=0.1,
    )

    assert report["ok"] is False
    assert (
        report["failure_phase"]
        == "runtime_default_idle_ttl_initial_disposal_wait"
    )
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 1
    assert len(runtime.calls) == 1
    assert report["failure"]["automatic_retry_attempted"] is False


def test_persistent_override_must_survive_beyond_runtime_default_ttl() -> None:
    provider = _Provider()
    runtime = _Runtime(provider, persistent_retained=False)
    clock = _Clock()

    report = _gate(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        expected_idle_ttl_ms=5000,
        disposal_wait_timeout=0.2,
        retention_margin_seconds=0.1,
    )

    assert report["ok"] is False
    assert (
        report["failure_phase"]
        == "per_turn_persistent_override_retention_wait"
    )
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert len(runtime.calls) == 2
    assert report["persistent_override_retention"]["confirmed"] is False
    assert report["failure"]["automatic_retry_attempted"] is False


def test_runtime_default_must_restore_after_persistent_override() -> None:
    provider = _Provider()
    runtime = _Runtime(provider, restored_policy="PERSISTENT")
    clock = _Clock()

    report = _gate(runtime, provider, clock).run(
        acknowledge_live_writes=True,
        expected_idle_ttl_ms=5000,
        disposal_wait_timeout=0.2,
        retention_margin_seconds=0.1,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "runtime_default_idle_ttl_restored_send"
    assert report["write_attempts"] == 3
    assert report["write_completions"] == 3
    assert len(runtime.calls) == 3
    assert (
        report["runtime_default_restored_turn"]["observation"][
            "browser_authority_policy"
        ]
        == "PERSISTENT"
    )
    assert report["failure"]["automatic_retry_attempted"] is False
