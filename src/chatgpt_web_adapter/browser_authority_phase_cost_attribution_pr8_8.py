from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .browser_authority_policy_replication_pr8_8 import (
    _conversation_id,
    _observation_record,
    _provenance_record,
)
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_REPLICATIONS = 3
DEFAULT_DISPOSAL_WAIT_SECONDS = 15.0
DEFAULT_CLOSED_STABILITY_MS = 1000
PHASE_SCHEMA = 1
PHASE_KEYS = (
    "runtime_tab_first_resolve_ms",
    "runtime_tab_resolve_total_ms",
    "page_turn_elapsed_ms",
    "tab_ready_to_write_delegated_ms",
    "write_delegated_to_network_complete_ms",
    "network_complete_to_native_complete_ms",
    "write_delegated_to_native_complete_ms",
    "native_turn_elapsed_ms",
    "other_native_overhead_ms",
)


def _prompt(cycle: int, phase: str) -> str:
    return f"Reply with exactly: SDK_PR8_8_PHASE_COST_{cycle:02d}_{phase.upper()}_OK"


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _stats(values) -> dict[str, Any]:
    values = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


class BrowserAuthorityPhaseTimingProvider(BrowserAuthorityCharacterizationProvider):
    """Read-only phase timing queries; product writes still use the proven provider path."""

    def phase_timing_support(self) -> dict[str, Any]:
        response = self._characterization_rpc(
            {"characterizeBrowserAuthorityPhaseTimingSupport": True, "timeoutMs": 3000},
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "phase_timing_supported": response.get("phaseTimingSupported") is True,
            "phase_timing_schema_version": _int(response.get("phaseTimingSchemaVersion")),
        }

    def phase_timing_for_lease(self, lease_id: str) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        lease_id = lease_id.strip()
        response = self._characterization_rpc(
            {
                "characterizeBrowserAuthorityPhaseTiming": True,
                "expectedBrowserAuthorityLeaseId": lease_id,
                "timeoutMs": 3000,
            },
            timeout=max(1.0, self.connect_timeout),
        )
        if response.get("phaseTimingSupported") is not True:
            raise RequestError("PR8_8_PHASE_TIMING_NOT_SUPPORTED", request_stage="browser_authority_phase_timing")
        if response.get("phaseTimingLeaseId") != lease_id:
            raise RequestError("PR8_8_PHASE_TIMING_LEASE_MISMATCH", request_stage="browser_authority_phase_timing")
        if _int(response.get("phaseTimingSchemaVersion")) != PHASE_SCHEMA:
            raise RequestError("PR8_8_PHASE_TIMING_SCHEMA_MISMATCH", request_stage="browser_authority_phase_timing")

        mapping = {
            "runtime_tab_resolve_call_count": "runtimeTabResolveCallCount",
            "runtime_tab_first_resolve_ms": "runtimeTabFirstResolveMs",
            "runtime_tab_resolve_total_ms": "runtimeTabResolveTotalMs",
            "runtime_tab_resolve_max_ms": "runtimeTabResolveMaxMs",
            "page_turn_elapsed_ms": "pageTurnElapsedMs",
            "tab_ready_to_write_delegated_ms": "tabReadyToWriteDelegatedMs",
            "write_delegated_to_network_complete_ms": "writeDelegatedToNetworkCompleteMs",
            "network_complete_to_native_complete_ms": "networkCompleteToNativeCompleteMs",
            "write_delegated_to_native_complete_ms": "writeDelegatedToNativeCompleteMs",
            "native_turn_elapsed_ms": "nativeTurnElapsedMs",
            "other_native_overhead_ms": "otherNativeOverheadMs",
        }
        record = {"phase_timing_lease_id": lease_id, "phase_timing_schema_version": PHASE_SCHEMA}
        for out_name, wire_name in mapping.items():
            value = _int(response.get(wire_name))
            if value is None:
                raise RequestError(f"PR8_8_PHASE_TIMING_MISSING:{wire_name}", request_stage="browser_authority_phase_timing")
            record[out_name] = value
        reloaded = response.get("runtimeReloaded")
        if not isinstance(reloaded, bool):
            raise RequestError("PR8_8_PHASE_TIMING_MISSING:runtimeReloaded", request_stage="browser_authority_phase_timing")
        record["runtime_reloaded"] = reloaded
        record["runtime_reload_ms"] = _int(response.get("runtimeReloadMs"))
        return record


