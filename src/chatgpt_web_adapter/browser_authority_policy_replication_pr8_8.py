from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .client import ChatGPTWebClient
from .product_runtime import ChatGPTProductRuntime, assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_REPLICATIONS = 3
MIN_REPLICATIONS = 2
MAX_REPLICATIONS = 5
DEFAULT_RESOURCE_SAMPLE_MS = 3_000
DEFAULT_DISPOSAL_WAIT_SECONDS = 15.0
DEFAULT_CLOSED_STABILITY_MS = 1_000


def _prompt(cycle: int, phase: str) -> str:
    token = f"SDK_PR8_8_REPLICATION_{cycle:02d}_{phase.upper()}_OK"
    return f"Reply with exactly: {token}"


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _conversation_id(execution: Any) -> str:
    response = getattr(execution, "response", None)
    conversation = getattr(response, "conversation", None)
    value = getattr(conversation, "conversation_id", None)
    if not isinstance(value, str) or not value:
        raise RuntimeError("PR8_8_REPLICATION_MISSING_CONVERSATION_ID")
    return value


def _provenance_record(execution: Any) -> dict[str, Any]:
    provenance = getattr(execution, "provenance", None)
    if provenance is None:
        raise RuntimeError("PR8_8_REPLICATION_PROVENANCE_MISSING")
    completion = getattr(provenance, "completion", None)
    if getattr(completion, "completed", None) is not True:
        raise RuntimeError("PR8_8_REPLICATION_COMPLETION_NOT_PROVEN")
    if getattr(completion, "canonical_completion_proven", None) is not True:
        raise RuntimeError("PR8_8_REPLICATION_CANONICAL_FINALITY_NOT_PROVEN")
    conversation_mode = getattr(provenance, "conversation_mode", None)
    requested_mode = _enum_value(getattr(conversation_mode, "requested_conversation_mode", None))
    observed_mode = _enum_value(getattr(conversation_mode, "observed_conversation_mode", None))
    observed_mode_proven = getattr(conversation_mode, "observed_mode_proven", None)
    if requested_mode != "NORMAL" or observed_mode != "NORMAL" or observed_mode_proven is not True:
        raise RuntimeError("PR8_8_REPLICATION_NORMAL_MODE_NOT_PROVEN")
    return {
        "canonical_completion_proven": True,
        "requested_conversation_mode": requested_mode,
        "observed_conversation_mode": observed_mode,
        "observed_mode_proven": True,
        "transport": getattr(provenance, "transport", None),
        "product_semantics": getattr(provenance, "product_semantics", None),
    }


def _observation_record(execution: Any) -> dict[str, Any]:
    observation = getattr(execution, "observation", None)
    if observation is None or getattr(observation, "write_event_observed", None) is not True:
        raise RuntimeError("PR8_8_REPLICATION_WRITE_EVENT_NOT_OBSERVED")
    if getattr(observation, "browser_authority_release_proven", None) is not True:
        raise RuntimeError("PR8_8_REPLICATION_AUTHORITY_RELEASE_NOT_PROVEN")
    names = (
        "runtime_tab_id", "runtime_tab_preexisting", "runtime_tab_created_for_turn",
        "foreground_activation_observed", "browser_authority_lease_id",
        "browser_authority_generation", "browser_authority_policy",
        "browser_authority_ttl_ms", "browser_authority_issued_at_ms",
        "browser_authority_released_at_ms", "browser_authority_disposal_due_at_ms",
        "browser_authority_disposal_action", "turn_lifecycle_id",
        "turn_lifecycle_state_at_write",
    )
    payload = {name: getattr(observation, name, None) for name in names}
    payload["write_event_observed"] = True
    payload["browser_authority_release_proven"] = True
    return payload


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int_metric(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _stats(values: Iterable[int | float | None]) -> dict[str, Any]:
    cleaned = [float(value) for value in values if _numeric(value) is not None]
    if not cleaned:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(cleaned),
        "min": min(cleaned),
        "max": max(cleaned),
        "mean": statistics.fmean(cleaned),
        "median": statistics.median(cleaned),
    }


def _foreground_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [record["observation"].get("foreground_activation_observed") for record in records]
    true_count = sum(value is True for value in values)
    false_count = sum(value is False for value in values)
    unknown_count = len(values) - true_count - false_count
    known = true_count + false_count
    return {
        "turn_count": len(values),
        "observed_true": true_count,
        "observed_false": false_count,
        "unknown": unknown_count,
        "activation_rate_among_known": true_count / known if known else None,
    }


