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
from .product_runtime import ChatGPTProductRuntime

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_DISPOSAL_WAIT_SECONDS = 15.0

LIVE_PROMPTS = {
    "turn_scoped": "Reply with exactly: SDK_PR8_8_HIGH_LEVEL_TURN_SCOPED_OK",
    "post_close_persistent": (
        "Reply with exactly: SDK_PR8_8_HIGH_LEVEL_POST_CLOSE_PERSISTENT_OK"
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
        raise RuntimeError("PR8_8_HIGH_LEVEL_MISSING_CONVERSATION_ID")
    return value


def _require_high_level_canonical_success(execution: Any) -> dict[str, Any]:
    provenance = getattr(execution, "provenance", None)
    if provenance is None:
        raise RuntimeError("PR8_8_HIGH_LEVEL_PROVENANCE_MISSING")

    completion = getattr(provenance, "completion", None)
    if getattr(completion, "completed", None) is not True:
        raise RuntimeError("PR8_8_HIGH_LEVEL_COMPLETION_NOT_PROVEN")
    if getattr(completion, "canonical_completion_proven", None) is not True:
        raise RuntimeError("PR8_8_HIGH_LEVEL_CANONICAL_FINALITY_NOT_PROVEN")

    conversation_mode = getattr(provenance, "conversation_mode", None)
    requested_mode = _enum_value(
        getattr(conversation_mode, "requested_conversation_mode", None)
    )
    observed_mode = _enum_value(
        getattr(conversation_mode, "observed_conversation_mode", None)
    )
    observed_mode_proven = getattr(
        conversation_mode,
        "observed_mode_proven",
        None,
    )
    if (
        requested_mode != "NORMAL"
        or observed_mode != "NORMAL"
        or observed_mode_proven is not True
    ):
        raise RuntimeError("PR8_8_HIGH_LEVEL_NORMAL_MODE_NOT_PROVEN")

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
        raise RuntimeError("PR8_8_HIGH_LEVEL_WRITE_EVENT_NOT_OBSERVED")
    if getattr(observation, "browser_authority_release_proven", None) is not True:
        raise RuntimeError("PR8_8_HIGH_LEVEL_AUTHORITY_RELEASE_NOT_PROVEN")

    return {
        "write_event_observed": True,
        "runtime_tab_id": getattr(observation, "runtime_tab_id", None),
        "runtime_tab_preexisting": getattr(
            observation,
            "runtime_tab_preexisting",
            None,
        ),
        "runtime_tab_created_for_turn": getattr(
            observation,
            "runtime_tab_created_for_turn",
            None,
        ),
        "foreground_activation_observed": getattr(
            observation,
            "foreground_activation_observed",
            None,
        ),
        "browser_authority_lease_id": getattr(
            observation,
            "browser_authority_lease_id",
            None,
        ),
        "browser_authority_generation": getattr(
            observation,
            "browser_authority_generation",
            None,
        ),
        "browser_authority_policy": getattr(
            observation,
            "browser_authority_policy",
            None,
        ),
        "browser_authority_ttl_ms": getattr(
            observation,
            "browser_authority_ttl_ms",
            None,
        ),
        "browser_authority_issued_at_ms": getattr(
            observation,
            "browser_authority_issued_at_ms",
            None,
        ),
        "browser_authority_released_at_ms": getattr(
            observation,
            "browser_authority_released_at_ms",
            None,
        ),
        "browser_authority_disposal_due_at_ms": getattr(
            observation,
            "browser_authority_disposal_due_at_ms",
            None,
        ),
        "browser_authority_release_proven": True,
        "browser_authority_disposal_action": getattr(
            observation,
            "browser_authority_disposal_action",
            None,
        ),
        "turn_lifecycle_id": getattr(observation, "turn_lifecycle_id", None),
        "turn_lifecycle_state_at_write": getattr(
            observation,
            "turn_lifecycle_state_at_write",
            None,
        ),
    }


class ProductRuntimeBrowserAuthorityLiveGate:
    """Two-write live proof of PR8.8 high-level Browser Authority plumbing.

    Product mutation is performed only through ChatGPTProductRuntime. The gate
    does not inspect private writer/runtime state and does not call the explicit
    runtime-tab release primitive. Runtime-tab absence/recreation is observed
    through the already-supported provider status surface.
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

    def run(
        self,
        *,
        acknowledge_live_writes: bool,
        conversation: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        disposal_wait_timeout: float = DEFAULT_DISPOSAL_WAIT_SECONDS,
    ) -> dict[str, Any]:
        if acknowledge_live_writes is not True:
            raise ValueError(
                "PR8.8 high-level live gate performs two real product writes; "
                "set acknowledge_live_writes=True"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if disposal_wait_timeout <= 0:
            raise ValueError("disposal_wait_timeout must be positive")

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "high_level_product_runtime_browser_authority_live_gate",
            "runtime_surface": "ChatGPTProductRuntime",
            "acknowledged_live_writes": True,
            "automatic_write_retry": False,
            "write_budget": 2,
            "write_attempts": 0,
            "write_completions": 0,
            "initial_conversation_supplied": conversation is not None,
            "turn_scoped_turn": None,
            "turn_scoped_disposal": None,
            "post_close_persistent_turn": None,
            "failure_phase": None,
            "failure": None,
        }

        phase = "high_level_preflight"
        try:
            support = self.provider.characterization_status()
            report["extension_support"] = support.to_dict()
            if not support.supported:
                raise RuntimeError("PR8_8_HIGH_LEVEL_EXTENSION_SUPPORT_NOT_AVAILABLE")
            if not support.runtime_tab_release_supported:
                raise RuntimeError("PR8_8_HIGH_LEVEL_RUNTIME_TAB_RELEASE_NOT_AVAILABLE")

            governance = dict(self.runtime.governance())
            report["runtime_governance"] = {
                "transport": governance.get("transport"),
                "automatic_write_retry": governance.get("automatic_write_retry"),
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
                "browser_authority_policy_contract_scope": governance.get(
                    "browser_authority_policy_contract_scope"
                ),
                "temporary_mode_production_enabled": governance.get(
                    "temporary_mode_production_enabled"
                ),
            }
            if governance.get("automatic_write_retry") is not False:
                raise RuntimeError("PR8_8_HIGH_LEVEL_AUTOMATIC_RETRY_INVARIANT_CHANGED")
            if governance.get("canonical_readback_required") is not True:
                raise RuntimeError("PR8_8_HIGH_LEVEL_CANONICAL_READBACK_NOT_REQUIRED")
            if governance.get("browser_authority_policy_high_level_surface") is not True:
                raise RuntimeError("PR8_8_HIGH_LEVEL_POLICY_SURFACE_NOT_AVAILABLE")
            if (
                governance.get("browser_authority_selected_transport_policy_support")
                is not True
            ):
                raise RuntimeError("PR8_8_HIGH_LEVEL_TRANSPORT_POLICY_SUPPORT_NOT_PROVEN")
            if governance.get("browser_authority_effective_runtime_default_policy") != "PERSISTENT":
                raise RuntimeError("PR8_8_HIGH_LEVEL_DEFAULT_POLICY_NOT_PERSISTENT")
            if governance.get("browser_authority_effective_runtime_default_ttl_ms") is not None:
                raise RuntimeError("PR8_8_HIGH_LEVEL_PERSISTENT_DEFAULT_HAS_TTL")
            if governance.get("browser_authority_policy_contract_scope") != "RESOURCE_LIFECYCLE_ONLY":
                raise RuntimeError("PR8_8_HIGH_LEVEL_POLICY_SCOPE_CHANGED")
            if governance.get("temporary_mode_production_enabled") is not False:
                raise RuntimeError("PR8_8_HIGH_LEVEL_TEMPORARY_BOUNDARY_CHANGED")

            report["initial_runtime_tab_id"] = support.runtime_tab_id

            phase = "turn_scoped_high_level_send"
            report["write_attempts"] += 1
            first_started = self._monotonic()
            first_execution = self.runtime.send_text_observed(
                LIVE_PROMPTS["turn_scoped"],
                conversation=conversation,
                timeout=timeout,
                poll_interval=poll_interval,
                conversation_mode="normal",
                browser_authority_policy="TURN_SCOPED",
                browser_authority_ttl_ms=0,
            )
            first_total_ms = int(round((self._monotonic() - first_started) * 1000))
            report["write_completions"] += 1

            first_conversation_id = _conversation_id(first_execution)
            first_provenance = _require_high_level_canonical_success(first_execution)
            first_observation = _observation_record(first_execution)
            first_record = {
                "phase": "turn_scoped_high_level_send",
                "conversation_id": first_conversation_id,
                "total_ms": first_total_ms,
                "provenance": first_provenance,
                "observation": first_observation,
            }
            report["turn_scoped_turn"] = first_record

            if first_observation["browser_authority_policy"] != "TURN_SCOPED":
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_POLICY_NOT_OBSERVED")
            if first_observation["browser_authority_ttl_ms"] != 0:
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_TTL_NOT_OBSERVED")
            if first_observation["browser_authority_disposal_action"] != "CLOSE":
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_CLOSE_NOT_ARMED")
            first_lease_id = first_observation["browser_authority_lease_id"]
            if not isinstance(first_lease_id, str) or not first_lease_id:
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_LEASE_ID_MISSING")
            first_tab_id = first_observation["runtime_tab_id"]
            if not isinstance(first_tab_id, int) or isinstance(first_tab_id, bool):
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_RUNTIME_TAB_MISSING")

            phase = "turn_scoped_high_level_disposal_wait"
            disposal = self._wait_for_runtime_tab_absence(
                timeout=disposal_wait_timeout,
            )
            report["turn_scoped_disposal"] = disposal
            if disposal.get("confirmed") is not True:
                raise RuntimeError("PR8_8_HIGH_LEVEL_TURN_SCOPED_CLOSE_NOT_CONFIRMED")

            phase = "post_close_default_persistent_send"
            report["write_attempts"] += 1
            second_started = self._monotonic()
            second_execution = self.runtime.send_text_observed(
                LIVE_PROMPTS["post_close_persistent"],
                conversation=first_conversation_id,
                timeout=timeout,
                poll_interval=poll_interval,
                conversation_mode="normal",
            )
            second_total_ms = int(round((self._monotonic() - second_started) * 1000))
            report["write_completions"] += 1

            second_conversation_id = _conversation_id(second_execution)
            second_provenance = _require_high_level_canonical_success(second_execution)
            second_observation = _observation_record(second_execution)
            second_record = {
                "phase": "post_close_default_persistent_send",
                "conversation_id": second_conversation_id,
                "total_ms": second_total_ms,
                "provenance": second_provenance,
                "observation": second_observation,
            }
            report["post_close_persistent_turn"] = second_record

            if second_conversation_id != first_conversation_id:
                raise RuntimeError("PR8_8_HIGH_LEVEL_CONVERSATION_ID_CHANGED_AFTER_CLOSE")
            if second_observation["browser_authority_policy"] != "PERSISTENT":
                raise RuntimeError("PR8_8_HIGH_LEVEL_DEFAULT_PERSISTENT_NOT_OBSERVED")
            if second_observation["browser_authority_ttl_ms"] is not None:
                raise RuntimeError("PR8_8_HIGH_LEVEL_DEFAULT_PERSISTENT_TTL_PRESENT")
            if second_observation["browser_authority_disposal_action"] != "KEEP":
                raise RuntimeError("PR8_8_HIGH_LEVEL_DEFAULT_PERSISTENT_NOT_KEPT")
            if second_observation["runtime_tab_created_for_turn"] is not True:
                raise RuntimeError("PR8_8_HIGH_LEVEL_POST_CLOSE_AUTHORITY_NOT_RECREATED")

            second_tab_id = second_observation["runtime_tab_id"]
            if not isinstance(second_tab_id, int) or isinstance(second_tab_id, bool):
                raise RuntimeError("PR8_8_HIGH_LEVEL_RECREATED_RUNTIME_TAB_MISSING")
            if second_tab_id == first_tab_id:
                raise RuntimeError("PR8_8_HIGH_LEVEL_RUNTIME_TAB_ID_NOT_RECREATED")

            final_status = self.provider.status()
            report["final_runtime_status"] = {
                "bridge_available": final_status.available,
                "extension_connected": final_status.extension_connected,
                "runtime_tab_id": final_status.runtime_tab_id,
            }
            if not final_status.available or not final_status.extension_connected:
                raise RuntimeError("PR8_8_HIGH_LEVEL_FINAL_BRIDGE_NOT_READY")
            if final_status.runtime_tab_id != second_tab_id:
                raise RuntimeError("PR8_8_HIGH_LEVEL_PERSISTENT_RUNTIME_TAB_NOT_RETAINED")

            report["final_conversation_id"] = second_conversation_id
            report["summary"] = {
                "high_level_turn_scoped_override_observed": True,
                "turn_scoped_close_confirmed": True,
                "canonical_finality_preserved_for_turn_scoped_send": True,
                "same_conversation_continued_after_close": True,
                "browser_authority_recreated_for_next_high_level_turn": True,
                "default_persistent_policy_preserved": True,
                "canonical_finality_preserved_for_post_close_turn": True,
                "final_persistent_runtime_tab_retained": True,
                "runtime_tab_id_changed_after_close": first_tab_id != second_tab_id,
                "write_budget_respected": report["write_attempts"] <= 2,
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
            "PR8.8 two-write high-level ChatGPTProductRuntime Browser Authority live gate"
        )
    )
    parser.add_argument("--conversation")
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument(
        "--disposal-wait-timeout",
        type=float,
        default=DEFAULT_DISPOSAL_WAIT_SECONDS,
    )
    parser.add_argument(
        "--acknowledge-live-writes",
        action="store_true",
        help="required: the gate performs up to two real ChatGPT product writes",
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required because this gate performs "
            "up to two real product writes"
        )

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = BrowserAuthorityCharacterizationProvider()
    runtime = ChatGPTProductRuntime(client, provider=provider)
    runner = ProductRuntimeBrowserAuthorityLiveGate(
        runtime,
        provider=provider,
    )
    report = runner.run(
        acknowledge_live_writes=True,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        disposal_wait_timeout=args.disposal_wait_timeout,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
