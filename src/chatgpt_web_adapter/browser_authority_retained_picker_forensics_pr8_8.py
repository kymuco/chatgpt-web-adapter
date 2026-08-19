from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .browser_authority_instant_selection_repair_pr8_8 import (
    InstantSelectionRepairProvider,
)
from .browser_authority_instant_latency_pr8_8 import _bool, _list_of_strings, _string
from .browser_authority_phase_cost_attribution_pr8_8 import _int
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

RETAINED_PICKER_FORENSICS_SCHEMA = 1
DEFAULT_FORENSICS_TIMEOUT = 20.0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bounded_list_of_dicts(value: Any, limit: int = 80) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


class RetainedPickerForensicsProvider(InstantSelectionRepairProvider):
    """PR8.8 read-only retained-tab picker topology characterization."""

    def retained_picker_forensics_support(self) -> dict[str, Any]:
        response = self._characterization_rpc(
            {
                "characterizeRetainedPickerForensicsSupport": True,
                "timeoutMs": 3000,
            },
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "retained_picker_forensics_supported":
                response.get("retainedPickerForensicsSupported") is True,
            "retained_picker_forensics_schema_version":
                _int(response.get("retainedPickerForensicsSchemaVersion")),
            "retained_existing_tab_probe_supported":
                response.get("retainedExistingTabProbeSupported") is True,
            "dom_topology_supported": response.get("domTopologySupported") is True,
            "accessibility_topology_supported":
                response.get("accessibilityTopologySupported") is True,
            "conversation_write_guard_supported":
                response.get("conversationWriteGuardSupported") is True,
            "fenced_reconciliation_close_supported":
                response.get("fencedReconciliationCloseSupported") is True,
            "zero_product_writes": response.get("zeroProductWrites") is True,
        }

    def retained_picker_surface_forensics(
        self,
        conversation: str,
        *,
        expected_runtime_tab_id: int,
        timeout: float = DEFAULT_FORENSICS_TIMEOUT,
    ) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if (
            isinstance(expected_runtime_tab_id, bool)
            or not isinstance(expected_runtime_tab_id, int)
            or expected_runtime_tab_id <= 0
        ):
            raise ValueError("expected_runtime_tab_id must be a positive int")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        response = self._characterization_rpc(
            {
                "characterizeRetainedPickerSurfaceForensics": True,
                "conversationId": conversation.strip(),
                "expectedRuntimeTabId": expected_runtime_tab_id,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if response.get("retainedPickerForensicsSupported") is not True:
            raise RequestError(
                "PR8_8_RETAINED_PICKER_FORENSICS_NOT_SUPPORTED",
                request_stage="retained_picker_forensics",
            )
        if _int(response.get("retainedPickerForensicsSchemaVersion")) != RETAINED_PICKER_FORENSICS_SCHEMA:
            raise RequestError(
                "PR8_8_RETAINED_PICKER_FORENSICS_SCHEMA_MISMATCH",
                request_stage="retained_picker_forensics",
            )

        dom = _dict(response.get("domTopology"))
        ax = _dict(response.get("accessibilityTopology"))
        return {
            "conversation_id": _string(response.get("conversationId")),
            "expected_runtime_tab_id": _int(response.get("expectedRuntimeTabId")),
            "runtime_tab_id": _int(response.get("runtimeTabId")),
            "runtime_tab_id_after": _int(response.get("runtimeTabIdAfter")),
            "runtime_tab_retained": response.get("runtimeTabRetained") is True,
            "browser_authority_lease_id": _string(response.get("browserAuthorityLeaseId")),
            "lease_id_present": response.get("leaseIdPresent") is True,
            "zero_product_writes": response.get("zeroProductWrites") is True,
            "conversation_write_count": _int(response.get("conversationWriteCount")) or 0,
            "tab_was_active": _bool(response.get("tabWasActive")),
            "tab_active_after": _bool(response.get("tabActiveAfter")),
            "tab_activated_during_probe": response.get("tabActivatedDuringProbe") is True,
            "foreground_activation_observed": response.get("foregroundActivationObserved") is True,
            "debugger_attached_before": _bool(response.get("debuggerAttachedBefore")),
            "debugger_attached_after": _bool(response.get("debuggerAttachedAfter")),
            "picker_surface_open": response.get("pickerSurfaceOpen") is True,
            "instant_dom_candidate_count": _int(response.get("instantDomCandidateCount")) or 0,
            "instant_ax_candidate_count": _int(response.get("instantAxCandidateCount")) or 0,
            "recognized_modes": _list_of_strings(response.get("recognizedModes")),
            "dom_topology": {
                "composer_ready": dom.get("composerReady") is True,
                "picker_control": _dict(dom.get("pickerControl")),
                "popup_surface_open": dom.get("popupSurfaceOpen") is True,
                "popup_surfaces": _bounded_list_of_dicts(dom.get("popupSurfaces"), 24),
                "dom_candidates": _bounded_list_of_dicts(dom.get("domCandidates"), 80),
                "recognized_modes": _list_of_strings(dom.get("recognizedModes")),
                "instant_dom_candidate_count": _int(dom.get("instantDomCandidateCount")) or 0,
                "scanned_visible_element_count": _int(dom.get("scannedVisibleElementCount")) or 0,
            },
            "accessibility_topology": {
                "candidate_count": _int(ax.get("candidateCount")) or 0,
                "instant_candidate_count": _int(ax.get("instantCandidateCount")) or 0,
                "recognized_modes": _list_of_strings(ax.get("recognizedModes")),
                "candidates": _bounded_list_of_dicts(ax.get("candidates"), 80),
            },
        }


class RetainedPickerForensicsRunner:
    """Zero-product-write forensics for one retained failed-picker runtime tab."""

    def __init__(self, runtime: Any, *, provider: RetainedPickerForensicsProvider) -> None:
        self.runtime = runtime
        self.provider = provider

    @staticmethod
    def _failure(error: BaseException) -> dict[str, Any]:
        return {
            "type": type(error).__name__,
            "message": str(error),
            "automatic_retry_attempted": False,
        }

    @staticmethod
    def _health_record(health: Any) -> dict[str, Any]:
        to_dict = getattr(health, "to_dict", None)
        return to_dict() if callable(to_dict) else {}

    @staticmethod
    def _validate_forensics(record: dict[str, Any], *, conversation: str, tab_id: int) -> None:
        if record.get("conversation_id") != conversation:
            raise RuntimeError("PR8_8_FORENSICS_CONVERSATION_MISMATCH")
        if record.get("runtime_tab_id") != tab_id or record.get("runtime_tab_id_after") != tab_id:
            raise RuntimeError("PR8_8_FORENSICS_RUNTIME_TAB_CHANGED")
        if record.get("runtime_tab_retained") is not True:
            raise RuntimeError("PR8_8_FORENSICS_RUNTIME_TAB_NOT_RETAINED")
        if record.get("zero_product_writes") is not True or record.get("conversation_write_count") != 0:
            raise RuntimeError("PR8_8_FORENSICS_ZERO_WRITE_BOUNDARY_VIOLATED")
        if record.get("tab_activated_during_probe") is True:
            raise RuntimeError("PR8_8_FORENSICS_FOREGROUND_ACTIVATION_OCCURRED")
        if record.get("debugger_attached_before") is True:
            raise RuntimeError("PR8_8_FORENSICS_DEBUGGER_WAS_ALREADY_ATTACHED")
        if record.get("debugger_attached_after") is True:
            raise RuntimeError("PR8_8_FORENSICS_DEBUGGER_LEAK")
        if record.get("lease_id_present") is not True or not record.get("browser_authority_lease_id"):
            raise RuntimeError("PR8_8_FORENSICS_LEASE_FENCE_NOT_AVAILABLE")

    def run(
        self,
        *,
        conversation: str,
        expected_runtime_tab_id: int,
        timeout: float = DEFAULT_FORENSICS_TIMEOUT,
        reconcile_close_after_forensics: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        conversation = conversation.strip()
        if (
            isinstance(expected_runtime_tab_id, bool)
            or not isinstance(expected_runtime_tab_id, int)
            or expected_runtime_tab_id <= 0
        ):
            raise ValueError("expected_runtime_tab_id must be a positive int")

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "retained_failed_picker_surface_forensics_zero_write_reconciliation",
            "conversation": conversation,
            "expected_runtime_tab_id": expected_runtime_tab_id,
            "product_write_budget": 0,
            "write_attempts": 0,
            "write_completions": 0,
            "automatic_write_retry": False,
            "reconcile_close_requested": bool(reconcile_close_after_forensics),
            "reconcile_close_performed": False,
            "failure_phase": None,
            "failure": None,
        }
        phase = "forensics_support_preflight"
        try:
            support = self.provider.retained_picker_forensics_support()
            report["forensics_support"] = support
            if (
                support["retained_picker_forensics_supported"] is not True
                or support["retained_picker_forensics_schema_version"] != RETAINED_PICKER_FORENSICS_SCHEMA
                or support["retained_existing_tab_probe_supported"] is not True
                or support["dom_topology_supported"] is not True
                or support["accessibility_topology_supported"] is not True
                or support["conversation_write_guard_supported"] is not True
                or support["fenced_reconciliation_close_supported"] is not True
                or support["zero_product_writes"] is not True
            ):
                raise RuntimeError("PR8_8_FORENSICS_EXTENSION_RELOAD_REQUIRED")

            phase = "retained_runtime_preflight"
            status = self.provider.characterization_status()
            report["initial_authority_status"] = status.to_dict()
            if not status.supported or not status.runtime_tab_release_supported:
                raise RuntimeError("PR8_8_FORENSICS_BROWSER_AUTHORITY_SUPPORT_UNAVAILABLE")
            if status.runtime_tab_id != expected_runtime_tab_id:
                raise RuntimeError("PR8_8_FORENSICS_EXPECTED_RETAINED_TAB_NOT_PRESENT")
            if status.lease_id_present is not True:
                raise RuntimeError("PR8_8_FORENSICS_RETAINED_LEASE_METADATA_MISSING")

            health = self.runtime.health(conversation)
            report["initial_runtime_health"] = self._health_record(health)
            if health.ready is not True or health.canonical_status != "completed":
                raise RuntimeError("PR8_8_FORENSICS_CANONICAL_CONVERSATION_NOT_STABLE_COMPLETED")
            if getattr(health, "runtime_tab_id", expected_runtime_tab_id) != expected_runtime_tab_id:
                raise RuntimeError("PR8_8_FORENSICS_HEALTH_RUNTIME_TAB_MISMATCH")

            phase = "retained_picker_surface_forensics"
            forensic = self.provider.retained_picker_surface_forensics(
                conversation,
                expected_runtime_tab_id=expected_runtime_tab_id,
                timeout=timeout,
            )
            report["forensics"] = forensic
            self._validate_forensics(forensic, conversation=conversation, tab_id=expected_runtime_tab_id)

            phase = "post_forensics_canonical_recheck"
            post_health = self.runtime.health(conversation)
            report["post_forensics_runtime_health"] = self._health_record(post_health)
            if post_health.ready is not True or post_health.canonical_status != "completed":
                raise RuntimeError("PR8_8_FORENSICS_POST_PROBE_CANONICAL_STATE_CHANGED")
            post_status = self.provider.status()
            report["post_forensics_bridge_status"] = {
                "available": post_status.available,
                "extension_connected": post_status.extension_connected,
                "runtime_tab_id": post_status.runtime_tab_id,
            }
            if post_status.runtime_tab_id != expected_runtime_tab_id:
                raise RuntimeError("PR8_8_FORENSICS_POST_PROBE_RUNTIME_TAB_CHANGED")

            report["topology_summary"] = {
                "picker_surface_open": forensic["picker_surface_open"],
                "recognized_modes": forensic["recognized_modes"],
                "instant_dom_candidate_count": forensic["instant_dom_candidate_count"],
                "instant_ax_candidate_count": forensic["instant_ax_candidate_count"],
                "dom_candidate_count": len(forensic["dom_topology"]["dom_candidates"]),
                "ax_candidate_count": forensic["accessibility_topology"]["candidate_count"],
                "popup_surface_count": len(forensic["dom_topology"]["popup_surfaces"]),
                "evidence_scope": (
                    "bounded normalized DOM/Accessibility topology only; no raw DOM/HTML, "
                    "raw labels, prompt text, response text, cookies, or auth material exported"
                ),
            }

            if reconcile_close_after_forensics:
                phase = "fenced_reconciliation_close"
                lease_id = forensic["browser_authority_lease_id"]
                release = self.provider.release_runtime_tab(
                    expected_runtime_tab_id=expected_runtime_tab_id,
                    browser_authority_lease_id=lease_id,
                    timeout=10.0,
                )
                report["reconciliation_close"] = {
                    "released": release.released,
                    "already_absent": release.already_absent,
                    "runtime_tab_id": release.runtime_tab_id,
                    "browser_authority_lease_id": release.browser_authority_lease_id,
                    "automatic_retry": False,
                }
                final_status = self.provider.status()
                report["final_bridge_status"] = {
                    "available": final_status.available,
                    "extension_connected": final_status.extension_connected,
                    "runtime_tab_id": final_status.runtime_tab_id,
                }
                if final_status.runtime_tab_id is not None:
                    raise RuntimeError("PR8_8_FORENSICS_RECONCILIATION_CLOSE_NOT_CONFIRMED")
                final_health = self.runtime.health(conversation)
                report["final_runtime_health"] = self._health_record(final_health)
                if final_health.ready is not True or final_health.canonical_status != "completed":
                    raise RuntimeError("PR8_8_FORENSICS_CANONICAL_STATE_CHANGED_AFTER_CLOSE")
                report["reconcile_close_performed"] = True

            report["reconciliation_governance"] = {
                "product_writes_performed": 0,
                "automatic_retry_attempted": False,
                "retained_tab_inspected_before_any_close": True,
                "canonical_completed_required_before_forensics": True,
                "canonical_completed_rechecked_after_forensics": True,
                "close_requires_explicit_cli_opt_in": True,
                "close_uses_exact_runtime_tab_fence": True,
                "close_uses_stored_browser_authority_lease_fence": True,
                "close_is_browser_resource_lifecycle_only": True,
                "conversation_identity_not_mutated": True,
                "temporary_mode_boundary_preserved": True,
            }
            report["summary"] = {
                "retained_failed_picker_forensics_completed": True,
                "zero_product_writes": True,
                "exact_retained_runtime_tab_fenced": True,
                "canonical_conversation_stable_completed": True,
                "dom_topology_captured": True,
                "accessibility_topology_captured": True,
                "conversation_write_guard_clean": True,
                "debugger_detached_after_probe": True,
                "retained_tab_left_untouched": not reconcile_close_after_forensics,
                "fenced_reconciliation_close_performed": bool(reconcile_close_after_forensics),
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
            "PR8.8 retained failed-picker DOM/Accessibility forensics with zero product writes"
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--expected-runtime-tab-id", type=int, required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_FORENSICS_TIMEOUT)
    parser.add_argument(
        "--reconcile-close-after-forensics",
        action="store_true",
        help=(
            "after a successful zero-write forensic snapshot and canonical recheck, "
            "close only the exact retained runtime tab using its stored lease fence"
        ),
    )
    args = parser.parse_args()

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=True,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = RetainedPickerForensicsProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    runner = RetainedPickerForensicsRunner(runtime, provider=provider)
    report = runner.run(
        conversation=args.conversation,
        expected_runtime_tab_id=args.expected_runtime_tab_id,
        timeout=args.timeout,
        reconcile_close_after_forensics=args.reconcile_close_after_forensics,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
