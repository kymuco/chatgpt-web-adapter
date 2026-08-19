from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.product_runtime_browser_authority_live_gate import (
    ProductRuntimeBrowserAuthorityLiveGate,
)


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _Support:
    def __init__(
        self,
        *,
        supported: bool = True,
        runtime_tab_release_supported: bool = True,
        runtime_tab_id: int | None = 41,
    ) -> None:
        self.supported = supported
        self.resource_sampling_supported = True
        self.runtime_tab_release_supported = runtime_tab_release_supported
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


class _Provider:
    def __init__(self, *, support=None, statuses=None) -> None:
        self.support = support or _Support()
        self.statuses = list(statuses or [])
        self.last_status = SimpleNamespace(
            available=True,
            extension_connected=True,
            runtime_tab_id=41,
        )
        self.status_calls = 0
        self.characterization_calls = 0

    def characterization_status(self):
        self.characterization_calls += 1
        return self.support

    def status(self):
        self.status_calls += 1
        if self.statuses:
            self.last_status = self.statuses.pop(0)
        return self.last_status


class _Runtime:
    def __init__(self, executions=None, *, governance=None) -> None:
        self.executions = list(executions or [])
        self.calls = []
        self._governance = {
            "transport": "browser-owned",
            "automatic_write_retry": False,
            "canonical_readback_required": True,
            "browser_authority_policy_high_level_surface": True,
            "browser_authority_selected_transport_policy_support": True,
            "browser_authority_effective_runtime_default_policy": "PERSISTENT",
            "browser_authority_effective_runtime_default_ttl_ms": None,
            "browser_authority_policy_contract_scope": "RESOURCE_LIFECYCLE_ONLY",
            "temporary_mode_production_enabled": False,
        }
        if governance is not None:
            self._governance.update(governance)

    def governance(self):
        return dict(self._governance)

    def send_text_observed(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if not self.executions:
            raise AssertionError("unexpected high-level product write")
        item = self.executions.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _mode_provenance():
    return SimpleNamespace(
        requested_conversation_mode=SimpleNamespace(value="NORMAL"),
        observed_conversation_mode=SimpleNamespace(value="NORMAL"),
        observed_mode_proven=True,
    )


def _execution(
    *,
    conversation_id: str,
    tab_id: int,
    policy: str,
    ttl_ms: int | None,
    disposal_action: str,
    created_for_turn: bool,
    canonical_completion_proven: bool = True,
):
    return SimpleNamespace(
        response=SimpleNamespace(
            conversation=SimpleNamespace(conversation_id=conversation_id)
        ),
        provenance=SimpleNamespace(
            completion=SimpleNamespace(
                completed=True,
                canonical_completion_proven=canonical_completion_proven,
            ),
            conversation_mode=_mode_provenance(),
            transport="browser-owned",
            product_semantics="ordinary-chatgpt",
        ),
        observation=SimpleNamespace(
            write_event_observed=True,
            runtime_tab_id=tab_id,
            runtime_tab_preexisting=not created_for_turn,
            runtime_tab_created_for_turn=created_for_turn,
            foreground_activation_observed=True,
            browser_authority_lease_id=f"lease-{tab_id}",
            browser_authority_generation=1,
            browser_authority_policy=policy,
            browser_authority_ttl_ms=ttl_ms,
            browser_authority_issued_at_ms=1000,
            browser_authority_released_at_ms=2000,
            browser_authority_disposal_due_at_ms=(
                2000 if policy == "TURN_SCOPED" and ttl_ms == 0 else None
            ),
            browser_authority_release_proven=True,
            browser_authority_disposal_action=disposal_action,
            turn_lifecycle_id=f"turn-{tab_id}",
            turn_lifecycle_state_at_write="WRITE_COMPLETED",
        ),
    )


def _bridge_status(tab_id: int | None):
    return SimpleNamespace(
        available=True,
        extension_connected=True,
        runtime_tab_id=tab_id,
    )


def _runner(runtime, provider):
    clock = _Clock()
    return ProductRuntimeBrowserAuthorityLiveGate(
        runtime,
        provider=provider,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def test_live_gate_requires_explicit_write_acknowledgement() -> None:
    runtime = _Runtime()
    provider = _Provider()

    with pytest.raises(ValueError, match="two real product writes"):
        _runner(runtime, provider).run(acknowledge_live_writes=False)

    assert runtime.calls == []
    assert provider.characterization_calls == 0


def test_preflight_failure_is_zero_write() -> None:
    runtime = _Runtime(
        governance={"browser_authority_policy_high_level_surface": False}
    )
    provider = _Provider()

    report = _runner(runtime, provider).run(acknowledge_live_writes=True)

    assert report["ok"] is False
    assert report["failure_phase"] == "high_level_preflight"
    assert report["write_attempts"] == 0
    assert report["write_completions"] == 0
    assert runtime.calls == []


def test_happy_path_uses_two_public_runtime_writes_and_preserves_default() -> None:
    conversation_id = "conversation-1"
    first = _execution(
        conversation_id=conversation_id,
        tab_id=41,
        policy="TURN_SCOPED",
        ttl_ms=0,
        disposal_action="CLOSE",
        created_for_turn=False,
    )
    second = _execution(
        conversation_id=conversation_id,
        tab_id=52,
        policy="PERSISTENT",
        ttl_ms=None,
        disposal_action="KEEP",
        created_for_turn=True,
    )
    runtime = _Runtime([first, second])
    provider = _Provider(statuses=[_bridge_status(None), _bridge_status(52)])

    report = _runner(runtime, provider).run(acknowledge_live_writes=True)

    assert report["ok"] is True
    assert report["write_budget"] == 2
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert report["final_conversation_id"] == conversation_id
    assert report["turn_scoped_disposal"]["confirmed"] is True
    assert report["summary"]["high_level_turn_scoped_override_observed"] is True
    assert report["summary"]["browser_authority_recreated_for_next_high_level_turn"] is True
    assert report["summary"]["default_persistent_policy_preserved"] is True
    assert report["summary"]["runtime_tab_id_changed_after_close"] is True
    assert report["summary"]["automatic_write_retry_attempted"] is False

    first_text, first_kwargs = runtime.calls[0]
    assert "SDK_PR8_8_HIGH_LEVEL_TURN_SCOPED_OK" in first_text
    assert first_kwargs["conversation"] is None
    assert first_kwargs["conversation_mode"] == "normal"
    assert first_kwargs["browser_authority_policy"] == "TURN_SCOPED"
    assert first_kwargs["browser_authority_ttl_ms"] == 0

    second_text, second_kwargs = runtime.calls[1]
    assert "SDK_PR8_8_HIGH_LEVEL_POST_CLOSE_PERSISTENT_OK" in second_text
    assert second_kwargs["conversation"] == conversation_id
    assert second_kwargs["conversation_mode"] == "normal"
    assert "browser_authority_policy" not in second_kwargs
    assert "browser_authority_ttl_ms" not in second_kwargs


def test_close_not_confirmed_stops_before_second_product_write() -> None:
    first = _execution(
        conversation_id="conversation-1",
        tab_id=41,
        policy="TURN_SCOPED",
        ttl_ms=0,
        disposal_action="CLOSE",
        created_for_turn=False,
    )
    runtime = _Runtime([first])
    provider = _Provider(statuses=[_bridge_status(41)] * 4)

    report = _runner(runtime, provider).run(
        acknowledge_live_writes=True,
        disposal_wait_timeout=0.25,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "turn_scoped_high_level_disposal_wait"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 1
    assert len(runtime.calls) == 1
    assert report["failure"]["automatic_retry_attempted"] is False


def test_missing_canonical_finality_stops_after_first_return_without_retry() -> None:
    first = _execution(
        conversation_id="conversation-1",
        tab_id=41,
        policy="TURN_SCOPED",
        ttl_ms=0,
        disposal_action="CLOSE",
        created_for_turn=False,
        canonical_completion_proven=False,
    )
    runtime = _Runtime([first])
    provider = _Provider()

    report = _runner(runtime, provider).run(acknowledge_live_writes=True)

    assert report["ok"] is False
    assert report["failure_phase"] == "turn_scoped_high_level_send"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 1
    assert len(runtime.calls) == 1
    assert provider.status_calls == 0


def test_post_close_recreation_must_be_observed() -> None:
    conversation_id = "conversation-1"
    first = _execution(
        conversation_id=conversation_id,
        tab_id=41,
        policy="TURN_SCOPED",
        ttl_ms=0,
        disposal_action="CLOSE",
        created_for_turn=False,
    )
    second = _execution(
        conversation_id=conversation_id,
        tab_id=52,
        policy="PERSISTENT",
        ttl_ms=None,
        disposal_action="KEEP",
        created_for_turn=False,
    )
    runtime = _Runtime([first, second])
    provider = _Provider(statuses=[_bridge_status(None)])

    report = _runner(runtime, provider).run(acknowledge_live_writes=True)

    assert report["ok"] is False
    assert report["failure_phase"] == "post_close_default_persistent_send"
    assert report["write_attempts"] == 2
    assert report["write_completions"] == 2
    assert len(runtime.calls) == 2


def test_delegated_failure_is_not_retried_by_gate() -> None:
    error = RuntimeError("synthetic delegated failure")
    runtime = _Runtime([error])
    provider = _Provider()

    report = _runner(runtime, provider).run(acknowledge_live_writes=True)

    assert report["ok"] is False
    assert report["failure_phase"] == "turn_scoped_high_level_send"
    assert report["write_attempts"] == 1
    assert report["write_completions"] == 0
    assert len(runtime.calls) == 1
    assert report["failure"]["automatic_retry_attempted"] is False


def test_gate_source_uses_public_product_runtime_without_private_writer_or_release() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "src"
        / "chatgpt_web_adapter"
        / "product_runtime_browser_authority_live_gate.py"
    ).read_text(encoding="utf-8")

    assert "ChatGPTProductRuntime" in source
    assert ".send_text_observed(" in source
    assert "._writer" not in source
    assert "lifecycle_snapshot(" not in source
    assert "release_runtime_tab(" not in source
    assert "BrowserOwnedProductWriteRuntime" not in source