class BrowserAuthorityPhaseCostAttributionRunner:
    def __init__(
        self,
        runtime: Any,
        *,
        provider: BrowserAuthorityPhaseTimingProvider,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.runtime = runtime
        self.provider = provider
        self._monotonic = monotonic
        self._sleep = sleep

    @staticmethod
    def _failure(error: BaseException) -> dict[str, Any]:
        payload = {
            "type": type(error).__name__,
            "message": str(error),
            "automatic_retry_attempted": False,
        }
        for name in (
            "failure_kind",
            "write_may_have_been_submitted",
            "reconciliation_required",
            "automatic_retry_allowed",
            "manual_retry_safe_after_repair",
            "request_stage",
        ):
            if hasattr(error, name):
                payload[name] = getattr(error, name)
        return payload

    def _wait_absent(self, timeout: float) -> dict[str, Any]:
        started = self._monotonic()
        deadline = started + timeout
        samples = 0
        while self._monotonic() < deadline:
            status = self.provider.status()
            samples += 1
            if status.available and status.extension_connected and status.runtime_tab_id is None:
                return {
                    "confirmed": True,
                    "runtime_tab_id_after": None,
                    "observed_wait_ms": round((self._monotonic() - started) * 1000),
                    "samples": samples,
                }
            self._sleep(0.1)
        status = self.provider.status()
        return {
            "confirmed": False,
            "runtime_tab_id_after": status.runtime_tab_id,
            "observed_wait_ms": round((self._monotonic() - started) * 1000),
            "samples": samples + 1,
        }

    def _closed_window(self, duration_ms: int) -> dict[str, Any]:
        started = self._monotonic()
        deadline = started + duration_ms / 1000
        samples = 0
        while self._monotonic() < deadline:
            status = self.provider.status()
            samples += 1
            if not status.available or not status.extension_connected or status.runtime_tab_id is not None:
                return {
                    "confirmed": False,
                    "runtime_tab_id_after": status.runtime_tab_id,
                    "observed_window_ms": round((self._monotonic() - started) * 1000),
                    "samples": samples,
                }
            self._sleep(0.1)
        status = self.provider.status()
        return {
            "confirmed": status.available and status.extension_connected and status.runtime_tab_id is None,
            "runtime_tab_id_after": status.runtime_tab_id,
            "observed_window_ms": round((self._monotonic() - started) * 1000),
            "samples": samples + 1,
        }

    @staticmethod
    def _validate_timing(t: dict[str, Any], phase: str) -> None:
        for key in PHASE_KEYS:
            if not isinstance(t.get(key), int) or isinstance(t.get(key), bool):
                raise RuntimeError(f"{phase}:PHASE_TIMING_NON_INTEGER:{key}")
            if key != "other_native_overhead_ms" and t[key] < 0:
                raise RuntimeError(f"{phase}:PHASE_TIMING_NEGATIVE:{key}")
        calls = t.get("runtime_tab_resolve_call_count")
        if not isinstance(calls, int) or calls < 1:
            raise RuntimeError(f"{phase}:RUNTIME_TAB_RESOLVE_CALL_COUNT_INVALID")
        if t["runtime_tab_first_resolve_ms"] > t["runtime_tab_resolve_total_ms"]:
            raise RuntimeError(f"{phase}:FIRST_RESOLVE_EXCEEDS_TOTAL")
        if abs(
            t["tab_ready_to_write_delegated_ms"]
            + t["write_delegated_to_native_complete_ms"]
            - t["page_turn_elapsed_ms"]
        ) > 5:
            raise RuntimeError(f"{phase}:PAGE_PHASES_DO_NOT_SUM")
        if abs(
            t["write_delegated_to_network_complete_ms"]
            + t["network_complete_to_native_complete_ms"]
            - t["write_delegated_to_native_complete_ms"]
        ) > 5:
            raise RuntimeError(f"{phase}:NETWORK_PHASES_DO_NOT_SUM")
        if t["runtime_reloaded"] and t["runtime_reload_ms"] is None:
            raise RuntimeError(f"{phase}:RUNTIME_RELOAD_TIMING_MISSING")
        if not t["runtime_reloaded"] and t["runtime_reload_ms"] is not None:
            raise RuntimeError(f"{phase}:UNEXPECTED_RUNTIME_RELOAD_TIMING")
        accounted = (
            t["runtime_tab_resolve_total_ms"]
            + t["page_turn_elapsed_ms"]
            + (t["runtime_reload_ms"] or 0)
        )
        if t["native_turn_elapsed_ms"] + 10 < accounted:
            raise RuntimeError(f"{phase}:NATIVE_PHASE_ACCOUNTING_OVERFLOW")

    def _turn(
        self,
        report: dict[str, Any],
        *,
        cycle: int,
        phase: str,
        conversation: str,
        timeout: float,
        poll_interval: float,
        policy: str | None = None,
        ttl_ms: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        report["write_attempts"] += 1
        started = self._monotonic()
        kwargs = {
            "conversation": conversation,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "conversation_mode": "normal",
        }
        if policy is not None:
            kwargs["browser_authority_policy"] = policy
        if ttl_ms is not None:
            kwargs["browser_authority_ttl_ms"] = ttl_ms
        execution = self.runtime.send_text_observed(_prompt(cycle, phase), **kwargs)
        returned_at_ms = round(self._monotonic() * 1000)
        report["write_completions"] += 1
        observation = _observation_record(execution)
        lease_id = observation.get("browser_authority_lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise RuntimeError(f"PR8_8_PHASE_COST_{phase.upper()}:LEASE_ID_MISSING")
        timing = self.provider.phase_timing_for_lease(lease_id)
        self._validate_timing(timing, f"PR8_8_PHASE_COST_{phase.upper()}")
        released_at = _int(observation.get("browser_authority_released_at_ms"))
        return _conversation_id(execution), {
            "cycle": cycle,
            "phase": phase,
            "total_ms": round((self._monotonic() - started) * 1000),
            "conversation_id": _conversation_id(execution),
            "provenance": _provenance_record(execution),
            "observation": observation,
            "phase_timing": timing,
            "post_release_canonical_return_ms": (
                returned_at_ms - released_at
                if released_at is not None and returned_at_ms >= released_at
                else None
            ),
        }

    @staticmethod
    def _persistent(record: dict[str, Any], *, created: bool, preexisting: bool, phase: str) -> int:
        o = record["observation"]
        if o["browser_authority_policy"] != "PERSISTENT" or o["browser_authority_ttl_ms"] is not None:
            raise RuntimeError(f"{phase}:PERSISTENT_NOT_OBSERVED")
        if o["browser_authority_disposal_action"] != "KEEP":
            raise RuntimeError(f"{phase}:PERSISTENT_NOT_KEPT")
        if o["runtime_tab_created_for_turn"] is not created or o["runtime_tab_preexisting"] is not preexisting:
            raise RuntimeError(f"{phase}:RUNTIME_TAB_STATE_MISMATCH")
        tab_id = o["runtime_tab_id"]
        if not isinstance(tab_id, int) or isinstance(tab_id, bool):
            raise RuntimeError(f"{phase}:RUNTIME_TAB_ID_MISSING")
        return tab_id

    @staticmethod
    def _close(record: dict[str, Any], tab_id: int, phase: str) -> None:
        o = record["observation"]
        if o["runtime_tab_id"] != tab_id or o["runtime_tab_preexisting"] is not True or o["runtime_tab_created_for_turn"] is not False:
            raise RuntimeError(f"{phase}:CLOSE_RUNTIME_TAB_MISMATCH")
        if o["browser_authority_policy"] != "TURN_SCOPED" or o["browser_authority_ttl_ms"] != 0:
            raise RuntimeError(f"{phase}:TURN_SCOPED_NOT_OBSERVED")
        if o["browser_authority_disposal_action"] != "CLOSE":
            raise RuntimeError(f"{phase}:CLOSE_NOT_ARMED")

    @staticmethod
    def _phase_summary(cycles: list[dict[str, Any]]) -> dict[str, Any]:
        pairs = []
        for cycle in cycles:
            cold = cycle["cold_turn"]
            warm = cycle["warm_turn"]
            pair = {"cycle": cycle["cycle"]}
            for key in PHASE_KEYS:
                c, w = cold["phase_timing"][key], warm["phase_timing"][key]
                pair[f"cold_{key}"] = c
                pair[f"warm_{key}"] = w
                pair[f"cold_minus_warm_{key}"] = c - w
            pair["cold_post_release_canonical_return_ms"] = cold["post_release_canonical_return_ms"]
            pair["warm_post_release_canonical_return_ms"] = warm["post_release_canonical_return_ms"]
            pairs.append(pair)
        distributions = {
            key: {
                "cold": _stats(p[f"cold_{key}"] for p in pairs),
                "warm": _stats(p[f"warm_{key}"] for p in pairs),
                "cold_minus_warm": _stats(p[f"cold_minus_warm_{key}"] for p in pairs),
            }
            for key in PHASE_KEYS
        }
        distributions["post_release_canonical_return_ms"] = {
            "cold": _stats(p["cold_post_release_canonical_return_ms"] for p in pairs),
            "warm": _stats(p["warm_post_release_canonical_return_ms"] for p in pairs),
        }
        return {
            "pairs": pairs,
            "distributions": distributions,
            "cold_recreation_metric": "runtime_tab_first_resolve_ms",
            "cold_recreation_metric_scope": (
                "first ensureRuntimeTab call for one fixed completed durable conversation; "
                "cold includes create/load, warm includes live-tab lookup"
            ),
            "interpretation": "descriptive_only_no_policy_threshold_applied",
        }

    def run(
        self,
        *,
        acknowledge_live_writes: bool,
        conversation: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        replications: int = DEFAULT_REPLICATIONS,
        disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
        closed_stability_ms: int = DEFAULT_CLOSED_STABILITY_MS,
    ) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError("PR8.8 phase-cost attribution performs real product writes")
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required for fixed-conversation phase attribution")
        conversation = conversation.strip()
        if replications < 2 or replications > 5:
            raise ValueError("replications must be between 2 and 5")
        if timeout <= 0 or poll_interval <= 0 or disposal_wait_timeout <= 0:
            raise ValueError("timeouts and poll_interval must be positive")
        if closed_stability_ms < 200 or closed_stability_ms > 5000:
            raise ValueError("closed_stability_ms must be between 200 and 5000")

        report = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "browser_authority_phase_level_cost_attribution",
            "runtime_surface": "ChatGPTProductRuntime",
            "automatic_write_retry": False,
            "conversation": conversation,
            "replications_requested": replications,
            "write_budget": replications * 3,
            "write_attempts": 0,
            "write_completions": 0,
            "cycles": [],
            "failure_phase": None,
            "failure": None,
        }
        phase = "phase_cost_preflight"
        try:
            try:
                timing_support = self.provider.phase_timing_support()
            except Exception as error:
                raise RuntimeError("PR8_8_PHASE_COST_EXTENSION_RELOAD_REQUIRED_BEFORE_WRITES") from error
            report["phase_timing_support"] = timing_support
            if timing_support["phase_timing_supported"] is not True or timing_support["phase_timing_schema_version"] != PHASE_SCHEMA:
                raise RuntimeError("PR8_8_PHASE_COST_EXTENSION_RELOAD_REQUIRED_BEFORE_WRITES")

            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported or not support.runtime_tab_release_supported:
                raise RuntimeError("PR8_8_PHASE_COST_EXTENSION_SUPPORT_NOT_AVAILABLE")
            if support.runtime_tab_id is not None:
                raise RuntimeError("PR8_8_PHASE_COST_INITIAL_RUNTIME_TAB_MUST_BE_ABSENT")

            health = self.runtime.health(conversation)
            report["runtime_health"] = health.to_dict()
            if health.ready is not True or health.canonical_status != "completed":
                raise RuntimeError("PR8_8_PHASE_COST_FIXED_CONVERSATION_NOT_READY")

            governance = dict(self.runtime.governance())
            report["runtime_governance"] = {
                key: governance.get(key)
                for key in (
                    "transport",
                    "automatic_write_retry",
                    "canonical_readback_required",
                    "browser_authority_effective_runtime_default_policy",
                    "browser_authority_effective_runtime_default_ttl_ms",
                    "browser_authority_policy_contract_scope",
                    "temporary_mode_production_enabled",
                )
            }
            if governance.get("automatic_write_retry") is not False or governance.get("canonical_readback_required") is not True:
                raise RuntimeError("PR8_8_PHASE_COST_RUNTIME_GOVERNANCE_CHANGED")
            if governance.get("browser_authority_effective_runtime_default_policy") != "PERSISTENT":
                raise RuntimeError("PR8_8_PHASE_COST_DEFAULT_POLICY_NOT_PERSISTENT")
            if governance.get("browser_authority_effective_runtime_default_ttl_ms") is not None:
                raise RuntimeError("PR8_8_PHASE_COST_PERSISTENT_DEFAULT_HAS_TTL")
            if governance.get("browser_authority_policy_contract_scope") != "RESOURCE_LIFECYCLE_ONLY":
                raise RuntimeError("PR8_8_PHASE_COST_POLICY_SCOPE_CHANGED")
            if governance.get("temporary_mode_production_enabled") is not False:
                raise RuntimeError("PR8_8_PHASE_COST_TEMPORARY_BOUNDARY_CHANGED")

            for n in range(1, replications + 1):
                cycle = {"cycle": n, "cold_turn": None, "warm_turn": None, "close_turn": None, "close_disposal": None, "closed_window": None}
                report["cycles"].append(cycle)

                phase = f"cycle_{n:02d}_cold_persistent_send"
                cid, cold = self._turn(report, cycle=n, phase="cold", conversation=conversation, timeout=timeout, poll_interval=poll_interval)
                cycle["cold_turn"] = cold
                cold_tab = self._persistent(cold, created=True, preexisting=False, phase=f"PR8_8_PHASE_COST_{n:02d}_COLD")
                if cid != conversation:
                    raise RuntimeError(f"PR8_8_PHASE_COST_{n:02d}:CONVERSATION_CHANGED_ON_COLD")

                phase = f"cycle_{n:02d}_warm_persistent_send"
                cid, warm = self._turn(report, cycle=n, phase="warm", conversation=conversation, timeout=timeout, poll_interval=poll_interval)
                cycle["warm_turn"] = warm
                warm_tab = self._persistent(warm, created=False, preexisting=True, phase=f"PR8_8_PHASE_COST_{n:02d}_WARM")
                if cid != conversation or warm_tab != cold_tab:
                    raise RuntimeError(f"PR8_8_PHASE_COST_{n:02d}:WARM_REUSE_FAILED")

                phase = f"cycle_{n:02d}_turn_scoped_close_send"
                cid, close = self._turn(
                    report,
                    cycle=n,
                    phase="close",
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    policy="TURN_SCOPED",
                    ttl_ms=0,
                )
                cycle["close_turn"] = close
                self._close(close, warm_tab, f"PR8_8_PHASE_COST_{n:02d}")
                if cid != conversation:
                    raise RuntimeError(f"PR8_8_PHASE_COST_{n:02d}:CONVERSATION_CHANGED_ON_CLOSE")

                phase = f"cycle_{n:02d}_close_disposal_wait"
                cycle["close_disposal"] = self._wait_absent(disposal_wait_timeout)
                if cycle["close_disposal"]["confirmed"] is not True:
                    raise RuntimeError(f"PR8_8_PHASE_COST_{n:02d}:CLOSE_NOT_CONFIRMED")

                phase = f"cycle_{n:02d}_closed_stability_window"
                cycle["closed_window"] = self._closed_window(closed_stability_ms)
                if cycle["closed_window"]["confirmed"] is not True:
                    raise RuntimeError(f"PR8_8_PHASE_COST_{n:02d}:CLOSED_WINDOW_NOT_STABLE")

            phase = "phase_cost_summary"
            records = [c[k] for c in report["cycles"] for k in ("cold_turn", "warm_turn", "close_turn")]
            lease_ids = [r["observation"]["browser_authority_lease_id"] for r in records]
            generations = [r["observation"]["browser_authority_generation"] for r in records]
            if len(set(lease_ids)) != len(lease_ids):
                raise RuntimeError("PR8_8_PHASE_COST_LEASE_IDS_NOT_UNIQUE")
            if not all(b > a for a, b in zip(generations, generations[1:])):
                raise RuntimeError("PR8_8_PHASE_COST_GENERATIONS_NOT_STRICT")

            final_status = self.provider.status()
            report["final_runtime_status"] = {
                "bridge_available": final_status.available,
                "extension_connected": final_status.extension_connected,
                "runtime_tab_id": final_status.runtime_tab_id,
            }
            if final_status.runtime_tab_id is not None:
                raise RuntimeError("PR8_8_PHASE_COST_FINAL_RUNTIME_TAB_NOT_CLOSED")

            phase_summary = self._phase_summary(report["cycles"])
            report["phase_cost_characterization"] = phase_summary
            report["policy_decision_governance"] = {
                "library_default_policy": "PERSISTENT",
                "library_default_change_performed": False,
                "hde_assembly_policy_change_performed": False,
                "phase_cost_threshold_applied": False,
                "cold_recreation_metric": "runtime_tab_first_resolve_ms",
                "cold_recreation_metric_scope": phase_summary["cold_recreation_metric_scope"],
                "decision_scope": "RESOURCE_LIFECYCLE_ONLY",
                "decision_requires_human_review": True,
                "temporary_mode_boundary_preserved": True,
            }
            report["final_conversation_id"] = conversation
            report["summary"] = {
                "phase_level_attribution_completed": True,
                "replication_count": replications,
                "cold_recreation_acquisition_isolated": True,
                "all_phase_records_fenced_by_lease_id": True,
                "all_cold_turns_created_new_runtime_tab": True,
                "all_warm_turns_reused_same_runtime_tab": True,
                "all_close_turns_reused_then_closed_runtime_tab": True,
                "all_closed_windows_stable": True,
                "same_completed_conversation_used_for_every_pair": True,
                "canonical_finality_preserved_across_all_writes": True,
                "policy_decision_is_evidence_only": True,
                "default_policy_change_performed": False,
                "write_budget_respected": report["write_attempts"] <= report["write_budget"],
                "automatic_write_retry_attempted": False,
            }
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = self._failure(error)
            return report


def main() -> int:
    parser = argparse.ArgumentParser(description="PR8.8 Browser Authority phase-level cost attribution")
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    parser.add_argument("--disposal-wait-timeout", type=float, default=DEFAULT_DISPOSAL_WAIT_SECONDS)
    parser.add_argument("--closed-stability-ms", type=int, default=DEFAULT_CLOSED_STABILITY_MS)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required because this runner performs real ChatGPT product writes")

    client = ChatGPTWebClient(auth_file=args.auth_file, auto_refresh_auth=True, auto_login=False, auto_sentinel=False)
    provider = BrowserAuthorityPhaseTimingProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = BrowserAuthorityPhaseCostAttributionRunner(runtime, provider=provider).run(
        acknowledge_live_writes=True,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        replications=args.replications,
        disposal_wait_timeout=args.disposal_wait_timeout,
        closed_stability_ms=args.closed_stability_ms,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
