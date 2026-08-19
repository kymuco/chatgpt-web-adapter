from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .browser_authority_lease import BrowserAuthorityPolicy
from .browser_native_provider import BrowserNativeBridgeStatus, BrowserNativeTurnProvider
from .browser_owned_write_runtime import (
    BrowserOwnedProductWriteRuntime,
    BrowserOwnedWriteRuntimeError,
)
from .client import ChatGPTWebClient
from .exceptions import RequestError

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_IDLE_SAMPLE_MS = 5_000
DEFAULT_IDLE_TTL_MS = 5_000
DEFAULT_DISPOSAL_WAIT_SECONDS = 15.0

LIVE_PROMPTS = {
    "persistent_initial": "Reply with exactly: SDK_PR8_8_PERSISTENT_INITIAL_OK",
    "persistent_warm": "Reply with exactly: SDK_PR8_8_PERSISTENT_WARM_OK",
    "turn_scoped_close": "Reply with exactly: SDK_PR8_8_TURN_SCOPED_CLOSE_OK",
    "post_close_recreation": "Reply with exactly: SDK_PR8_8_POST_CLOSE_RECREATION_OK",
    "idle_ttl_close": "Reply with exactly: SDK_PR8_8_IDLE_TTL_CLOSE_OK",
}


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


@dataclass(frozen=True)
class BrowserAuthorityCharacterizationStatus:
    supported: bool
    resource_sampling_supported: bool
    runtime_tab_release_supported: bool
    runtime_tab_id: int | None
    lease_id_present: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserAuthorityRuntimeResourceSample:
    runtime_tab_id: int
    requested_sample_ms: int
    observed_sample_ms: int
    task_duration_start_s: float | None
    task_duration_end_s: float | None
    task_duration_delta_s: float | None
    task_time_fraction: float | None
    js_heap_used_start_bytes: float | None
    js_heap_used_end_bytes: float | None
    js_heap_used_max_bytes: float | None
    js_heap_total_start_bytes: float | None
    js_heap_total_end_bytes: float | None
    documents_start: int | None
    documents_end: int | None
    nodes_start: int | None
    nodes_end: int | None
    js_event_listeners_start: int | None
    js_event_listeners_end: int | None
    tab_was_active: bool
    tab_active_after: bool | None
    tab_activated_during_sample: bool
    foreground_activation_observed: bool
    debugger_attached_after: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrowserAuthorityCharacterizationProvider(BrowserNativeTurnProvider):
    """PR8.8 read-only characterization RPCs on the serialized turn lane."""

    def _characterization_rpc(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                **payload,
            },
            timeout=timeout + self.connect_timeout,
        )
        if response.get("request_id") != request_id:
            raise RequestError(
                "BROWSER_NATIVE_RESPONSE_MISMATCH",
                request_stage="browser_authority_characterization",
            )
        if not response.get("ok"):
            error = response.get("error") or "BROWSER_AUTHORITY_CHARACTERIZATION_FAILED"
            raise RequestError(
                str(error),
                request_stage="browser_authority_characterization",
            )
        return response

    def characterization_status(
        self,
        *,
        timeout: float | None = None,
    ) -> BrowserAuthorityCharacterizationStatus:
        total_timeout = self.connect_timeout if timeout is None else float(timeout)
        response = self._characterization_rpc(
            {
                "characterizeBrowserAuthorityStatus": True,
                "timeoutMs": int(max(1.0, total_timeout) * 1000),
            },
            timeout=max(1.0, total_timeout),
        )
        return BrowserAuthorityCharacterizationStatus(
            supported=bool(response.get("characterizationSupported")),
            resource_sampling_supported=bool(response.get("resourceSamplingSupported")),
            runtime_tab_release_supported=bool(response.get("runtimeTabReleaseSupported")),
            runtime_tab_id=_optional_int(response.get("runtimeTabId")),
            lease_id_present=bool(response.get("leaseIdPresent")),
        )

    def sample_runtime_tab_resources(
        self,
        *,
        sample_ms: int = DEFAULT_IDLE_SAMPLE_MS,
        timeout: float | None = None,
    ) -> BrowserAuthorityRuntimeResourceSample:
        if isinstance(sample_ms, bool) or not isinstance(sample_ms, int):
            raise TypeError("sample_ms must be an int")
        if sample_ms < 1_000 or sample_ms > 15_000:
            raise ValueError("sample_ms must be between 1000 and 15000")
        total_timeout = (
            max(self.connect_timeout, sample_ms / 1000.0 + 5.0)
            if timeout is None
            else float(timeout)
        )
        if total_timeout <= sample_ms / 1000.0:
            raise ValueError("timeout must exceed sample window")
        response = self._characterization_rpc(
            {
                "characterizeBrowserAuthorityResources": True,
                "sampleMs": sample_ms,
                "timeoutMs": int(total_timeout * 1000),
            },
            timeout=total_timeout,
        )
        runtime_tab_id = _optional_int(response.get("runtimeTabId"))
        if runtime_tab_id is None:
            raise RequestError(
                "BROWSER_AUTHORITY_RESOURCE_SAMPLE_MISSING_RUNTIME_TAB",
                request_stage="browser_authority_characterization",
            )
        return BrowserAuthorityRuntimeResourceSample(
            runtime_tab_id=runtime_tab_id,
            requested_sample_ms=sample_ms,
            observed_sample_ms=_optional_int(response.get("observedSampleMs")) or sample_ms,
            task_duration_start_s=_optional_float(response.get("taskDurationStartS")),
            task_duration_end_s=_optional_float(response.get("taskDurationEndS")),
            task_duration_delta_s=_optional_float(response.get("taskDurationDeltaS")),
            task_time_fraction=_optional_float(response.get("taskTimeFraction")),
            js_heap_used_start_bytes=_optional_float(response.get("jsHeapUsedStartBytes")),
            js_heap_used_end_bytes=_optional_float(response.get("jsHeapUsedEndBytes")),
            js_heap_used_max_bytes=_optional_float(response.get("jsHeapUsedMaxBytes")),
            js_heap_total_start_bytes=_optional_float(response.get("jsHeapTotalStartBytes")),
            js_heap_total_end_bytes=_optional_float(response.get("jsHeapTotalEndBytes")),
            documents_start=_optional_int(response.get("documentsStart")),
            documents_end=_optional_int(response.get("documentsEnd")),
            nodes_start=_optional_int(response.get("nodesStart")),
            nodes_end=_optional_int(response.get("nodesEnd")),
            js_event_listeners_start=_optional_int(response.get("jsEventListenersStart")),
            js_event_listeners_end=_optional_int(response.get("jsEventListenersEnd")),
            tab_was_active=bool(response.get("tabWasActive")),
            tab_active_after=_optional_bool(response.get("tabActiveAfter")),
            tab_activated_during_sample=bool(response.get("tabActivatedDuringSample")),
            foreground_activation_observed=bool(
                response.get("foregroundActivationObserved")
            ),
            debugger_attached_after=_optional_bool(response.get("debuggerAttachedAfter")),
        )