def _resource_record(sample: Any) -> dict[str, Any]:
    to_dict = getattr(sample, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    names = (
        "runtime_tab_id", "requested_sample_ms", "observed_sample_ms",
        "task_duration_start_s", "task_duration_end_s", "task_duration_delta_s",
        "task_time_fraction", "js_heap_used_start_bytes", "js_heap_used_end_bytes",
        "js_heap_used_max_bytes", "js_heap_total_start_bytes", "js_heap_total_end_bytes",
        "documents_start", "documents_end", "nodes_start", "nodes_end",
        "js_event_listeners_start", "js_event_listeners_end", "tab_was_active",
        "tab_active_after", "tab_activated_during_sample", "foreground_activation_observed",
        "debugger_attached_after",
    )
    return {name: getattr(sample, name, None) for name in names}


class BrowserAuthorityPolicyReplicationRunner:
    """Independent repeated warm-retention/cold-recreation characterization."""

    def __init__(self, runtime: ChatGPTProductRuntime, *, provider: BrowserAuthorityCharacterizationProvider,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.runtime = runtime
        self.provider = provider
        self._monotonic = monotonic
        self._sleep = sleep

    @staticmethod
    def _failure_payload(error: BaseException) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": type(error).__name__, "message": str(error), "automatic_retry_attempted": False}
        for name in ("failure_kind", "write_may_have_been_submitted", "reconciliation_required", "automatic_retry_allowed", "manual_retry_safe_after_repair", "request_stage"):
            if hasattr(error, name):
                payload[name] = getattr(error, name)
        return payload

    def _wait_for_runtime_tab_absence(self, *, timeout: float) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("disposal wait timeout must be positive")
        started = self._monotonic()
        deadline = started + timeout
        samples = 0
        last_status = None
        while self._monotonic() < deadline:
            last_status = self.provider.status()
            samples += 1
            if last_status.available and last_status.extension_connected and last_status.runtime_tab_id is None:
                return {"confirmed": True, "bridge_available": True, "extension_connected": True, "runtime_tab_id_after": None,
                        "observed_wait_ms": int(round((self._monotonic() - started) * 1000)), "samples": samples}
            self._sleep(0.1)
        if last_status is None:
            last_status = self.provider.status()
            samples += 1
        return {"confirmed": False, "bridge_available": bool(getattr(last_status, "available", False)),
                "extension_connected": bool(getattr(last_status, "extension_connected", False)),
                "runtime_tab_id_after": getattr(last_status, "runtime_tab_id", None),
                "observed_wait_ms": int(round((self._monotonic() - started) * 1000)), "samples": samples}

    def _prove_closed_window(self, *, duration_ms: int) -> dict[str, Any]:
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            raise TypeError("closed stability window must be an int")
        if duration_ms <= 0:
            raise ValueError("closed stability window must be positive")
        started = self._monotonic()
        deadline = started + duration_ms / 1000.0
        samples = 0
        last_status = None
        while self._monotonic() < deadline:
            last_status = self.provider.status()
            samples += 1
            if not last_status.available or not last_status.extension_connected or last_status.runtime_tab_id is not None:
                return {"confirmed": False, "requested_window_ms": duration_ms,
                        "observed_window_ms": int(round((self._monotonic() - started) * 1000)), "samples": samples,
                        "bridge_available": bool(getattr(last_status, "available", False)),
                        "extension_connected": bool(getattr(last_status, "extension_connected", False)),
                        "runtime_tab_id_after": getattr(last_status, "runtime_tab_id", None)}
            self._sleep(0.1)
        last_status = self.provider.status()
        samples += 1
        confirmed = last_status.available and last_status.extension_connected and last_status.runtime_tab_id is None
        return {"confirmed": bool(confirmed), "requested_window_ms": duration_ms,
                "observed_window_ms": int(round((self._monotonic() - started) * 1000)), "samples": samples,
                "bridge_available": bool(last_status.available), "extension_connected": bool(last_status.extension_connected),
                "runtime_tab_id_after": last_status.runtime_tab_id}

    def _turn(self, report: dict[str, Any], *, cycle: int, phase: str, conversation: Any,
              timeout: float, poll_interval: float, browser_authority_policy: str | None = None,
              browser_authority_ttl_ms: int | None = None) -> tuple[str, dict[str, Any]]:
        report["write_attempts"] += 1
        started = self._monotonic()
        kwargs: dict[str, Any] = {"conversation": conversation, "timeout": timeout, "poll_interval": poll_interval, "conversation_mode": "normal"}
        if browser_authority_policy is not None:
            kwargs["browser_authority_policy"] = browser_authority_policy
        if browser_authority_ttl_ms is not None:
            kwargs["browser_authority_ttl_ms"] = browser_authority_ttl_ms
        execution = self.runtime.send_text_observed(_prompt(cycle, phase), **kwargs)
        returned_at_ms = int(round(self._monotonic() * 1000))
        total_ms = int(round((self._monotonic() - started) * 1000))
        report["write_completions"] += 1
        conversation_id = _conversation_id(execution)
        provenance = _provenance_record(execution)
        observation = _observation_record(execution)
        issued_at = _int_metric(observation["browser_authority_issued_at_ms"])
        released_at = _int_metric(observation["browser_authority_released_at_ms"])
        lease_duration_ms = released_at - issued_at if issued_at is not None and released_at is not None and released_at >= issued_at else None
        post_release_return_ms = returned_at_ms - released_at if released_at is not None and returned_at_ms >= released_at else None
        return conversation_id, {"cycle": cycle, "phase": phase, "conversation_id": conversation_id,
                                 "total_ms": total_ms, "returned_at_monotonic_ms": returned_at_ms,
                                 "lease_duration_ms": lease_duration_ms,
                                 "post_release_canonical_return_ms": post_release_return_ms,
                                 "provenance": provenance, "observation": observation}

    @staticmethod
    def _validate_persistent_turn(record: dict[str, Any], *, expected_created: bool, expected_preexisting: bool, phase: str) -> int:
        observation = record["observation"]
        if observation["browser_authority_policy"] != "PERSISTENT":
            raise RuntimeError(f"{phase}:PERSISTENT_POLICY_NOT_OBSERVED")
        if observation["browser_authority_ttl_ms"] is not None:
            raise RuntimeError(f"{phase}:PERSISTENT_TTL_PRESENT")
        if observation["browser_authority_disposal_action"] != "KEEP":
            raise RuntimeError(f"{phase}:PERSISTENT_NOT_KEPT")
        if observation["runtime_tab_created_for_turn"] is not expected_created:
            raise RuntimeError(f"{phase}:RUNTIME_TAB_CREATION_STATE_MISMATCH")
        if observation["runtime_tab_preexisting"] is not expected_preexisting:
            raise RuntimeError(f"{phase}:RUNTIME_TAB_PREEXISTING_STATE_MISMATCH")
        tab_id = observation["runtime_tab_id"]
        if not isinstance(tab_id, int) or isinstance(tab_id, bool):
            raise RuntimeError(f"{phase}:RUNTIME_TAB_ID_MISSING")
        return tab_id

    @staticmethod
    def _validate_close_turn(record: dict[str, Any], *, expected_tab_id: int, phase: str) -> None:
        observation = record["observation"]
        if observation["runtime_tab_id"] != expected_tab_id:
            raise RuntimeError(f"{phase}:CLOSE_USED_DIFFERENT_RUNTIME_TAB")
        if observation["runtime_tab_preexisting"] is not True:
            raise RuntimeError(f"{phase}:CLOSE_TAB_NOT_PREEXISTING")
        if observation["runtime_tab_created_for_turn"] is not False:
            raise RuntimeError(f"{phase}:CLOSE_UNEXPECTEDLY_CREATED_TAB")
        if observation["browser_authority_policy"] != "TURN_SCOPED":
            raise RuntimeError(f"{phase}:TURN_SCOPED_POLICY_NOT_OBSERVED")
        if observation["browser_authority_ttl_ms"] != 0:
            raise RuntimeError(f"{phase}:TURN_SCOPED_TTL_NOT_ZERO")
        if observation["browser_authority_disposal_action"] != "CLOSE":
            raise RuntimeError(f"{phase}:TURN_SCOPED_CLOSE_NOT_ARMED")
        released_at = observation["browser_authority_released_at_ms"]
        due_at = observation["browser_authority_disposal_due_at_ms"]
        if not isinstance(released_at, int) or isinstance(released_at, bool) or not isinstance(due_at, int) or isinstance(due_at, bool) or due_at != released_at:
            raise RuntimeError(f"{phase}:TURN_SCOPED_CLOSE_NOT_ANCHORED_TO_RELEASE")

    @staticmethod
    def _validate_resource_sample(sample: dict[str, Any], *, expected_tab_id: int, phase: str) -> None:
        if sample.get("runtime_tab_id") != expected_tab_id:
            raise RuntimeError(f"{phase}:RESOURCE_SAMPLE_RUNTIME_TAB_MISMATCH")
        if sample.get("debugger_attached_after") is True:
            raise RuntimeError(f"{phase}:RESOURCE_SAMPLE_DEBUGGER_LEAK")
        if sample.get("tab_activated_during_sample") is True:
            raise RuntimeError(f"{phase}:RESOURCE_SAMPLE_ACTIVATED_RUNTIME_TAB")

    @staticmethod
    def _build_cost_summary(cycles: list[dict[str, Any]]) -> dict[str, Any]:
        pairs: list[dict[str, Any]] = []
        for cycle in cycles:
            cold, warm = cycle["cold_turn"], cycle["warm_turn"]
            cold_total, warm_total = cold["total_ms"], warm["total_ms"]
            pairs.append({"cycle": cycle["cycle"], "cold_total_ms": cold_total, "warm_total_ms": warm_total,
                          "cold_minus_warm_total_ms": cold_total - warm_total,
                          "cold_over_warm_total_ratio": cold_total / warm_total if warm_total > 0 else None,
                          "cold_lease_duration_ms": cold["lease_duration_ms"], "warm_lease_duration_ms": warm["lease_duration_ms"],
                          "cold_minus_warm_lease_duration_ms": cold["lease_duration_ms"] - warm["lease_duration_ms"] if cold["lease_duration_ms"] is not None and warm["lease_duration_ms"] is not None else None,
                          "cold_post_release_canonical_return_ms": cold["post_release_canonical_return_ms"],
                          "warm_post_release_canonical_return_ms": warm["post_release_canonical_return_ms"]})
        return {"pairs": pairs, "cold_total_ms": _stats(pair["cold_total_ms"] for pair in pairs),
                "warm_total_ms": _stats(pair["warm_total_ms"] for pair in pairs),
                "cold_minus_warm_total_ms": _stats(pair["cold_minus_warm_total_ms"] for pair in pairs),
                "cold_over_warm_total_ratio": _stats(pair["cold_over_warm_total_ratio"] for pair in pairs),
                "cold_lease_duration_ms": _stats(pair["cold_lease_duration_ms"] for pair in pairs),
                "warm_lease_duration_ms": _stats(pair["warm_lease_duration_ms"] for pair in pairs),
                "cold_post_release_canonical_return_ms": _stats(pair["cold_post_release_canonical_return_ms"] for pair in pairs),
                "warm_post_release_canonical_return_ms": _stats(pair["warm_post_release_canonical_return_ms"] for pair in pairs),
                "interpretation": "descriptive_only_no_default_policy_threshold_applied"}

    @staticmethod
    def _build_resource_summary(cycles: list[dict[str, Any]]) -> dict[str, Any]:
        samples = [cycle["retained_resource_sample"] for cycle in cycles]
        return {"sample_count": len(samples),
                "task_time_fraction": _stats(sample.get("task_time_fraction") for sample in samples),
                "js_heap_used_max_bytes": _stats(sample.get("js_heap_used_max_bytes") for sample in samples),
                "documents_end": _stats(sample.get("documents_end") for sample in samples),
                "nodes_end": _stats(sample.get("nodes_end") for sample in samples),
                "js_event_listeners_end": _stats(sample.get("js_event_listeners_end") for sample in samples),
                "sample_tab_activation_count": sum(sample.get("tab_activated_during_sample") is True for sample in samples),
                "sample_foreground_disturbance_count": sum(sample.get("foreground_activation_observed") is True for sample in samples),
                "debugger_leak_count": sum(sample.get("debugger_attached_after") is True for sample in samples),
                "closed_window_count": len(cycles),
                "stable_closed_window_count": sum(cycle["closed_window"].get("confirmed") is True for cycle in cycles),
                "scope_note": "closed windows prove runtime-tab absence only; they do not measure total Chrome process resource use"}

    def run(self, *, acknowledge_live_writes: bool, conversation: Any = None, timeout: float = DEFAULT_TIMEOUT,
            poll_interval: float = DEFAULT_POLL_INTERVAL, replications: int = DEFAULT_REPLICATIONS,
            resource_sample_ms: int = DEFAULT_RESOURCE_SAMPLE_MS,
            disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
            closed_stability_ms: int = DEFAULT_CLOSED_STABILITY_MS) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError("PR8.8 independent replication performs real product writes; set acknowledge_live_writes=True")
        if timeout <= 0: raise ValueError("timeout must be positive")
        if poll_interval <= 0: raise ValueError("poll_interval must be positive")
        if isinstance(replications, bool) or not isinstance(replications, int): raise TypeError("replications must be an int")
        if replications < MIN_REPLICATIONS or replications > MAX_REPLICATIONS: raise ValueError(f"replications must be between {MIN_REPLICATIONS} and {MAX_REPLICATIONS}")
        if isinstance(resource_sample_ms, bool) or not isinstance(resource_sample_ms, int): raise TypeError("resource_sample_ms must be an int")
        if resource_sample_ms < 1_000 or resource_sample_ms > 15_000: raise ValueError("resource_sample_ms must be between 1000 and 15000")
        if disposal_wait_timeout <= 0: raise ValueError("disposal_wait_timeout must be positive")
        if isinstance(closed_stability_ms, bool) or not isinstance(closed_stability_ms, int): raise TypeError("closed_stability_ms must be an int")
        if closed_stability_ms < 200 or closed_stability_ms > 5_000: raise ValueError("closed_stability_ms must be between 200 and 5000")

        report: dict[str, Any] = {"ok": False, "pr": "PR8.8", "probe_context": "independent_browser_authority_policy_replication_warm_vs_cold_resource_governance",
                                  "runtime_surface": "ChatGPTProductRuntime", "acknowledged_live_writes": True, "automatic_write_retry": False,
                                  "replications_requested": replications, "write_budget": replications * 3, "write_attempts": 0, "write_completions": 0,
                                  "resource_sample_ms": resource_sample_ms, "closed_stability_ms": closed_stability_ms,
                                  "initial_conversation_supplied": conversation is not None, "cycles": [], "failure_phase": None, "failure": None}
        phase = "replication_preflight"
        try:
            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported: raise RuntimeError("PR8_8_REPLICATION_EXTENSION_SUPPORT_NOT_AVAILABLE")
            if not support.resource_sampling_supported: raise RuntimeError("PR8_8_REPLICATION_RESOURCE_SAMPLING_NOT_AVAILABLE")
            if not support.runtime_tab_release_supported: raise RuntimeError("PR8_8_REPLICATION_RUNTIME_TAB_RELEASE_NOT_AVAILABLE")
            if support.runtime_tab_id is not None: raise RuntimeError("PR8_8_REPLICATION_INITIAL_RUNTIME_TAB_MUST_BE_ABSENT")
            governance = dict(self.runtime.governance())
            report["runtime_governance"] = {key: governance.get(key) for key in (
                "transport", "automatic_write_retry", "canonical_readback_required", "browser_authority_policy_high_level_surface",
                "browser_authority_selected_transport_policy_support", "browser_authority_effective_runtime_default_policy",
                "browser_authority_effective_runtime_default_ttl_ms", "browser_authority_runtime_default_policy_source",
                "browser_authority_policy_contract_scope", "temporary_mode_production_enabled")}
            if governance.get("automatic_write_retry") is not False: raise RuntimeError("PR8_8_REPLICATION_AUTOMATIC_RETRY_INVARIANT_CHANGED")
            if governance.get("canonical_readback_required") is not True: raise RuntimeError("PR8_8_REPLICATION_CANONICAL_READBACK_NOT_REQUIRED")
            if governance.get("browser_authority_policy_high_level_surface") is not True: raise RuntimeError("PR8_8_REPLICATION_HIGH_LEVEL_POLICY_SURFACE_MISSING")
            if governance.get("browser_authority_selected_transport_policy_support") is not True: raise RuntimeError("PR8_8_REPLICATION_TRANSPORT_POLICY_SUPPORT_MISSING")
            if governance.get("browser_authority_effective_runtime_default_policy") != "PERSISTENT": raise RuntimeError("PR8_8_REPLICATION_DEFAULT_POLICY_NOT_PERSISTENT")
            if governance.get("browser_authority_effective_runtime_default_ttl_ms") is not None: raise RuntimeError("PR8_8_REPLICATION_PERSISTENT_DEFAULT_HAS_TTL")
            if governance.get("browser_authority_runtime_default_policy_source") != "TRANSPORT_DEFAULT": raise RuntimeError("PR8_8_REPLICATION_DEFAULT_POLICY_SOURCE_NOT_TRANSPORT_DEFAULT")
            if governance.get("browser_authority_policy_contract_scope") != "RESOURCE_LIFECYCLE_ONLY": raise RuntimeError("PR8_8_REPLICATION_POLICY_SCOPE_CHANGED")
            if governance.get("temporary_mode_production_enabled") is not False: raise RuntimeError("PR8_8_REPLICATION_TEMPORARY_BOUNDARY_CHANGED")
            report["initial_runtime_tab_id"] = support.runtime_tab_id
            report["initial_lease_id_present"] = support.lease_id_present
            current_conversation = conversation
            first_conversation_id: str | None = None
            for cycle_number in range(1, replications + 1):
                cycle: dict[str, Any] = {"cycle": cycle_number, "cold_turn": None, "warm_turn": None, "retained_resource_sample": None,
                                         "close_turn": None, "close_disposal": None, "closed_window": None}
                report["cycles"].append(cycle)
                phase = f"cycle_{cycle_number:02d}_cold_persistent_send"
                cold_conversation_id, cold_record = self._turn(report, cycle=cycle_number, phase="cold", conversation=current_conversation, timeout=timeout, poll_interval=poll_interval)
                cycle["cold_turn"] = cold_record
                cold_tab_id = self._validate_persistent_turn(cold_record, expected_created=True, expected_preexisting=False, phase=f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}_COLD")
                if first_conversation_id is None: first_conversation_id = cold_conversation_id
                elif cold_conversation_id != first_conversation_id: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:CONVERSATION_CHANGED_ON_COLD")
                phase = f"cycle_{cycle_number:02d}_warm_persistent_send"
                warm_conversation_id, warm_record = self._turn(report, cycle=cycle_number, phase="warm", conversation=cold_conversation_id, timeout=timeout, poll_interval=poll_interval)
                cycle["warm_turn"] = warm_record
                warm_tab_id = self._validate_persistent_turn(warm_record, expected_created=False, expected_preexisting=True, phase=f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}_WARM")
                if warm_conversation_id != first_conversation_id: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:CONVERSATION_CHANGED_ON_WARM")
                if warm_tab_id != cold_tab_id: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:WARM_DID_NOT_REUSE_COLD_RUNTIME_TAB")
                phase = f"cycle_{cycle_number:02d}_retained_resource_sample"
                sample = _resource_record(self.provider.sample_runtime_tab_resources(sample_ms=resource_sample_ms))
                cycle["retained_resource_sample"] = sample
                self._validate_resource_sample(sample, expected_tab_id=warm_tab_id, phase=f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}")
                phase = f"cycle_{cycle_number:02d}_turn_scoped_close_send"
                close_conversation_id, close_record = self._turn(report, cycle=cycle_number, phase="close", conversation=warm_conversation_id, timeout=timeout,
                                                                  poll_interval=poll_interval, browser_authority_policy="TURN_SCOPED", browser_authority_ttl_ms=0)
                cycle["close_turn"] = close_record
                if close_conversation_id != first_conversation_id: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:CONVERSATION_CHANGED_ON_CLOSE")
                self._validate_close_turn(close_record, expected_tab_id=warm_tab_id, phase=f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}")
                phase = f"cycle_{cycle_number:02d}_close_disposal_wait"
                disposal = self._wait_for_runtime_tab_absence(timeout=disposal_wait_timeout)
                cycle["close_disposal"] = disposal
                if disposal.get("confirmed") is not True: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:TURN_SCOPED_CLOSE_NOT_CONFIRMED")
                phase = f"cycle_{cycle_number:02d}_closed_stability_window"
                closed_window = self._prove_closed_window(duration_ms=closed_stability_ms)
                cycle["closed_window"] = closed_window
                if closed_window.get("confirmed") is not True: raise RuntimeError(f"PR8_8_REPLICATION_CYCLE_{cycle_number:02d}:CLOSED_WINDOW_NOT_STABLE")
                current_conversation = close_conversation_id

            phase = "replication_summary"
            cycles = report["cycles"]
            all_turn_records = [cycle[key] for cycle in cycles for key in ("cold_turn", "warm_turn", "close_turn")]
            cold_records = [cycle["cold_turn"] for cycle in cycles]
            warm_records = [cycle["warm_turn"] for cycle in cycles]
            close_records = [cycle["close_turn"] for cycle in cycles]
            lease_ids = [record["observation"].get("browser_authority_lease_id") for record in all_turn_records]
            generations = [record["observation"].get("browser_authority_generation") for record in all_turn_records]
            generations_int = [value for value in generations if isinstance(value, int) and not isinstance(value, bool)]
            lease_ids_unique = all(isinstance(value, str) and value for value in lease_ids) and len(set(lease_ids)) == len(lease_ids)
            generations_strict = len(generations_int) == len(generations) and all(later > earlier for earlier, later in zip(generations_int, generations_int[1:]))
            if not lease_ids_unique: raise RuntimeError("PR8_8_REPLICATION_LEASE_IDS_NOT_UNIQUE")
            if not generations_strict: raise RuntimeError("PR8_8_REPLICATION_LEASE_GENERATIONS_NOT_STRICTLY_INCREASING")
            final_status = self.provider.status()
            report["final_runtime_status"] = {"bridge_available": bool(final_status.available), "extension_connected": bool(final_status.extension_connected), "runtime_tab_id": final_status.runtime_tab_id}
            if final_status.runtime_tab_id is not None: raise RuntimeError("PR8_8_REPLICATION_FINAL_RUNTIME_TAB_NOT_CLOSED")
            cost_summary = self._build_cost_summary(cycles)
            resource_summary = self._build_resource_summary(cycles)
            report["cost_characterization"] = cost_summary
            report["foreground_characterization"] = {"cold": _foreground_summary(cold_records), "warm": _foreground_summary(warm_records), "close": _foreground_summary(close_records),
                                                       "all_writes": _foreground_summary(all_turn_records),
                                                       "interpretation": "observational_only_foreground_activation_is_environment_dependent"}
            report["resource_characterization"] = resource_summary
            report["final_conversation_id"] = first_conversation_id
            report["summary"] = {"independent_replication_completed": True, "replication_count": replications,
                                 "all_cold_turns_created_new_runtime_tab": True, "all_warm_turns_reused_same_runtime_tab": True,
                                 "all_close_turns_reused_then_closed_runtime_tab": True, "all_closed_windows_stable": True,
                                 "same_conversation_continued_across_all_cycles": True, "canonical_finality_preserved_across_all_writes": True,
                                 "retained_resource_samples_non_disruptive": resource_summary["sample_tab_activation_count"] == 0 and resource_summary["debugger_leak_count"] == 0,
                                 "lease_ids_unique": True, "lease_generation_strictly_increasing": True,
                                 "transport_default_persistent_preserved": True, "temporary_mode_boundary_preserved": True,
                                 "cost_comparison_is_descriptive_only": True, "default_policy_change_performed": False,
                                 "write_budget_respected": report["write_attempts"] <= report["write_budget"], "automatic_write_retry_attempted": False}
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = self._failure_payload(error)
            return report


def main() -> int:
    parser = argparse.ArgumentParser(description="PR8.8 independent Browser Authority policy replication with warm-retention vs cold-recreation cost/resource characterization")
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    parser.add_argument("--resource-sample-ms", type=int, default=DEFAULT_RESOURCE_SAMPLE_MS)
    parser.add_argument("--disposal-wait-timeout", type=float, default=DEFAULT_DISPOSAL_WAIT_SECONDS)
    parser.add_argument("--closed-stability-ms", type=int, default=DEFAULT_CLOSED_STABILITY_MS)
    parser.add_argument("--acknowledge-live-writes", action="store_true", help="required: exactly three real product writes per completed replication cycle")
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required because this runner performs real ChatGPT product writes")
    if args.replications < MIN_REPLICATIONS or args.replications > MAX_REPLICATIONS:
        parser.error(f"--replications must be between {MIN_REPLICATIONS} and {MAX_REPLICATIONS}")
    client = ChatGPTWebClient(auth_file=args.auth_file, auto_refresh_auth=True, auto_login=False, auto_sentinel=False)
    provider = BrowserAuthorityCharacterizationProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    runner = BrowserAuthorityPolicyReplicationRunner(runtime, provider=provider)
    report = runner.run(acknowledge_live_writes=True, conversation=args.conversation, timeout=args.timeout,
                        poll_interval=args.poll_interval, replications=args.replications, resource_sample_ms=args.resource_sample_ms,
                        disposal_wait_timeout=args.disposal_wait_timeout, closed_stability_ms=args.closed_stability_ms)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
