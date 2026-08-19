from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .browser_authority_instant_latency_pr8_8 import (
    DEFAULT_CLOSED_STABILITY_MS,
    DEFAULT_DISPOSAL_WAIT_SECONDS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REPLICATIONS,
    DEFAULT_TIMEOUT,
    INSTANT_MODE_SCHEMA,
    InstantModeLatencyProvider,
    InstantModePhaseLatencyRunner,
    _bool,
    _list_of_strings,
    _string,
)
from .browser_authority_phase_cost_attribution_pr8_8 import _int, _stats
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

INSTANT_SELECTION_SCHEMA = 1


class InstantSelectionRepairProvider(InstantModeLatencyProvider):
    """Characterization provider for fresh-tab Instant product-UI materialization."""

    def instant_selection_support(self) -> dict[str, Any]:
        response = self._characterization_rpc(
            {
                "characterizeInstantSelectionRepairSupport": True,
                "timeoutMs": 3000,
            },
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "instant_selection_repair_supported":
                response.get("instantSelectionRepairSupported") is True,
            "instant_selection_schema_version":
                _int(response.get("instantSelectionSchemaVersion")),
            "product_ui_selection_supported":
                response.get("productUiSelectionSupported") is True,
            "pre_submit_network_classification_supported":
                response.get("preSubmitNetworkClassificationSupported") is True,
            "conversation_write_boundary_supported":
                response.get("conversationWriteBoundarySupported") is True,
        }

    def instant_selection_for_lease(self, lease_id: str) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        lease_id = lease_id.strip()
        response = self._characterization_rpc(
            {
                "characterizeInstantSelectionRecord": True,
                "expectedBrowserAuthorityLeaseId": lease_id,
                "timeoutMs": 3000,
            },
            timeout=max(1.0, self.connect_timeout),
        )
        if response.get("instantSelectionRepairSupported") is not True:
            raise RequestError(
                "PR8_8_INSTANT_SELECTION_NOT_SUPPORTED",
                request_stage="instant_selection_characterization",
            )
        if response.get("instantSelectionLeaseId") != lease_id:
            raise RequestError(
                "PR8_8_INSTANT_SELECTION_LEASE_MISMATCH",
                request_stage="instant_selection_characterization",
            )
        if _int(response.get("instantSelectionSchemaVersion")) != INSTANT_SELECTION_SCHEMA:
            raise RequestError(
                "PR8_8_INSTANT_SELECTION_SCHEMA_MISMATCH",
                request_stage="instant_selection_characterization",
            )

        return {
            "instant_selection_lease_id": lease_id,
            "instant_selection_schema_version": INSTANT_SELECTION_SCHEMA,
            "requested_model_mode": _string(response.get("requestedModelMode")),
            "selected_mode_before_selection":
                _string(response.get("selectedModeBeforeSelection")),
            "selected_mode_before_selection_proven":
                response.get("selectedModeBeforeSelectionProven") is True,
            "selected_mode_before_selection_proof_kind":
                _string(response.get("selectedModeBeforeSelectionProofKind")),
            "selected_mode_before_selection_candidate_count":
                _int(response.get("selectedModeBeforeSelectionCandidateCount")) or 0,
            "selection_performed": response.get("selectionPerformed") is True,
            "selection_elapsed_ms": _int(response.get("selectionElapsedMs")),
            "selection_mutation_elapsed_ms":
                _int(response.get("selectionMutationElapsedMs")),
            "picker_mode_before_click": _string(response.get("pickerModeBeforeClick")),
            "picker_candidate_count": _int(response.get("pickerCandidateCount")) or 0,
            "picker_nearest_distance_px":
                _int(response.get("pickerNearestDistancePx")),
            "instant_option_candidate_count":
                _int(response.get("instantOptionCandidateCount")) or 0,
            "selected_mode_after_selection":
                _string(response.get("selectedModeAfterSelection")),
            "selected_mode_after_selection_proven":
                response.get("selectedModeAfterSelectionProven") is True,
            "selected_mode_after_selection_proof_kind":
                _string(response.get("selectedModeAfterSelectionProofKind")),
            "selection_complete": response.get("selectionComplete") is True,
            "conversation_write_boundary_observed":
                response.get("conversationWriteBoundaryObserved") is True,
            "unexpected_conversation_write_before_selection_complete":
                response.get("unexpectedConversationWriteBeforeSelectionComplete") is True,
            "conversation_write_count_during_selection":
                _int(response.get("conversationWriteCountDuringSelection")) or 0,
            "network_request_count_during_selection":
                _int(response.get("networkRequestCountDuringSelection")) or 0,
            "chatgpt_request_count_during_selection":
                _int(response.get("chatgptRequestCountDuringSelection")) or 0,
            "chatgpt_mutating_non_conversation_request_count":
                _int(response.get("chatgptMutatingNonConversationRequestCount")) or 0,
            "setting_like_mutation_observed":
                response.get("settingLikeMutationObserved") is True,
            "request_classes": _list_of_strings(response.get("requestClasses")),
            "model_selection_materialization_status":
                _string(response.get("modelSelectionMaterializationStatus"))
                or "INCONCLUSIVE",
        }


