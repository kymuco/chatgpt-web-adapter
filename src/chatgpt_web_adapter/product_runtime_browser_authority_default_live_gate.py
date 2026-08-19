from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from .browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)
from .client import ChatGPTWebClient
from .product_runtime import ChatGPTProductRuntime, assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_IDLE_TTL_MS = 5_000
DEFAULT_DISPOSAL_WAIT_SECONDS = 15.0
DEFAULT_RETENTION_MARGIN_SECONDS = 1.0

LIVE_PROMPTS = {
    "runtime_default_idle_ttl_initial": (
        "Reply with exactly: SDK_PR8_8_RUNTIME_DEFAULT_IDLE_TTL_INITIAL_OK"
    ),
    "per_turn_persistent_override": (
        "Reply with exactly: SDK_PR8_8_PER_TURN_PERSISTENT_OVERRIDE_OK"
    ),
    "runtime_default_idle_ttl_restored": (
        "Reply with exactly: SDK_PR8_8_RUNTIME_DEFAULT_IDLE_TTL_RESTORED_OK"
    ),
}


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _conversation_id(execution: Any) -> str:
    response = getattr(execution, "response", None)
    conversation = getattr(response, "conversation", None)
    value = getattr(conversation, "conversation_id", None)
    if not isinstance(value, str) or not value:
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_MISSING_CONVERSATION_ID")
    return value


def _provenance_record(execution: Any) -> dict[str, Any]:
    provenance = getattr(execution, "provenance", None)
    if provenance is None:
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_PROVENANCE_MISSING")

    completion = getattr(provenance, "completion", None)
    if getattr(completion, "completed", None) is not True:
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_COMPLETION_NOT_PROVEN")
    if getattr(completion, "canonical_completion_proven", None) is not True:
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_CANONICAL_FINALITY_NOT_PROVEN")

    conversation_mode = getattr(provenance, "conversation_mode", None)
    requested_mode = _enum_value(
        getattr(conversation_mode, "requested_conversation_mode", None)
    )
    observed_mode = _enum_value(
        getattr(conversation_mode, "observed_conversation_mode", None)
    )
    observed_mode_proven = getattr(conversation_mode, "observed_mode_proven", None)
    if (
        requested_mode != "NORMAL"
        or observed_mode != "NORMAL"
        or observed_mode_proven is not True
    ):
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_NORMAL_MODE_NOT_PROVEN")

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
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_WRITE_EVENT_NOT_OBSERVED")
    if getattr(observation, "browser_authority_release_proven", None) is not True:
        raise RuntimeError("PR8_8_RUNTIME_DEFAULT_AUTHORITY_RELEASE_NOT_PROVEN")

    return {
        "write_event_observed": True,
        "runtime_tab_id": getattr(observation, "runtime_tab_id", None),
        "runtime_tab_preexisting": getattr(
            observation, "runtime_tab_preexisting", None
        ),
        "runtime_tab_created_for_turn": getattr(
            observation, "runtime_tab_created_for_turn", None
        ),
        "foreground_activation_observed": getattr(
            observation, "foreground_activation_observed", None
        ),
        "browser_authority_lease_id": getattr(
            observation, "browser_authority_lease_id", None
        ),
        "browser_authority_generation": getattr(
            observation, "browser_authority_generation", None
        ),
        "browser_authority_policy": getattr(
            observation, "browser_authority_policy", None
        ),
        "browser_authority_ttl_ms": getattr(
            observation, "browser_authority_ttl_ms", None
        ),
        "browser_authority_issued_at_ms": getattr(
            observation, "browser_authority_issued_at_ms", None
        ),
        "browser_authority_released_at_ms": getattr(
            observation, "browser_authority_released_at_ms", None
        ),
        "browser_authority_disposal_due_at_ms": getattr(
            observation, "browser_authority_disposal_due_at_ms", None
        ),
        "browser_authority_release_proven": True,
        "browser_authority_disposal_action": getattr(
            observation, "browser_authority_disposal_action", None
        ),
        "turn_lifecycle_id": getattr(observation, "turn_lifecycle_id", None),
        "turn_lifecycle_state_at_write": getattr(
            observation, "turn_lifecycle_state_at_write", None
        ),
    }