class BrowserAuthorityLiveCharacterizationRunner:
    """Run one bounded PR8.8 lifecycle/resource experiment.

    Exactly five product writes are budgeted on the happy path. There is no
    runner-level automatic product-write retry. Any failed phase stops later
    writes immediately.
    """

    def __init__(
        self,
        client: Any,
        *,
        provider: BrowserAuthorityCharacterizationProvider | None = None,
        runtime: BrowserOwnedProductWriteRuntime | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.provider = provider or BrowserAuthorityCharacterizationProvider()
        self.runtime = runtime or BrowserOwnedProductWriteRuntime(
            client,
            provider=self.provider,
        )
        self._monotonic = monotonic
        self._sleep = sleep

    def _turn(
        self,
        report: dict[str, Any],
        *,
        phase: str,
        conversation: Any,
        policy: BrowserAuthorityPolicy,
        ttl_ms: int | None,
        timeout: float,
        poll_interval: float,
    ) -> tuple[Any, dict[str, Any]]:
        report["write_attempts"] += 1
        started = self._monotonic()
        execution = self.runtime.send_text_observed(
            LIVE_PROMPTS[phase],
            conversation=conversation,
            timeout=timeout,
            poll_interval=poll_interval,
            browser_authority_policy=policy,
            browser_authority_ttl_ms=ttl_ms,
        )
        total_ms = int(round((self._monotonic() - started) * 1000))
        report["write_completions"] += 1

        observation = execution.observation
        snapshot = self.runtime.lifecycle_snapshot()
        lease = snapshot.get("browser_authority_lease") or {}
        lifecycle = snapshot.get("turn_lifecycle") or {}

        if not observation.write_event_observed:
            raise RuntimeError("LIVE_CHARACTERIZATION_WRITE_EVENT_NOT_OBSERVED")
        if observation.browser_authority_release_proven is not True:
            raise RuntimeError("LIVE_CHARACTERIZATION_AUTHORITY_RELEASE_NOT_PROVEN")
        if lifecycle.get("state") != "FINALIZED":
            raise RuntimeError(
                f"LIVE_CHARACTERIZATION_TURN_NOT_FINALIZED:{lifecycle.get('state')}"
            )

        issued = observation.browser_authority_issued_at_ms
        released = observation.browser_authority_released_at_ms
        lease_duration_ms = (
            released - issued
            if isinstance(issued, int) and isinstance(released, int) and released >= issued
            else None
        )
        write_completed_at = lifecycle.get("write_completed_at_ms")
        terminal_at = lifecycle.get("terminal_at_ms")
        finality_lag_ms = (
            terminal_at - write_completed_at
            if isinstance(write_completed_at, int)
            and isinstance(terminal_at, int)
            and terminal_at >= write_completed_at
            else None
        )

        response = execution.response
        conversation_id = getattr(
            getattr(response, "conversation", None),
            "conversation_id",
            None,
        )
        if not isinstance(conversation_id, str) or not conversation_id:
            raise RuntimeError("LIVE_CHARACTERIZATION_MISSING_CONVERSATION_ID")

        record = {
            "phase": phase,
            "policy": policy.value,
            "ttl_ms": ttl_ms,
            "conversation_id": conversation_id,
            "total_ms": total_ms,
            "write_event_observed": observation.write_event_observed,
            "runtime_tab_id": observation.runtime_tab_id,
            "runtime_tab_preexisting": observation.runtime_tab_preexisting,
            "runtime_tab_created_for_turn": observation.runtime_tab_created_for_turn,
            "foreground_activation_observed": observation.foreground_activation_observed,
            "browser_authority_lease_id": observation.browser_authority_lease_id,
            "browser_authority_generation": observation.browser_authority_generation,
            "browser_authority_release_proven": (
                observation.browser_authority_release_proven
            ),
            "browser_authority_lease_duration_ms": lease_duration_ms,
            "browser_authority_disposal_due_at_ms": (
                observation.browser_authority_disposal_due_at_ms
            ),
            "turn_lifecycle_state_at_write": observation.turn_lifecycle_state_at_write,
            "turn_lifecycle_final_state": lifecycle.get("state"),
            "canonical_finality_lag_ms": finality_lag_ms,
            "pending_disposal_after_return": bool(snapshot.get("pending_disposal")),
            "last_disposal_result_after_return": snapshot.get("last_disposal_result"),
            "lease_state_after_return": lease.get("state"),
        }
        report["turns"].append(record)
        return conversation_id, record

    def _wait_for_disposal(
        self,
        *,
        lease_id: str,
        timeout: float,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("disposal wait timeout must be positive")
        deadline = self._monotonic() + timeout
        last_snapshot: dict[str, Any] | None = None
        while self._monotonic() < deadline:
            snapshot = self.runtime.lifecycle_snapshot()
            last_snapshot = snapshot
            disposal = snapshot.get("last_disposal_result")
            if (
                isinstance(disposal, dict)
                and disposal.get("lease_id") == lease_id
                and disposal.get("status") in {"CLOSED", "ALREADY_ABSENT"}
            ):
                status = self.provider.status()
                return {
                    "confirmed": status.runtime_tab_id is None,
                    "disposal_result": disposal,
                    "runtime_tab_id_after": status.runtime_tab_id,
                }
            self._sleep(0.1)
        return {
            "confirmed": False,
            "disposal_result": (
                last_snapshot.get("last_disposal_result")
                if isinstance(last_snapshot, dict)
                else None
            ),
            "runtime_tab_id_after": self.provider.status().runtime_tab_id,
        }

    @staticmethod
    def _failure_payload(error: BaseException) -> dict[str, Any]:
        payload = {
            "type": type(error).__name__,
            "message": str(error),
            "automatic_retry_attempted": False,
        }
        if isinstance(error, BrowserOwnedWriteRuntimeError):
            payload.update(
                {
                    "failure_kind": error.failure_kind,
                    "write_may_have_been_submitted": error.write_may_have_been_submitted,
                    "reconciliation_required": error.reconciliation_required,
                    "automatic_retry_allowed": error.automatic_retry_allowed,
                    "manual_retry_safe_after_repair": error.manual_retry_safe_after_repair,
                }
            )
        return payload

    def run(
        self,
        *,
        acknowledge_live_writes: bool,
        conversation: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        idle_sample_ms: int = DEFAULT_IDLE_SAMPLE_MS,
        idle_ttl_ms: int = DEFAULT_IDLE_TTL_MS,
        disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
    ) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError(
                "PR8.8 live characterization performs five real product writes; "
                "set acknowledge_live_writes=True"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if isinstance(idle_ttl_ms, bool) or not isinstance(idle_ttl_ms, int):
            raise TypeError("idle_ttl_ms must be an int")
        if idle_ttl_ms <= 0:
            raise ValueError("idle_ttl_ms must be > 0")
        if isinstance(idle_sample_ms, bool) or not isinstance(idle_sample_ms, int):
            raise TypeError("idle_sample_ms must be an int")
        if idle_sample_ms < 1_000 or idle_sample_ms > 15_000:
            raise ValueError("idle_sample_ms must be between 1000 and 15000")

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "browser_authority_live_characterization",
            "acknowledged_live_writes": True,
            "automatic_write_retry": False,
            "write_budget": 5,
            "write_attempts": 0,
            "write_completions": 0,
            "turns": [],
            "resource_sample": None,
            "turn_scoped_disposal": None,
            "idle_ttl_disposal": None,
            "failure_phase": None,
            "failure": None,
        }

        phase = "extension_preflight"
        try:
            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported or not support.resource_sampling_supported:
                raise RuntimeError("PR8_8_CHARACTERIZATION_EXTENSION_RELOAD_REQUIRED")
            if not support.runtime_tab_release_supported:
                raise RuntimeError("PR8_8_RUNTIME_TAB_RELEASE_NOT_AVAILABLE")
            report["initial_runtime_tab_id"] = support.runtime_tab_id
            report["initial_runtime_tab_present"] = support.runtime_tab_id is not None

            phase = "persistent_initial"
            conversation_id, first = self._turn(
                report,
                phase=phase,
                conversation=conversation,
                policy=BrowserAuthorityPolicy.PERSISTENT,
                ttl_ms=None,
                timeout=timeout,
                poll_interval=poll_interval,
            )

            phase = "persistent_warm"
            conversation_id, warm = self._turn(
                report,
                phase=phase,
                conversation=conversation_id,
                policy=BrowserAuthorityPolicy.PERSISTENT,
                ttl_ms=None,
                timeout=timeout,
                poll_interval=poll_interval,
            )

            phase = "idle_resource_sample"
            sample = self.provider.sample_runtime_tab_resources(
                sample_ms=idle_sample_ms,
            )
            if sample.debugger_attached_after is True:
                raise RuntimeError("PR8_8_RESOURCE_SAMPLE_DEBUGGER_LEAK")
            report["resource_sample"] = sample.to_dict()

            phase = "turn_scoped_close"
            conversation_id, turn_scoped = self._turn(
                report,
                phase=phase,
                conversation=conversation_id,
                policy=BrowserAuthorityPolicy.TURN_SCOPED,
                ttl_ms=0,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            lease_id = turn_scoped.get("browser_authority_lease_id")
            if not isinstance(lease_id, str) or not lease_id:
                raise RuntimeError("PR8_8_TURN_SCOPED_MISSING_LEASE_ID")

            phase = "turn_scoped_disposal_wait"
            turn_scoped_disposal = self._wait_for_disposal(
                lease_id=lease_id,
                timeout=disposal_wait_timeout,
            )
            report["turn_scoped_disposal"] = turn_scoped_disposal
            if turn_scoped_disposal.get("confirmed") is not True:
                raise RuntimeError("PR8_8_TURN_SCOPED_CLOSE_NOT_CONFIRMED")

            phase = "post_close_recreation"
            recreation_started = self._monotonic()
            conversation_id, recreated = self._turn(
                report,
                phase=phase,
                conversation=conversation_id,
                policy=BrowserAuthorityPolicy.PERSISTENT,
                ttl_ms=None,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            recreated["close_to_next_turn_return_ms"] = int(
                round((self._monotonic() - recreation_started) * 1000)
            )
            if recreated.get("runtime_tab_created_for_turn") is not True:
                raise RuntimeError("PR8_8_POST_CLOSE_RUNTIME_TAB_NOT_RECREATED")

            phase = "idle_ttl_close"
            conversation_id, idle_ttl = self._turn(
                report,
                phase=phase,
                conversation=conversation_id,
                policy=BrowserAuthorityPolicy.IDLE_TTL,
                ttl_ms=idle_ttl_ms,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            idle_lease_id = idle_ttl.get("browser_authority_lease_id")
            if not isinstance(idle_lease_id, str) or not idle_lease_id:
                raise RuntimeError("PR8_8_IDLE_TTL_MISSING_LEASE_ID")

            phase = "idle_ttl_disposal_wait"
            idle_ttl_wait = max(
                disposal_wait_timeout,
                idle_ttl_ms / 1000.0 + 5.0,
            )
            idle_ttl_disposal = self._wait_for_disposal(
                lease_id=idle_lease_id,
                timeout=idle_ttl_wait,
            )
            report["idle_ttl_disposal"] = idle_ttl_disposal
            if idle_ttl_disposal.get("confirmed") is not True:
                raise RuntimeError("PR8_8_IDLE_TTL_CLOSE_NOT_CONFIRMED")

            phase = "summary"
            turn_records = {turn["phase"]: turn for turn in report["turns"]}
            lease_durations = [
                turn["browser_authority_lease_duration_ms"]
                for turn in report["turns"]
                if isinstance(turn.get("browser_authority_lease_duration_ms"), int)
            ]
            foreground_values = [
                turn.get("foreground_activation_observed") is True
                for turn in report["turns"]
            ]
            resource_foreground = bool(
                report["resource_sample"].get("foreground_activation_observed")
            )
            report["summary"] = {
                "initial_cold_start_observed": (
                    report["initial_runtime_tab_present"] is False
                    and first.get("runtime_tab_created_for_turn") is True
                ),
                "warm_reuse_observed": warm.get("runtime_tab_preexisting") is True,
                "warm_reuse_turn_total_ms": warm.get("total_ms"),
                "post_close_cold_recreation_turn_total_ms": turn_records[
                    "post_close_recreation"
                ].get("total_ms"),
                "turn_scoped_close_confirmed": True,
                "idle_ttl_close_confirmed": True,
                "canonical_finality_preserved_after_turn_scoped_close": (
                    turn_records["turn_scoped_close"].get(
                        "turn_lifecycle_final_state"
                    )
                    == "FINALIZED"
                ),
                "next_turn_after_close_succeeded": True,
                "browser_authority_lease_duration_ms_min": (
                    min(lease_durations) if lease_durations else None
                ),
                "browser_authority_lease_duration_ms_max": (
                    max(lease_durations) if lease_durations else None
                ),
                "idle_main_thread_task_time_fraction": report["resource_sample"].get(
                    "task_time_fraction"
                ),
                "idle_js_heap_used_max_bytes": report["resource_sample"].get(
                    "js_heap_used_max_bytes"
                ),
                "foreground_disturbance_observed": (
                    any(foreground_values) or resource_foreground
                ),
                "write_budget_respected": report["write_attempts"] <= report["write_budget"],
            }
            report["final_conversation_id"] = conversation_id
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = self._failure_payload(error)
            return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR8.8 bounded live Browser Authority Lease / TTL-disposal characterization"
        )
    )
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--idle-sample-ms", type=int, default=DEFAULT_IDLE_SAMPLE_MS)
    parser.add_argument("--idle-ttl-ms", type=int, default=DEFAULT_IDLE_TTL_MS)
    parser.add_argument(
        "--disposal-wait-timeout",
        type=float,
        default=DEFAULT_DISPOSAL_WAIT_SECONDS,
    )
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required: the runner performs up to five real ChatGPT product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required because this runner performs "
            "up to five real product writes"
        )

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = BrowserAuthorityCharacterizationProvider()
    runner = BrowserAuthorityLiveCharacterizationRunner(
        client,
        provider=provider,
    )
    report = runner.run(
        acknowledge_live_writes=True,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        idle_sample_ms=args.idle_sample_ms,
        idle_ttl_ms=args.idle_ttl_ms,
        disposal_wait_timeout=args.disposal_wait_timeout,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