class InstantSelectionRepairLatencyRunner(InstantModePhaseLatencyRunner):
    """Instant latency runner that repairs fresh-tab picker state before input.

    Fresh runtime tabs are allowed to hydrate in any proven composer-local mode.
    For each leased Instant characterization turn, the extension materializes
    Instant in that same runtime tab before prompt insertion. The existing
    Instant observer then independently proves Instant immediately before write.
    """

    def __init__(
        self,
        runtime: Any,
        *,
        provider: InstantSelectionRepairProvider,
        **kwargs: Any,
    ) -> None:
        super().__init__(runtime, provider=provider, **kwargs)
        self.provider = provider

    @staticmethod
    def _validate_preflight_mode(record: dict[str, Any], conversation: str) -> None:
        # Fresh-tab mode is characterization evidence, not a conversation-level
        # invariant. The repair intentionally accepts HIGH/MEDIUM/etc. as long
        # as the UI observation itself is proven and the disposable probe stays
        # zero-write/closed/non-disruptive.
        if record.get("conversation_id") != conversation:
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_CONVERSATION_MISMATCH")
        if record.get("conversation_write_count") != 0:
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_WROTE_TO_CONVERSATION")
        if (
            record.get("selected_mode_proven") is not True
            or not isinstance(record.get("selected_mode"), str)
            or not record.get("selected_mode")
        ):
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_MODE_NOT_PROVEN")
        if record.get("probe_tab_closed") is not True or record.get("runtime_tab_id_after") is not None:
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_RUNTIME_TAB_NOT_RESTORED_CLOSED")
        if record.get("debugger_attached_after") is True:
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_DEBUGGER_LEAK")
        if record.get("foreground_activation_observed") is True:
            raise RuntimeError("PR8_8_INSTANT_REPAIR_PREFLIGHT_FOREGROUND_DISTURBANCE")

    @staticmethod
    def _validate_selection_record(record: dict[str, Any], *, phase: str) -> None:
        if record.get("requested_model_mode") != "INSTANT":
            raise RuntimeError(f"{phase}:SELECTION_REQUIREMENT_NOT_RECORDED")
        if record.get("selected_mode_before_selection_proven") is not True:
            raise RuntimeError(f"{phase}:INITIAL_FRESH_TAB_MODE_NOT_PROVEN")
        if record.get("selection_complete") is not True:
            raise RuntimeError(f"{phase}:INSTANT_SELECTION_NOT_COMPLETE")
        if record.get("selected_mode_after_selection_proven") is not True:
            raise RuntimeError(f"{phase}:INSTANT_AFTER_SELECTION_NOT_PROVEN")
        if record.get("selected_mode_after_selection") != "INSTANT":
            raise RuntimeError(f"{phase}:INSTANT_SELECTION_DID_NOT_MATERIALIZE")
        if record.get("unexpected_conversation_write_before_selection_complete") is True:
            raise RuntimeError(f"{phase}:CONVERSATION_WRITE_OCCURRED_DURING_SELECTION")
        if record.get("conversation_write_count_during_selection") != 0:
            raise RuntimeError(f"{phase}:CONVERSATION_WRITE_COUNT_DURING_SELECTION_NONZERO")

        before = record.get("selected_mode_before_selection")
        performed = record.get("selection_performed") is True
        if before == "INSTANT" and performed:
            raise RuntimeError(f"{phase}:REDUNDANT_INSTANT_SELECTION_RECORDED")
        if before != "INSTANT" and not performed:
            raise RuntimeError(f"{phase}:REQUIRED_INSTANT_SELECTION_NOT_PERFORMED")
        if performed and record.get("conversation_write_boundary_observed") is not True:
            raise RuntimeError(f"{phase}:POST_SELECTION_CONVERSATION_BOUNDARY_NOT_OBSERVED")

    def _turn(self, *args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        cid, turn = super()._turn(*args, **kwargs)
        lease_id = turn["observation"].get("browser_authority_lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise RuntimeError("PR8_8_INSTANT_REPAIR:LEASE_ID_MISSING")
        selection = self.provider.instant_selection_for_lease(lease_id)
        phase = f"PR8_8_INSTANT_REPAIR_{str(turn.get('phase', 'turn')).upper()}"
        self._validate_selection_record(selection, phase=phase)
        turn["instant_selection"] = selection
        return cid, turn

    @staticmethod
    def _selection_summary(cycles: list[dict[str, Any]]) -> dict[str, Any]:
        records = [
            cycle[key]["instant_selection"]
            for cycle in cycles
            for key in ("cold_turn", "warm_turn", "close_turn")
        ]
        cold = [cycle["cold_turn"]["instant_selection"] for cycle in cycles]
        warm = [cycle["warm_turn"]["instant_selection"] for cycle in cycles]
        close = [cycle["close_turn"]["instant_selection"] for cycle in cycles]
        performed = [record for record in records if record["selection_performed"]]

        status_counts = Counter(
            record["model_selection_materialization_status"] for record in performed
        )
        initial_mode_counts = Counter(
            record["selected_mode_before_selection"] for record in records
        )
        cold_initial_mode_counts = Counter(
            record["selected_mode_before_selection"] for record in cold
        )

        return {
            "turn_count": len(records),
            "initial_mode_counts": dict(sorted(initial_mode_counts.items())),
            "cold_fresh_tab_initial_mode_counts":
                dict(sorted(cold_initial_mode_counts.items())),
            "selection_performed_count":
                sum(record["selection_performed"] for record in records),
            "cold_selection_performed_count":
                sum(record["selection_performed"] for record in cold),
            "warm_selection_performed_count":
                sum(record["selection_performed"] for record in warm),
            "close_selection_performed_count":
                sum(record["selection_performed"] for record in close),
            "all_turns_instant_after_selection":
                all(
                    record["selected_mode_after_selection"] == "INSTANT"
                    and record["selected_mode_after_selection_proven"] is True
                    for record in records
                ),
            "conversation_write_count_during_selection_total":
                sum(record["conversation_write_count_during_selection"] for record in records),
            "unexpected_conversation_write_before_selection_complete_count":
                sum(
                    record["unexpected_conversation_write_before_selection_complete"]
                    for record in records
                ),
            "selection_elapsed_ms":
                _stats(record["selection_elapsed_ms"] for record in records),
            "selection_mutation_elapsed_ms":
                _stats(record["selection_mutation_elapsed_ms"] for record in performed),
            "network_request_count_during_selection":
                _stats(record["network_request_count_during_selection"] for record in performed),
            "chatgpt_request_count_during_selection":
                _stats(record["chatgpt_request_count_during_selection"] for record in performed),
            "chatgpt_mutating_non_conversation_request_count":
                _stats(
                    record["chatgpt_mutating_non_conversation_request_count"]
                    for record in performed
                ),
            "setting_like_mutation_observed_count":
                sum(record["setting_like_mutation_observed"] for record in performed),
            "materialization_status_counts": dict(sorted(status_counts.items())),
            "request_classes_observed": sorted(
                {
                    request_class
                    for record in performed
                    for request_class in record["request_classes"]
                }
            ),
            "scope_note": (
                "network classification covers the product-UI selection window until "
                "the real conversation POST boundary; raw URLs/payloads are not exported"
            ),
        }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        # Verify the new layer before the parent runner can spend the first write.
        try:
            selection_support = self.provider.instant_selection_support()
        except Exception as error:
            return {
                "ok": False,
                "pr": "PR8.8",
                "probe_context": "instant_fresh_tab_selection_repair_preflight",
                "automatic_write_retry": False,
                "write_attempts": 0,
                "write_completions": 0,
                "failure_phase": "instant_selection_repair_support_preflight",
                "failure": self._failure(
                    RuntimeError("PR8_8_INSTANT_SELECTION_REPAIR_EXTENSION_RELOAD_REQUIRED")
                ),
            }

        if (
            selection_support["instant_selection_repair_supported"] is not True
            or selection_support["instant_selection_schema_version"]
            != INSTANT_SELECTION_SCHEMA
            or selection_support["product_ui_selection_supported"] is not True
            or selection_support["pre_submit_network_classification_supported"] is not True
            or selection_support["conversation_write_boundary_supported"] is not True
        ):
            return {
                "ok": False,
                "pr": "PR8.8",
                "probe_context": "instant_fresh_tab_selection_repair_preflight",
                "automatic_write_retry": False,
                "write_attempts": 0,
                "write_completions": 0,
                "instant_selection_repair_support": selection_support,
                "failure_phase": "instant_selection_repair_support_preflight",
                "failure": self._failure(
                    RuntimeError("PR8_8_INSTANT_SELECTION_REPAIR_SUPPORT_NOT_AVAILABLE")
                ),
            }

        report = super().run(**kwargs)
        report["probe_context"] = (
            "instant_fresh_tab_selection_materialization_phase_latency"
        )
        report["instant_selection_repair_support"] = selection_support
        report["fresh_tab_mode_is_conversation_invariant"] = False
        report["fresh_tab_mode_policy"] = (
            "observe fresh-tab mode; materialize Instant in the same runtime tab "
            "before prompt insertion; never assume conversation identity carries picker state"
        )

        preflight = report.get("selected_mode_preflight")
        if isinstance(preflight, dict):
            report["fresh_tab_mode_preflight"] = dict(preflight)

        if report.get("ok") is not True:
            return report

        selection_summary = self._selection_summary(report["cycles"])
        report["instant_selection_materialization"] = selection_summary

        summary = report.setdefault("summary", {})
        preflight_mode = (
            preflight.get("selected_mode")
            if isinstance(preflight, dict)
            else None
        )
        summary["exact_conversation_instant_preflight_proven"] = (
            preflight_mode == "INSTANT"
            and isinstance(preflight, dict)
            and preflight.get("selected_mode_proven") is True
        )
        summary["fresh_tab_mode_preflight_proven"] = (
            isinstance(preflight, dict)
            and preflight.get("selected_mode_proven") is True
        )
        summary["fresh_tab_mode_preflight_selected_mode"] = preflight_mode
        summary["instant_materialized_before_every_write"] = (
            selection_summary["all_turns_instant_after_selection"]
        )
        summary["conversation_writes_during_model_selection"] = (
            selection_summary["conversation_write_count_during_selection_total"]
        )
        summary["cold_selection_performed_count"] = (
            selection_summary["cold_selection_performed_count"]
        )
        summary["warm_selection_performed_count"] = (
            selection_summary["warm_selection_performed_count"]
        )
        summary["selection_setting_like_mutation_observed_count"] = (
            selection_summary["setting_like_mutation_observed_count"]
        )
        summary["fresh_tab_picker_state_not_assumed_from_conversation"] = True

        cross_mode = report.setdefault("cross_mode_governance", {})
        cross_mode["fresh_tab_picker_state_not_assumed_from_conversation"] = True
        cross_mode["instant_product_ui_materialization_performed"] = (
            selection_summary["selection_performed_count"] > 0
        )
        cross_mode["model_selection_network_evidence_is_descriptive_only"] = True
        return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PR8.8 fresh-tab Instant product-UI materialization and phase-level "
            "latency characterization"
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--replications", type=int, default=DEFAULT_REPLICATIONS)
    parser.add_argument(
        "--disposal-wait-timeout",
        type=float,
        default=DEFAULT_DISPOSAL_WAIT_SECONDS,
    )
    parser.add_argument(
        "--closed-stability-ms",
        type=int,
        default=DEFAULT_CLOSED_STABILITY_MS,
    )
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument(
        "--confirm-instant-auto-switch-disabled",
        action="store_true",
        help=(
            "required: confirm ChatGPT setting that allows Instant to auto-switch "
            "to deeper reasoning is disabled"
        ),
    )
    args = parser.parse_args()

    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required because this runner performs "
            "real ChatGPT product writes"
        )
    if not args.confirm_instant_auto_switch_disabled:
        parser.error(
            "--confirm-instant-auto-switch-disabled is required after disabling "
            "Instant auto-switch in ChatGPT settings"
        )

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = InstantSelectionRepairProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    runner = InstantSelectionRepairLatencyRunner(runtime, provider=provider)
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