def _validate_idle_ttl_observation(
    observation: dict[str, Any],
    *,
    expected_ttl_ms: int,
    phase: str,
) -> None:
    if observation["browser_authority_policy"] != "IDLE_TTL":
        raise RuntimeError(f"{phase}:IDLE_TTL_POLICY_NOT_OBSERVED")
    if observation["browser_authority_ttl_ms"] != expected_ttl_ms:
        raise RuntimeError(f"{phase}:IDLE_TTL_VALUE_NOT_OBSERVED")
    if observation["browser_authority_disposal_action"] != "CLOSE":
        raise RuntimeError(f"{phase}:IDLE_TTL_CLOSE_NOT_ARMED")

    released_at = observation["browser_authority_released_at_ms"]
    disposal_due_at = observation["browser_authority_disposal_due_at_ms"]
    if not isinstance(released_at, int) or isinstance(released_at, bool):
        raise RuntimeError(f"{phase}:RELEASE_TIMESTAMP_MISSING")
    if not isinstance(disposal_due_at, int) or isinstance(disposal_due_at, bool):
        raise RuntimeError(f"{phase}:DISPOSAL_TIMESTAMP_MISSING")
    if disposal_due_at - released_at != expected_ttl_ms:
        raise RuntimeError(f"{phase}:TTL_NOT_ANCHORED_TO_AUTHORITY_RELEASE")


