from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
    BrowserAuthorityCharacterizationStatus,
    BrowserAuthorityLiveCharacterizationRunner,
    BrowserAuthorityRuntimeResourceSample,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir
from chatgpt_web_adapter.browser_native_provider import BrowserNativeBridgeStatus


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeCharacterizationProvider:
    def __init__(
        self,
        *,
        supported: bool = True,
        resource_supported: bool = True,
        release_supported: bool = True,
        resource_foreground: bool = False,
    ) -> None:
        self.runtime_tab_id: int | None = None
        self.supported = supported
        self.resource_supported = resource_supported
        self.release_supported = release_supported
        self.resource_foreground = resource_foreground
        self.characterization_status_calls = 0
        self.resource_sample_calls = 0
        self.status_calls = 0

    def characterization_status(self):
        self.characterization_status_calls += 1
        return BrowserAuthorityCharacterizationStatus(
            supported=self.supported,
            resource_sampling_supported=self.resource_supported,
            runtime_tab_release_supported=self.release_supported,
            runtime_tab_id=self.runtime_tab_id,
            lease_id_present=False,
        )

    def sample_runtime_tab_resources(self, *, sample_ms: int):
        self.resource_sample_calls += 1
        assert self.runtime_tab_id is not None
        return BrowserAuthorityRuntimeResourceSample(
            runtime_tab_id=self.runtime_tab_id,
            requested_sample_ms=sample_ms,
            observed_sample_ms=sample_ms,
            task_duration_start_s=10.0,
            task_duration_end_s=10.01,
            task_duration_delta_s=0.01,
            task_time_fraction=0.002,
            js_heap_used_start_bytes=100.0,
            js_heap_used_end_bytes=120.0,
            js_heap_used_max_bytes=120.0,
            js_heap_total_start_bytes=200.0,
            js_heap_total_end_bytes=200.0,
            documents_start=1,
            documents_end=1,
            nodes_start=100,
            nodes_end=101,
            js_event_listeners_start=5,
            js_event_listeners_end=5,
            tab_was_active=False,
            tab_active_after=False,
            tab_activated_during_sample=self.resource_foreground,
            foreground_activation_observed=self.resource_foreground,
            debugger_attached_after=False,
        )

    def status(self):
        self.status_calls += 1
        return BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=self.runtime_tab_id,
        )


