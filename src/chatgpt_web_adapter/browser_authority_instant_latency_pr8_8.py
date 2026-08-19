from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from .browser_authority_phase_cost_attribution_pr8_8 import (
    BrowserAuthorityPhaseCostAttributionRunner,
    BrowserAuthorityPhaseTimingProvider,
    PHASE_KEYS,
    PHASE_SCHEMA,
    _int,
    _stats,
)
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
INSTANT_MODE_SCHEMA = 1


def _prompt(cycle: int, phase: str) -> str:
    return f"Reply with exactly: SDK_PR8_8_INSTANT_LATENCY_{cycle:02d}_{phase.upper()}_OK"


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if (
        isinstance(numerator, bool)
        or isinstance(denominator, bool)
        or not isinstance(numerator, (int, float))
        or not isinstance(denominator, (int, float))
        or denominator <= 0
    ):
        return None
    return float(numerator) / float(denominator)


class InstantModeLatencyProvider(BrowserAuthorityPhaseTimingProvider):
    """PR8.8 provider that requests Instant characterization on real write RPCs only.

    No generic product-runtime API is widened. The characterization requirement
    is injected only by this dedicated provider when the proven browser-owned
    runtime sends a real product turn carrying a Browser Authority lease.
    """

    def _rpc(self, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        outbound = payload
        if (
            payload.get("type") == "turn"
            and isinstance(payload.get("text"), str)
            and bool(payload["text"].strip())
            and isinstance(payload.get("browserAuthorityLeaseId"), str)
            and bool(payload["browserAuthorityLeaseId"].strip())
        ):
            outbound = {
                **payload,
                "requiredModelMode": "INSTANT",
                "requireNoReasoningRoute": True,
            }
        return super()._rpc(outbound, timeout=timeout)

    def instant_mode_support(self) -> dict[str, Any]:
        response = self._characterization_rpc(
            {"characterizeInstantModeSupport": True, "timeoutMs": 3000},
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "instant_mode_supported": response.get("instantModeSupported") is True,
            "instant_mode_schema_version": _int(response.get("instantModeSchemaVersion")),
            "selected_mode_probe_supported": response.get("selectedModeProbeSupported") is True,
            "request_route_observation_supported": response.get("requestRouteObservationSupported") is True,
            "response_route_observation_supported": response.get("responseRouteObservationSupported") is True,
        }

    def selected_mode_preflight(self, conversation: str, *, timeout: float = 20.0) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        response = self._characterization_rpc(
            {
                "characterizeInstantSelectedMode": True,
                "conversationId": conversation.strip(),
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        return {
            "conversation_id": _string(response.get("conversationId")),
            "selected_mode": _string(response.get("selectedMode")),
            "selected_mode_proven": response.get("selectedModeProven") is True,
            "candidate_count": _int(response.get("candidateCount")) or 0,
            "nearest_distance_px": _int(response.get("nearestDistancePx")),
            "proof_kind": _string(response.get("proofKind")),
            "conversation_write_count": _int(response.get("conversationWriteCount")),
            "runtime_tab_id_during_probe": _int(response.get("runtimeTabIdDuringProbe")),
            "runtime_tab_id_after": _int(response.get("runtimeTabIdAfter")),
            "probe_tab_closed": response.get("probeTabClosed") is True,
            "tab_was_active": _bool(response.get("tabWasActive")),
            "tab_active_after": _bool(response.get("tabActiveAfter")),
            "tab_activated_during_probe": response.get("tabActivatedDuringProbe") is True,
            "foreground_activation_observed": response.get("foregroundActivationObserved") is True,
            "debugger_attached_after": _bool(response.get("debuggerAttachedAfter")),
        }

    def instant_mode_for_lease(self, lease_id: str) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        lease_id = lease_id.strip()
        response = self._characterization_rpc(
            {
                "characterizeInstantModeRecord": True,
                "expectedBrowserAuthorityLeaseId": lease_id,
                "timeoutMs": 3000,
            },
            timeout=max(1.0, self.connect_timeout),
        )
        if response.get("instantModeSupported") is not True:
            raise RequestError("PR8_8_INSTANT_MODE_NOT_SUPPORTED", request_stage="instant_mode_characterization")
        if response.get("instantModeLeaseId") != lease_id:
            raise RequestError("PR8_8_INSTANT_MODE_LEASE_MISMATCH", request_stage="instant_mode_characterization")
        if _int(response.get("instantModeSchemaVersion")) != INSTANT_MODE_SCHEMA:
            raise RequestError("PR8_8_INSTANT_MODE_SCHEMA_MISMATCH", request_stage="instant_mode_characterization")

        def evidence(name: str) -> dict[str, Any]:
            value = response.get(name)
            value = value if isinstance(value, dict) else {}
            return {
                "model_identifiers": _list_of_strings(value.get("modelIdentifiers")),
                "model_modes": _list_of_strings(value.get("modelModes")),
                "reasoning_states": _list_of_strings(value.get("reasoningStates")),
                "model_hint_keys": _list_of_strings(value.get("modelHintKeys")),
                "reasoning_hint_keys": _list_of_strings(value.get("reasoningHintKeys")),
            }

        return {
            "instant_mode_lease_id": lease_id,
            "instant_mode_schema_version": INSTANT_MODE_SCHEMA,
            "requested_model_mode": _string(response.get("requestedModelMode")),
            "require_no_reasoning_route": response.get("requireNoReasoningRoute") is True,
            "selected_mode_before_write": _string(response.get("selectedModeBeforeWrite")),
            "selected_mode_before_write_proven": response.get("selectedModeBeforeWriteProven") is True,
            "selected_mode_candidate_count": _int(response.get("selectedModeCandidateCount")) or 0,
            "selected_mode_nearest_distance_px": _int(response.get("selectedModeNearestDistancePx")),
            "selected_mode_proof_kind": _string(response.get("selectedModeProofKind")),
            "conversation_request_observed": response.get("conversationRequestObserved") is True,
            "request_evidence": evidence("requestEvidence"),
            "response_evidence": evidence("responseEvidence"),
            "network_route_status": _string(response.get("networkRouteStatus")) or "INCONCLUSIVE",
            "instant_model_route_observed": response.get("instantModelRouteObserved") is True,
            "reasoning_route_observed": response.get("reasoningRouteObserved") is True,
            "reasoning_off_observed": response.get("reasoningOffObserved") is True,
            "network_no_reasoning_route_proven": response.get("networkNoReasoningRouteProven") is True,
        }


class InstantModePhaseLatencyRunner(BrowserAuthorityPhaseCostAttributionRunner):
    """Repeated fixed-conversation Instant latency characterization.

    The run requires a read-only exact-conversation Instant picker proof plus an
    explicit human confirmation that Instant -> Medium auto-switching is disabled
    in ChatGPT General settings. Browser-local request/response metadata is then
    used as an independent contradiction/proof channel. Positive reasoning-route
    evidence stops later writes; inconclusive network metadata is reported rather
    than silently promoted to proof.
    """

    def __init__(
        self,
        runtime: Any,
        *,
        provider: InstantModeLatencyProvider,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(runtime, provider=provider, monotonic=monotonic, sleep=sleep)
        self.provider = provider

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

    @staticmethod
    def _validate_preflight_mode(record: dict[str, Any], conversation: str) -> None:
        if record.get("conversation_id") != conversation:
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_CONVERSATION_MISMATCH")
        if record.get("conversation_write_count") != 0:
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_WROTE_TO_CONVERSATION")
        if record.get("selected_mode_proven") is not True or record.get("selected_mode") != "INSTANT":
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_SELECTED_MODE_NOT_PROVEN")
        if record.get("probe_tab_closed") is not True or record.get("runtime_tab_id_after") is not None:
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_RUNTIME_TAB_NOT_RESTORED_CLOSED")
        if record.get("debugger_attached_after") is True:
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_DEBUGGER_LEAK")
        if record.get("foreground_activation_observed") is True:
            raise RuntimeError("PR8_8_INSTANT_PREFLIGHT_FOREGROUND_DISTURBANCE")

    @staticmethod
    def _validate_instant_record(record: dict[str, Any], *, phase: str) -> None:
        if record.get("requested_model_mode") != "INSTANT":
            raise RuntimeError(f"{phase}:INSTANT_REQUIREMENT_NOT_RECORDED")
        if record.get("require_no_reasoning_route") is not True:
            raise RuntimeError(f"{phase}:NO_REASONING_REQUIREMENT_NOT_RECORDED")
        if record.get("selected_mode_before_write_proven") is not True:
            raise RuntimeError(f"{phase}:SELECTED_MODE_BEFORE_WRITE_NOT_PROVEN")
        if record.get("selected_mode_before_write") != "INSTANT":
            raise RuntimeError(f"{phase}:SELECTED_MODE_CHANGED_BEFORE_WRITE")
        if record.get("conversation_request_observed") is not True:
            raise RuntimeError(f"{phase}:CONVERSATION_REQUEST_NOT_OBSERVED")
        if record.get("reasoning_route_observed") is True:
            raise RuntimeError(f"{phase}:REASONING_ROUTE_OBSERVED")

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
        kwargs: dict[str, Any] = {
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
            raise RuntimeError(f"PR8_8_INSTANT_{phase.upper()}:LEASE_ID_MISSING")

        timing = self.provider.phase_timing_for_lease(lease_id)
        self._validate_timing(timing, f"PR8_8_INSTANT_{phase.upper()}")
        instant = self.provider.instant_mode_for_lease(lease_id)
        self._validate_instant_record(instant, phase=f"PR8_8_INSTANT_{phase.upper()}")
        released_at = _int(observation.get("browser_authority_released_at_ms"))
        cid = _conversation_id(execution)
        return cid, {
            "cycle": cycle,
            "phase": phase,
            "total_ms": round((self._monotonic() - started) * 1000),
            "conversation_id": cid,
            "provenance": _provenance_record(execution),
            "observation": observation,
            "phase_timing": timing,
            "instant_mode": instant,
            "post_release_canonical_return_ms": (
                returned_at_ms - released_at
                if released_at is not None and returned_at_ms >= released_at
                else None
            ),
        }

    @staticmethod
    def _latency_summary(cycles: list[dict[str, Any]]) -> dict[str, Any]:
        pairs: list[dict[str, Any]] = []
        for cycle in cycles:
            cold = cycle["cold_turn"]
            warm = cycle["warm_turn"]
            pair = {
                "cycle": cycle["cycle"],
                "cold_total_ms": cold["total_ms"],
                "warm_total_ms": warm["total_ms"],
                "cold_minus_warm_total_ms": cold["total_ms"] - warm["total_ms"],
                "cold_over_warm_total_ratio": _ratio(cold["total_ms"], warm["total_ms"]),
            }
            for key in PHASE_KEYS:
                c = cold["phase_timing"][key]
                w = warm["phase_timing"][key]
                pair[f"cold_{key}"] = c
                pair[f"warm_{key}"] = w
                pair[f"cold_minus_warm_{key}"] = c - w
            pair["cold_post_release_canonical_return_ms"] = cold["post_release_canonical_return_ms"]
            pair["warm_post_release_canonical_return_ms"] = warm["post_release_canonical_return_ms"]
            pair["cold_recreation_share_of_total"] = _ratio(
                cold["phase_timing"]["runtime_tab_first_resolve_ms"],
                cold["total_ms"],
            )
            pair["cold_prewrite_penalty_ms"] = (
                cold["phase_timing"]["tab_ready_to_write_delegated_ms"]
                - warm["phase_timing"]["tab_ready_to_write_delegated_ms"]
            )
            pair["cold_prewrite_penalty_share_of_warm_total"] = _ratio(
                pair["cold_prewrite_penalty_ms"],
                warm["total_ms"],
            )
            pairs.append(pair)

        phase_distributions = {
            key: {
                "cold": _stats(pair[f"cold_{key}"] for pair in pairs),
                "warm": _stats(pair[f"warm_{key}"] for pair in pairs),
                "cold_minus_warm": _stats(pair[f"cold_minus_warm_{key}"] for pair in pairs),
            }
            for key in PHASE_KEYS
        }
        return {
            "pairs": pairs,
            "total_ms": {
                "cold": _stats(pair["cold_total_ms"] for pair in pairs),
                "warm": _stats(pair["warm_total_ms"] for pair in pairs),
                "cold_minus_warm": _stats(pair["cold_minus_warm_total_ms"] for pair in pairs),
                "cold_over_warm_ratio": _stats(pair["cold_over_warm_total_ratio"] for pair in pairs),
            },
            "phase_distributions": phase_distributions,
            "post_release_canonical_return_ms": {
                "cold": _stats(pair["cold_post_release_canonical_return_ms"] for pair in pairs),
                "warm": _stats(pair["warm_post_release_canonical_return_ms"] for pair in pairs),
            },
            "cold_recreation_share_of_total": _stats(pair["cold_recreation_share_of_total"] for pair in pairs),
            "cold_prewrite_penalty_ms": _stats(pair["cold_prewrite_penalty_ms"] for pair in pairs),
            "cold_prewrite_penalty_share_of_warm_total": _stats(
                pair["cold_prewrite_penalty_share_of_warm_total"] for pair in pairs
            ),
            "interpretation": "instant_fixed_exact_reply_descriptive_only",
        }

    @staticmethod
    def _model_route_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
        instant_records = [record["instant_mode"] for record in records]
        statuses = [record["network_route_status"] for record in instant_records]
        return {
            "turn_count": len(instant_records),
            "selected_instant_before_write_count": sum(
                record["selected_mode_before_write"] == "INSTANT"
                and record["selected_mode_before_write_proven"] is True
                for record in instant_records
            ),
            "network_no_reasoning_route_proven_count": sum(
                record["network_no_reasoning_route_proven"] is True for record in instant_records
            ),
            "network_route_inconclusive_count": sum(status == "INCONCLUSIVE" for status in statuses),
            "reasoning_route_observed_count": sum(
                record["reasoning_route_observed"] is True for record in instant_records
            ),
            "network_route_statuses": statuses,
            "acceptance_basis": (
                "selected Instant proven before every write + explicit manual confirmation that "
                "Instant auto-switch is disabled + zero positive reasoning-route observations; "
                "network no-reasoning proof is reported separately and is not fabricated when metadata is inconclusive"
            ),
        }

    def run(
        self,
        *,
        acknowledge_live_writes: bool,
        confirm_instant_auto_switch_disabled: bool,
        conversation: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        replications: int = DEFAULT_REPLICATIONS,
        disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
        closed_stability_ms: int = DEFAULT_CLOSED_STABILITY_MS,
    ) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError("PR8.8 Instant latency characterization performs real product writes")
        if confirm_instant_auto_switch_disabled is not True:
            raise ValueError(
                "confirm_instant_auto_switch_disabled=True is required after disabling Instant auto-switch in ChatGPT General settings"
            )
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        conversation = conversation.strip()
        if replications < 2 or replications > 5:
            raise ValueError("replications must be between 2 and 5")
        if timeout <= 0 or poll_interval <= 0 or disposal_wait_timeout <= 0:
            raise ValueError("timeouts and poll_interval must be positive")
        if closed_stability_ms < 200 or closed_stability_ms > 5000:
            raise ValueError("closed_stability_ms must be between 200 and 5000")

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "instant_mode_phase_level_latency_no_reasoning_baseline",
            "runtime_surface": "ChatGPTProductRuntime",
            "requested_model_mode": "INSTANT",
            "manual_instant_auto_switch_disabled_confirmation": True,
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
        phase = "instant_preflight"
        try:
            try:
                instant_support = self.provider.instant_mode_support()
                timing_support = self.provider.phase_timing_support()
            except Exception as error:
                raise RuntimeError("PR8_8_INSTANT_EXTENSION_RELOAD_REQUIRED_BEFORE_WRITES") from error
            report["instant_mode_support"] = instant_support
            report["phase_timing_support"] = timing_support
            if (
                instant_support["instant_mode_supported"] is not True
                or instant_support["instant_mode_schema_version"] != INSTANT_MODE_SCHEMA
                or instant_support["selected_mode_probe_supported"] is not True
                or timing_support["phase_timing_supported"] is not True
                or timing_support["phase_timing_schema_version"] != PHASE_SCHEMA
            ):
                raise RuntimeError("PR8_8_INSTANT_EXTENSION_RELOAD_REQUIRED_BEFORE_WRITES")

            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported or not support.runtime_tab_release_supported:
                raise RuntimeError("PR8_8_INSTANT_EXTENSION_SUPPORT_NOT_AVAILABLE")
            if support.runtime_tab_id is not None:
                raise RuntimeError("PR8_8_INSTANT_INITIAL_RUNTIME_TAB_MUST_BE_ABSENT")

            health = self.runtime.health(conversation)
            report["runtime_health"] = health.to_dict()
            if health.ready is not True or health.canonical_status != "completed":
                raise RuntimeError("PR8_8_INSTANT_FIXED_CONVERSATION_NOT_READY")

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
                raise RuntimeError("PR8_8_INSTANT_RUNTIME_GOVERNANCE_CHANGED")
            if governance.get("browser_authority_effective_runtime_default_policy") != "PERSISTENT":
                raise RuntimeError("PR8_8_INSTANT_DEFAULT_POLICY_NOT_PERSISTENT")
            if governance.get("browser_authority_effective_runtime_default_ttl_ms") is not None:
                raise RuntimeError("PR8_8_INSTANT_PERSISTENT_DEFAULT_HAS_TTL")
            if governance.get("browser_authority_policy_contract_scope") != "RESOURCE_LIFECYCLE_ONLY":
                raise RuntimeError("PR8_8_INSTANT_POLICY_SCOPE_CHANGED")
            if governance.get("temporary_mode_production_enabled") is not False:
                raise RuntimeError("PR8_8_INSTANT_TEMPORARY_BOUNDARY_CHANGED")

            phase = "instant_selected_mode_exact_conversation_preflight"
            mode_preflight = self.provider.selected_mode_preflight(conversation)
            report["selected_mode_preflight"] = mode_preflight
            self._validate_preflight_mode(mode_preflight, conversation)
            post_probe_status = self.provider.status()
            report["post_mode_probe_runtime_status"] = {
                "bridge_available": post_probe_status.available,
                "extension_connected": post_probe_status.extension_connected,
                "runtime_tab_id": post_probe_status.runtime_tab_id,
            }
            if post_probe_status.runtime_tab_id is not None:
                raise RuntimeError("PR8_8_INSTANT_MODE_PROBE_DID_NOT_RESTORE_COLD_BASELINE")

            for n in range(1, replications + 1):
                cycle = {
                    "cycle": n,
                    "cold_turn": None,
                    "warm_turn": None,
                    "close_turn": None,
                    "close_disposal": None,
                    "closed_window": None,
                }
                report["cycles"].append(cycle)

                phase = f"cycle_{n:02d}_instant_cold_persistent_send"
                cid, cold = self._turn(
                    report,
                    cycle=n,
                    phase="cold",
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                cycle["cold_turn"] = cold
                cold_tab = self._persistent(
                    cold,
                    created=True,
                    preexisting=False,
                    phase=f"PR8_8_INSTANT_{n:02d}_COLD",
                )
                if cid != conversation:
                    raise RuntimeError(f"PR8_8_INSTANT_{n:02d}:CONVERSATION_CHANGED_ON_COLD")

                phase = f"cycle_{n:02d}_instant_warm_persistent_send"
                cid, warm = self._turn(
                    report,
                    cycle=n,
                    phase="warm",
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                cycle["warm_turn"] = warm
                warm_tab = self._persistent(
                    warm,
                    created=False,
                    preexisting=True,
                    phase=f"PR8_8_INSTANT_{n:02d}_WARM",
                )
                if cid != conversation or warm_tab != cold_tab:
                    raise RuntimeError(f"PR8_8_INSTANT_{n:02d}:WARM_REUSE_FAILED")

                phase = f"cycle_{n:02d}_instant_turn_scoped_close_send"
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
                self._close(close, warm_tab, f"PR8_8_INSTANT_{n:02d}")
                if cid != conversation:
                    raise RuntimeError(f"PR8_8_INSTANT_{n:02d}:CONVERSATION_CHANGED_ON_CLOSE")

                phase = f"cycle_{n:02d}_instant_close_disposal_wait"
                cycle["close_disposal"] = self._wait_absent(disposal_wait_timeout)
                if cycle["close_disposal"]["confirmed"] is not True:
                    raise RuntimeError(f"PR8_8_INSTANT_{n:02d}:CLOSE_NOT_CONFIRMED")

                phase = f"cycle_{n:02d}_instant_closed_stability_window"
                cycle["closed_window"] = self._closed_window(closed_stability_ms)
                if cycle["closed_window"]["confirmed"] is not True:
                    raise RuntimeError(f"PR8_8_INSTANT_{n:02d}:CLOSED_WINDOW_NOT_STABLE")

            phase = "instant_latency_summary"
            records = [cycle[key] for cycle in report["cycles"] for key in ("cold_turn", "warm_turn", "close_turn")]
            lease_ids = [record["observation"]["browser_authority_lease_id"] for record in records]
            generations = [record["observation"]["browser_authority_generation"] for record in records]
            if len(set(lease_ids)) != len(lease_ids):
                raise RuntimeError("PR8_8_INSTANT_LEASE_IDS_NOT_UNIQUE")
            if not all(b > a for a, b in zip(generations, generations[1:])):
                raise RuntimeError("PR8_8_INSTANT_GENERATIONS_NOT_STRICT")

            model_summary = self._model_route_summary(records)
            if model_summary["reasoning_route_observed_count"] != 0:
                raise RuntimeError("PR8_8_INSTANT_REASONING_ROUTE_OBSERVED")
            if model_summary["selected_instant_before_write_count"] != len(records):
                raise RuntimeError("PR8_8_INSTANT_NOT_SELECTED_FOR_EVERY_WRITE")

            final_status = self.provider.status()
            report["final_runtime_status"] = {
                "bridge_available": final_status.available,
                "extension_connected": final_status.extension_connected,
                "runtime_tab_id": final_status.runtime_tab_id,
            }
            if final_status.runtime_tab_id is not None:
                raise RuntimeError("PR8_8_INSTANT_FINAL_RUNTIME_TAB_NOT_CLOSED")

            report["instant_latency_characterization"] = self._latency_summary(report["cycles"])
            report["model_route_characterization"] = model_summary
            report["cross_mode_governance"] = {
                "current_run_model_mode": "INSTANT",
                "manual_auto_switch_disabled_confirmation": True,
                "prior_reasoning_phase_report_embedded": False,
                "cross_mode_numeric_verdict_performed": False,
                "reasoning_reference_required_for_cross_mode_verdict": True,
                "library_default_policy": "PERSISTENT",
                "library_default_change_performed": False,
                "hde_assembly_policy_change_performed": False,
                "decision_requires_human_review": True,
                "temporary_mode_boundary_preserved": True,
            }
            report["final_conversation_id"] = conversation
            report["summary"] = {
                "instant_latency_characterization_completed": True,
                "replication_count": replications,
                "exact_conversation_instant_preflight_proven": True,
                "instant_selected_before_every_write": True,
                "manual_instant_auto_switch_disabled_confirmed": True,
                "positive_reasoning_route_observations": 0,
                "network_no_reasoning_route_proven_count": model_summary["network_no_reasoning_route_proven_count"],
                "network_route_inconclusive_count": model_summary["network_route_inconclusive_count"],
                "all_cold_turns_created_new_runtime_tab": True,
                "all_warm_turns_reused_same_runtime_tab": True,
                "all_close_turns_reused_then_closed_runtime_tab": True,
                "all_closed_windows_stable": True,
                "same_completed_conversation_used_for_every_pair": True,
                "canonical_finality_preserved_across_all_writes": True,
                "phase_timing_preserved_across_all_writes": True,
                "cross_mode_verdict_deferred_until_reference_comparison": True,
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
    parser = argparse.ArgumentParser(
        description=(
            "PR8.8 Instant-mode fixed-conversation phase-level latency characterization "
            "with no-reasoning boundary evidence"
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    parser.add_argument("--disposal-wait-timeout", type=float, default=DEFAULT_DISPOSAL_WAIT_SECONDS)
    parser.add_argument("--closed-stability-ms", type=int, default=DEFAULT_CLOSED_STABILITY_MS)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument(
        "--confirm-instant-auto-switch-disabled",
        action="store_true",
        help="required: confirm ChatGPT General setting that allows Instant to auto-switch to deeper reasoning is disabled",
    )
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required because this runner performs real ChatGPT product writes")
    if not args.confirm_instant_auto_switch_disabled:
        parser.error(
            "--confirm-instant-auto-switch-disabled is required after disabling Instant auto-switch in ChatGPT General settings"
        )

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = InstantModeLatencyProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    runner = InstantModePhaseLatencyRunner(runtime, provider=provider)
    report = runner.run(
        acknowledge_live_writes=True,
        confirm_instant_auto_switch_disabled=True,
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