class ProductRuntimeDefaultIdleTtlLiveGate:
    """Three-write proof of runtime-default/override/restoration precedence.

    Product mutation is performed only through ChatGPTProductRuntime. The gate
    observes runtime-tab absence/retention through provider.status() and never
    calls private writer state, lifecycle_snapshot(), or release_runtime_tab().
    """

    def __init__(
        self,
        runtime: ChatGPTProductRuntime,
        *,
        provider: BrowserAuthorityCharacterizationProvider,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.runtime = runtime
        self.provider = provider
        self._monotonic = monotonic
        self._sleep = sleep

    def _wait_for_runtime_tab_absence(self, *, timeout: float) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("disposal wait timeout must be positive")

        deadline = self._monotonic() + timeout
        last_status = None
        while self._monotonic() < deadline:
            last_status = self.provider.status()
            if (
                last_status.available
                and last_status.extension_connected
                and last_status.runtime_tab_id is None
            ):
                return {
                    "confirmed": True,
                    "bridge_available": True,
                    "extension_connected": True,
                    "runtime_tab_id_after": None,
                }
            self._sleep(0.1)

        if last_status is None:
            last_status = self.provider.status()
        return {
            "confirmed": False,
            "bridge_available": bool(getattr(last_status, "available", False)),
            "extension_connected": bool(
                getattr(last_status, "extension_connected", False)
            ),
            "runtime_tab_id_after": getattr(last_status, "runtime_tab_id", None),
        }

    def _prove_runtime_tab_retained(
        self,
        *,
        expected_runtime_tab_id: int,
        wait_seconds: float,
    ) -> dict[str, Any]:
        if wait_seconds <= 0:
            raise ValueError("retention wait must be positive")

        started = self._monotonic()
        deadline = started + wait_seconds
        samples = 0
        last_status = None
        while self._monotonic() < deadline:
            last_status = self.provider.status()
            samples += 1
            if (
                not last_status.available
                or not last_status.extension_connected
                or last_status.runtime_tab_id != expected_runtime_tab_id
            ):
                return {
                    "confirmed": False,
                    "expected_runtime_tab_id": expected_runtime_tab_id,
                    "runtime_tab_id_after": getattr(
                        last_status, "runtime_tab_id", None
                    ),
                    "bridge_available": bool(
                        getattr(last_status, "available", False)
                    ),
                    "extension_connected": bool(
                        getattr(last_status, "extension_connected", False)
                    ),
                    "observed_wait_ms": int(
                        round((self._monotonic() - started) * 1000)
                    ),
                    "samples": samples,
                }
            self._sleep(0.1)

        last_status = self.provider.status()
        samples += 1
        confirmed = (
            last_status.available
            and last_status.extension_connected
            and last_status.runtime_tab_id == expected_runtime_tab_id
        )
        return {
            "confirmed": bool(confirmed),
            "expected_runtime_tab_id": expected_runtime_tab_id,
            "runtime_tab_id_after": last_status.runtime_tab_id,
            "bridge_available": bool(last_status.available),
            "extension_connected": bool(last_status.extension_connected),
            "observed_wait_ms": int(
                round((self._monotonic() - started) * 1000)
            ),
            "samples": samples,
        }

    @staticmethod
    def _failure_payload(error: BaseException) -> dict[str, Any]:
        payload: dict[str, Any] = {
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

    def _turn(
        self,
        report: dict[str, Any],
        *,
        phase: str,
        prompt: str,
        conversation: Any,
        timeout: float,
        poll_interval: float,
        browser_authority_policy: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        report["write_attempts"] += 1
        started = self._monotonic()

        kwargs: dict[str, Any] = {
            "conversation": conversation,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "conversation_mode": "normal",
        }
        if browser_authority_policy is not None:
            kwargs["browser_authority_policy"] = browser_authority_policy

        execution = self.runtime.send_text_observed(prompt, **kwargs)
        total_ms = int(round((self._monotonic() - started) * 1000))
        report["write_completions"] += 1

        conversation_id = _conversation_id(execution)
        provenance = _provenance_record(execution)
        observation = _observation_record(execution)
        record = {
            "phase": phase,
            "conversation_id": conversation_id,
            "total_ms": total_ms,
            "provenance": provenance,
            "observation": observation,
        }
        return conversation_id, record

    def run(
        self,
        *,
        acknowledge_live_writes: bool,
        conversation: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        expected_idle_ttl_ms: int = DEFAULT_IDLE_TTL_MS,
        disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
        retention_margin_seconds: float = DEFAULT_RETENTION_MARGIN_SECONDS,
    ) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError(
                "PR8.8 runtime-default live gate performs three real product writes; "
                "set acknowledge_live_writes=True"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if (
            isinstance(expected_idle_ttl_ms, bool)
            or not isinstance(expected_idle_ttl_ms, int)
        ):
            raise TypeError("expected_idle_ttl_ms must be an int")
        if expected_idle_ttl_ms <= 0:
            raise ValueError("expected_idle_ttl_ms must be > 0")
        if disposal_wait_timeout <= 0:
            raise ValueError("disposal_wait_timeout must be positive")
        if retention_margin_seconds <= 0:
            raise ValueError("retention_margin_seconds must be positive")

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": (
                "high_level_runtime_default_idle_ttl_override_restoration_live_gate"
            ),
            "runtime_surface": "ChatGPTProductRuntime",
            "acknowledged_live_writes": True,
            "automatic_write_retry": False,
            "write_budget": 3,
            "write_attempts": 0,
            "write_completions": 0,
            "configured_runtime_default_policy": "IDLE_TTL",
            "configured_runtime_default_ttl_ms": expected_idle_ttl_ms,
            "initial_conversation_supplied": conversation is not None,
            "runtime_default_initial_turn": None,
            "runtime_default_initial_disposal": None,
            "persistent_override_turn": None,
            "persistent_override_retention": None,
            "runtime_default_restored_turn": None,
            "runtime_default_restored_disposal": None,
            "failure_phase": None,
            "failure": None,
        }

        phase = "high_level_runtime_default_preflight"
        try:
            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_EXTENSION_SUPPORT_NOT_AVAILABLE"
                )
            if not support.runtime_tab_release_supported:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_RUNTIME_TAB_RELEASE_NOT_AVAILABLE"
                )

            governance = dict(self.runtime.governance())
            report["runtime_governance"] = {
                "transport": governance.get("transport"),
                "automatic_write_retry": governance.get(
                    "automatic_write_retry"
                ),
                "canonical_readback_required": governance.get(
                    "canonical_readback_required"
                ),
                "browser_authority_policy_high_level_surface": governance.get(
                    "browser_authority_policy_high_level_surface"
                ),
                "browser_authority_selected_transport_policy_support": governance.get(
                    "browser_authority_selected_transport_policy_support"
                ),
                "browser_authority_effective_runtime_default_policy": governance.get(
                    "browser_authority_effective_runtime_default_policy"
                ),
                "browser_authority_effective_runtime_default_ttl_ms": governance.get(
                    "browser_authority_effective_runtime_default_ttl_ms"
                ),
                "browser_authority_runtime_default_policy_source": governance.get(
                    "browser_authority_runtime_default_policy_source"
                ),
                "browser_authority_policy_contract_scope": governance.get(
                    "browser_authority_policy_contract_scope"
                ),
                "temporary_mode_production_enabled": governance.get(
                    "temporary_mode_production_enabled"
                ),
            }

            if governance.get("automatic_write_retry") is not False:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_AUTOMATIC_RETRY_INVARIANT_CHANGED"
                )
            if governance.get("canonical_readback_required") is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_CANONICAL_READBACK_NOT_REQUIRED"
                )
            if governance.get("browser_authority_policy_high_level_surface") is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_HIGH_LEVEL_POLICY_SURFACE_NOT_AVAILABLE"
                )
            if (
                governance.get(
                    "browser_authority_selected_transport_policy_support"
                )
                is not True
            ):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_TRANSPORT_POLICY_SUPPORT_NOT_PROVEN"
                )
            if (
                governance.get(
                    "browser_authority_effective_runtime_default_policy"
                )
                != "IDLE_TTL"
            ):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_IDLE_TTL_NOT_CONFIGURED"
                )
            if (
                governance.get(
                    "browser_authority_effective_runtime_default_ttl_ms"
                )
                != expected_idle_ttl_ms
            ):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_IDLE_TTL_VALUE_MISMATCH"
                )
            if (
                governance.get("browser_authority_runtime_default_policy_source")
                != "RUNTIME_DEFAULT"
            ):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_POLICY_SOURCE_NOT_RUNTIME_DEFAULT"
                )
            if (
                governance.get("browser_authority_policy_contract_scope")
                != "RESOURCE_LIFECYCLE_ONLY"
            ):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_POLICY_SCOPE_CHANGED"
                )
            if governance.get("temporary_mode_production_enabled") is not False:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_TEMPORARY_BOUNDARY_CHANGED"
                )

            report["initial_runtime_tab_id"] = support.runtime_tab_id

            phase = "runtime_default_idle_ttl_initial_send"
            first_conversation_id, first_record = self._turn(
                report,
                phase=phase,
                prompt=LIVE_PROMPTS["runtime_default_idle_ttl_initial"],
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            report["runtime_default_initial_turn"] = first_record
            first_observation = first_record["observation"]
            _validate_idle_ttl_observation(
                first_observation,
                expected_ttl_ms=expected_idle_ttl_ms,
                phase="PR8_8_RUNTIME_DEFAULT_INITIAL",
            )

            phase = "runtime_default_idle_ttl_initial_disposal_wait"
            disposal_wait = max(
                disposal_wait_timeout,
                expected_idle_ttl_ms / 1000.0 + 5.0,
            )
            first_disposal = self._wait_for_runtime_tab_absence(
                timeout=disposal_wait,
            )
            report["runtime_default_initial_disposal"] = first_disposal
            if first_disposal.get("confirmed") is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_INITIAL_IDLE_TTL_CLOSE_NOT_CONFIRMED"
                )

            phase = "per_turn_persistent_override_send"
            second_conversation_id, second_record = self._turn(
                report,
                phase=phase,
                prompt=LIVE_PROMPTS["per_turn_persistent_override"],
                conversation=first_conversation_id,
                timeout=timeout,
                poll_interval=poll_interval,
                browser_authority_policy="PERSISTENT",
            )
            report["persistent_override_turn"] = second_record
            second_observation = second_record["observation"]

            if second_conversation_id != first_conversation_id:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_CONVERSATION_CHANGED_ON_OVERRIDE"
                )
            if second_observation["browser_authority_policy"] != "PERSISTENT":
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_PER_TURN_PERSISTENT_NOT_OBSERVED"
                )
            if second_observation["browser_authority_ttl_ms"] is not None:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_PER_TURN_PERSISTENT_HAS_TTL"
                )
            if second_observation["browser_authority_disposal_action"] != "KEEP":
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_PER_TURN_PERSISTENT_NOT_KEPT"
                )
            if second_observation["runtime_tab_created_for_turn"] is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_OVERRIDE_AUTHORITY_NOT_RECREATED"
                )

            second_tab_id = second_observation["runtime_tab_id"]
            if not isinstance(second_tab_id, int) or isinstance(second_tab_id, bool):
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_OVERRIDE_RUNTIME_TAB_MISSING"
                )

            phase = "per_turn_persistent_override_retention_wait"
            retention_wait_seconds = (
                expected_idle_ttl_ms / 1000.0 + retention_margin_seconds
            )
            retention = self._prove_runtime_tab_retained(
                expected_runtime_tab_id=second_tab_id,
                wait_seconds=retention_wait_seconds,
            )
            report["persistent_override_retention"] = retention
            if retention.get("confirmed") is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_PERSISTENT_OVERRIDE_NOT_RETAINED"
                )

            phase = "runtime_default_idle_ttl_restored_send"
            third_conversation_id, third_record = self._turn(
                report,
                phase=phase,
                prompt=LIVE_PROMPTS["runtime_default_idle_ttl_restored"],
                conversation=second_conversation_id,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            report["runtime_default_restored_turn"] = third_record
            third_observation = third_record["observation"]

            if third_conversation_id != first_conversation_id:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_CONVERSATION_CHANGED_AFTER_OVERRIDE"
                )
            _validate_idle_ttl_observation(
                third_observation,
                expected_ttl_ms=expected_idle_ttl_ms,
                phase="PR8_8_RUNTIME_DEFAULT_RESTORED",
            )
            if third_observation["runtime_tab_id"] != second_tab_id:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_RESTORED_USED_DIFFERENT_RUNTIME_TAB"
                )
            if third_observation["runtime_tab_preexisting"] is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_RESTORED_TAB_NOT_PREEXISTING"
                )
            if third_observation["runtime_tab_created_for_turn"] is not False:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_RESTORED_TAB_UNEXPECTEDLY_CREATED"
                )

            phase = "runtime_default_idle_ttl_restored_disposal_wait"
            third_disposal = self._wait_for_runtime_tab_absence(
                timeout=disposal_wait,
            )
            report["runtime_default_restored_disposal"] = third_disposal
            if third_disposal.get("confirmed") is not True:
                raise RuntimeError(
                    "PR8_8_RUNTIME_DEFAULT_RESTORED_IDLE_TTL_CLOSE_NOT_CONFIRMED"
                )

            phase = "summary"
            final_status = self.provider.status()
            report["final_runtime_status"] = {
                "bridge_available": bool(final_status.available),
                "extension_connected": bool(final_status.extension_connected),
                "runtime_tab_id": final_status.runtime_tab_id,
            }
            report["final_conversation_id"] = third_conversation_id
            report["summary"] = {
                "runtime_default_idle_ttl_observed_on_initial_send": True,
                "initial_idle_ttl_close_confirmed": True,
                "per_turn_persistent_override_observed": True,
                "per_turn_override_precedence_proven": True,
                "persistent_override_retained_beyond_runtime_ttl": True,
                "runtime_default_restored_after_override": True,
                "restored_default_reused_retained_runtime_tab": True,
                "restored_idle_ttl_close_confirmed": True,
                "same_conversation_continued_across_all_three_turns": True,
                "canonical_finality_preserved_across_all_three_turns": True,
                "temporary_mode_boundary_preserved": True,
                "write_budget_respected": (
                    report["write_attempts"] <= report["write_budget"]
                ),
                "automatic_write_retry_attempted": False,
            }
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = self._failure_payload(error)
            return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR8.8 high-level runtime-default IDLE_TTL / per-turn override / "
            "default-restoration live integration gate"
        )
    )
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
    )
    parser.add_argument(
        "--idle-ttl-ms",
        type=int,
        default=DEFAULT_IDLE_TTL_MS,
    )
    parser.add_argument(
        "--disposal-wait-timeout",
        type=float,
        default=DEFAULT_DISPOSAL_WAIT_SECONDS,
    )
    parser.add_argument(
        "--retention-margin-seconds",
        type=float,
        default=DEFAULT_RETENTION_MARGIN_SECONDS,
    )
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required: the runner performs up to three real ChatGPT product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required because this runner performs "
            "up to three real product writes"
        )
    if args.idle_ttl_ms <= 0:
        parser.error("--idle-ttl-ms must be > 0")

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = BrowserAuthorityCharacterizationProvider()
    runtime = assemble_product_runtime(
        client=client,
        provider=provider,
        browser_authority_policy="IDLE_TTL",
        browser_authority_ttl_ms=args.idle_ttl_ms,
    )
    gate = ProductRuntimeDefaultIdleTtlLiveGate(
        runtime,
        provider=provider,
    )
    report = gate.run(
        acknowledge_live_writes=True,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        expected_idle_ttl_ms=args.idle_ttl_ms,
        disposal_wait_timeout=args.disposal_wait_timeout,
        retention_margin_seconds=args.retention_margin_seconds,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