class FakeRuntime:
    def __init__(
        self,
        provider: FakeCharacterizationProvider,
        clock: FakeClock,
        *,
        suppress_turn_scoped_disposal: bool = False,
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.suppress_turn_scoped_disposal = suppress_turn_scoped_disposal
        self.calls: list[dict[str, object]] = []
        self.generation = 0
        self._snapshot = {
            "browser_authority_lease": None,
            "turn_lifecycle": None,
            "pending_disposal": False,
            "last_disposal_result": None,
        }

    def send_text_observed(
        self,
        text,
        *,
        conversation,
        timeout,
        poll_interval,
        browser_authority_policy,
        browser_authority_ttl_ms,
        **kwargs,
    ):
        self.generation += 1
        self.calls.append(
            {
                "text": text,
                "conversation": conversation,
                "policy": browser_authority_policy.value,
                "ttl_ms": browser_authority_ttl_ms,
            }
        )
        created = self.provider.runtime_tab_id is None
        if created:
            self.provider.runtime_tab_id = 100 + self.generation
        runtime_tab_id = self.provider.runtime_tab_id
        self.clock.advance(0.1)

        lease_id = f"lease-{self.generation}"
        issued_at_ms = self.generation * 1000
        released_at_ms = issued_at_ms + 50
        lifecycle = {
            "state": "FINALIZED",
            "write_completed_at_ms": released_at_ms,
            "terminal_at_ms": released_at_ms + 20,
        }
        self._snapshot = {
            "browser_authority_lease": {
                "lease_id": lease_id,
                "state": "RELEASED",
            },
            "turn_lifecycle": lifecycle,
            "pending_disposal": browser_authority_policy.value != "PERSISTENT",
            "last_disposal_result": None,
        }

        should_dispose = browser_authority_policy.value in {"TURN_SCOPED", "IDLE_TTL"}
        if (
            browser_authority_policy.value == "TURN_SCOPED"
            and self.suppress_turn_scoped_disposal
        ):
            should_dispose = False
        if should_dispose:
            self.provider.runtime_tab_id = None
            self._snapshot["pending_disposal"] = False
            self._snapshot["last_disposal_result"] = {
                "lease_id": lease_id,
                "status": "CLOSED",
                "runtime_tab_id": runtime_tab_id,
            }

        observation = SimpleNamespace(
            write_event_observed=True,
            runtime_tab_id=runtime_tab_id,
            runtime_tab_preexisting=not created,
            runtime_tab_created_for_turn=created,
            foreground_activation_observed=False,
            browser_authority_lease_id=lease_id,
            browser_authority_generation=self.generation,
            browser_authority_release_proven=True,
            browser_authority_issued_at_ms=issued_at_ms,
            browser_authority_released_at_ms=released_at_ms,
            browser_authority_disposal_due_at_ms=(
                released_at_ms + (browser_authority_ttl_ms or 0)
                if browser_authority_policy.value != "PERSISTENT"
                else None
            ),
            turn_lifecycle_state_at_write="WRITE_COMPLETED",
        )
        conversation_id = conversation or "conversation-1"
        response = SimpleNamespace(
            conversation=SimpleNamespace(conversation_id=conversation_id)
        )
        return SimpleNamespace(response=response, observation=observation)

    def lifecycle_snapshot(self):
        return self._snapshot


def build_runner(
    *,
    provider: FakeCharacterizationProvider | None = None,
    suppress_turn_scoped_disposal: bool = False,
):
    clock = FakeClock()
    provider = provider or FakeCharacterizationProvider()
    runtime = FakeRuntime(
        provider,
        clock,
        suppress_turn_scoped_disposal=suppress_turn_scoped_disposal,
    )
    runner = BrowserAuthorityLiveCharacterizationRunner(
        object(),
        provider=provider,
        runtime=runtime,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    return runner, provider, runtime


def test_live_runner_requires_explicit_write_acknowledgement_before_any_probe() -> None:
    runner, provider, runtime = build_runner()

    with pytest.raises(ValueError, match="five real product writes"):
        runner.run(acknowledge_live_writes=False)

    assert provider.characterization_status_calls == 0
    assert runtime.calls == []


def test_live_runner_fails_before_write_when_updated_extension_is_not_loaded() -> None:
    provider = FakeCharacterizationProvider(resource_supported=False)
    runner, provider, runtime = build_runner(provider=provider)

    report = runner.run(
        acknowledge_live_writes=True,
        idle_sample_ms=1000,
        idle_ttl_ms=1000,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "extension_preflight"
    assert "EXTENSION_RELOAD_REQUIRED" in report["failure"]["message"]
    assert report["write_attempts"] == 0
    assert runtime.calls == []


def test_live_runner_happy_path_is_bounded_five_write_policy_sequence() -> None:
    runner, provider, runtime = build_runner()

    report = runner.run(
        acknowledge_live_writes=True,
        idle_sample_ms=1000,
        idle_ttl_ms=1000,
    )

    assert report["ok"] is True
    assert report["write_attempts"] == 5
    assert report["write_completions"] == 5
    assert len(runtime.calls) == 5
    assert [call["policy"] for call in runtime.calls] == [
        "PERSISTENT",
        "PERSISTENT",
        "TURN_SCOPED",
        "PERSISTENT",
        "IDLE_TTL",
    ]
    assert [call["ttl_ms"] for call in runtime.calls] == [
        None,
        None,
        0,
        None,
        1000,
    ]
    assert provider.resource_sample_calls == 1
    assert report["turn_scoped_disposal"]["confirmed"] is True
    assert report["idle_ttl_disposal"]["confirmed"] is True
    assert report["turns"][3]["runtime_tab_created_for_turn"] is True
    assert report["summary"]["warm_reuse_observed"] is True
    assert report["summary"]["next_turn_after_close_succeeded"] is True
    assert (
        report["summary"]["canonical_finality_preserved_after_turn_scoped_close"]
        is True
    )
    assert report["summary"]["write_budget_respected"] is True
    assert report["summary"]["idle_main_thread_task_time_fraction"] == 0.002
    assert report["summary"]["idle_js_heap_used_max_bytes"] == 120.0


def test_live_runner_never_continues_after_turn_scoped_close_is_unproven() -> None:
    runner, _, runtime = build_runner(suppress_turn_scoped_disposal=True)

    report = runner.run(
        acknowledge_live_writes=True,
        idle_sample_ms=1000,
        idle_ttl_ms=1000,
        disposal_wait_timeout=0.2,
    )

    assert report["ok"] is False
    assert report["failure_phase"] == "turn_scoped_disposal_wait"
    assert report["write_attempts"] == 3
    assert report["write_completions"] == 3
    assert len(runtime.calls) == 3
    assert report["failure"]["automatic_retry_attempted"] is False


def test_live_runner_propagates_foreground_disturbance_from_resource_probe() -> None:
    provider = FakeCharacterizationProvider(resource_foreground=True)
    runner, _, _ = build_runner(provider=provider)

    report = runner.run(
        acknowledge_live_writes=True,
        idle_sample_ms=1000,
        idle_ttl_ms=1000,
    )

    assert report["ok"] is True
    assert report["resource_sample"]["foreground_activation_observed"] is True
    assert report["summary"]["foreground_disturbance_observed"] is True


def test_characterization_status_uses_read_only_turn_lane(monkeypatch) -> None:
    provider = BrowserAuthorityCharacterizationProvider()
    captured = {}

    def fake_rpc(payload, *, timeout):
        captured["payload"] = dict(payload)
        return {
            "protocol": 1,
            "type": "turn_result",
            "request_id": payload["request_id"],
            "ok": True,
            "characterizationSupported": True,
            "resourceSamplingSupported": True,
            "runtimeTabReleaseSupported": True,
            "runtimeTabId": 42,
            "leaseIdPresent": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    status = provider.characterization_status(timeout=2.0)

    assert captured["payload"]["type"] == "turn"
    assert captured["payload"]["characterizeBrowserAuthorityStatus"] is True
    assert "text" not in captured["payload"]
    assert status.supported is True
    assert status.runtime_tab_id == 42


def test_resource_sample_serializes_bounded_read_only_request(monkeypatch) -> None:
    provider = BrowserAuthorityCharacterizationProvider()
    captured = {}

    def fake_rpc(payload, *, timeout):
        captured["payload"] = dict(payload)
        return {
            "protocol": 1,
            "type": "turn_result",
            "request_id": payload["request_id"],
            "ok": True,
            "runtimeTabId": 42,
            "observedSampleMs": 1000,
            "taskDurationStartS": 1.0,
            "taskDurationEndS": 1.02,
            "taskDurationDeltaS": 0.02,
            "taskTimeFraction": 0.02,
            "jsHeapUsedStartBytes": 100,
            "jsHeapUsedEndBytes": 110,
            "jsHeapUsedMaxBytes": 110,
            "jsHeapTotalStartBytes": 200,
            "jsHeapTotalEndBytes": 210,
            "documentsStart": 1,
            "documentsEnd": 1,
            "nodesStart": 50,
            "nodesEnd": 51,
            "jsEventListenersStart": 5,
            "jsEventListenersEnd": 5,
            "tabWasActive": False,
            "tabActiveAfter": False,
            "tabActivatedDuringSample": False,
            "foregroundActivationObserved": False,
            "debuggerAttachedAfter": False,
        }

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    sample = provider.sample_runtime_tab_resources(sample_ms=1000, timeout=3.0)

    assert captured["payload"]["type"] == "turn"
    assert captured["payload"]["characterizeBrowserAuthorityResources"] is True
    assert captured["payload"]["sampleMs"] == 1000
    assert "text" not in captured["payload"]
    assert sample.runtime_tab_id == 42
    assert sample.task_time_fraction == pytest.approx(0.02)
    assert sample.debugger_attached_after is False


@pytest.mark.parametrize("sample_ms", [0, 999, 15001])
def test_resource_sample_rejects_unbounded_windows(sample_ms: int) -> None:
    provider = BrowserAuthorityCharacterizationProvider()
    with pytest.raises(ValueError, match="between 1000 and 15000"):
        provider.sample_runtime_tab_resources(sample_ms=sample_ms)


def test_resource_sample_requires_timeout_longer_than_window() -> None:
    provider = BrowserAuthorityCharacterizationProvider()
    with pytest.raises(ValueError, match="timeout must exceed sample window"):
        provider.sample_runtime_tab_resources(sample_ms=5000, timeout=5.0)


def test_pr88_live_characterization_is_read_only_below_temporary_wrappers() -> None:
    root = browser_native_extension_dir()
    worker = (
        root / "service_worker_runtime_tab_reconciliation.js"
    ).read_text(encoding="utf-8")

    assert "characterizeBrowserAuthorityStatus" in worker
    assert "characterizeBrowserAuthorityResources" in worker
    assert 'probeContext: "browser_authority_characterization_support"' in worker
    assert 'probeContext: "browser_authority_runtime_tab_idle_resources"' in worker
    assert '"Performance.getMetrics"' in worker
    assert '"Memory.getDOMCounters"' in worker
    assert "PR88_RESOURCE_SAMPLE_MIN_MS = 1000" in worker
    assert "PR88_RESOURCE_SAMPLE_MAX_MS = 15000" in worker
    assert "message?.text != null" in worker
    assert "PR8_8_RESOURCE_SAMPLE_FLAG_CONFLICT" in worker
    assert "Input.insertText" not in worker
    assert "submitOfficialPageTurn" not in worker


def test_pr88_resource_probe_reports_foreground_and_debugger_hygiene() -> None:
    root = browser_native_extension_dir()
    worker = (
        root / "service_worker_runtime_tab_reconciliation.js"
    ).read_text(encoding="utf-8")

    assert "tabActivatedDuringSample" in worker
    assert "foregroundActivationObserved" in worker
    assert "debuggerAttachedAfter" in worker
    assert "chrome.tabs.onActivated.addListener" in worker
    assert "chrome.tabs.onActivated.removeListener" in worker
    assert "chrome.debugger.detach" in worker
