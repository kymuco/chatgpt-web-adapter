from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .browser_authority_instant_latency_pr8_8 import _bool, _string
from .browser_authority_phase_cost_attribution_pr8_8 import _int
from .browser_authority_retained_picker_forensics_pr8_8 import (
    RetainedPickerForensicsProvider,
    RetainedPickerForensicsRunner,
)
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

SCHEMA = 1
DEFAULT_TIMEOUT = 10.0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class RetainedRouteIdentityProvider(RetainedPickerForensicsProvider):
    def retained_route_identity_support(self) -> dict[str, Any]:
        r = self._characterization_rpc(
            {"characterizeRetainedRouteIdentitySupport": True, "timeoutMs": 3000},
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "retained_route_identity_supported": r.get("retainedRouteIdentitySupported") is True,
            "retained_route_identity_schema_version": _int(r.get("retainedRouteIdentitySchemaVersion")),
            "retained_existing_tab_route_probe_supported": r.get("retainedExistingTabRouteProbeSupported") is True,
            "conversation_mismatch_characterization_supported": r.get("conversationMismatchCharacterizationSupported") is True,
            "route_mismatch_dom_ax_suppression_supported": r.get("routeMismatchDomAxSuppressionSupported") is True,
            "raw_route_redaction_supported": r.get("rawRouteRedactionSupported") is True,
            "exact_match_surface_forensics_delegation_supported": r.get("exactMatchSurfaceForensicsDelegationSupported") is True,
            "zero_product_writes": r.get("zeroProductWrites") is True,
        }

    @staticmethod
    def _route(value: Any) -> dict[str, Any]:
        r = _dict(value)
        return {
            "route_kind": _string(r.get("routeKind")),
            "observed_conversation_id": _string(r.get("observedConversationId")),
            "expected_conversation_id": _string(r.get("expectedConversationId")),
            "conversation_matches_expected": r.get("conversationMatchesExpected") is True,
            "route_identity_status": _string(r.get("routeIdentityStatus")),
            "raw_url_exported": r.get("rawUrlExported") is True,
            "query_exported": r.get("queryExported") is True,
            "fragment_exported": r.get("fragmentExported") is True,
        }

    def retained_route_identity_forensics(self, conversation: str, *, expected_runtime_tab_id: int, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if isinstance(expected_runtime_tab_id, bool) or not isinstance(expected_runtime_tab_id, int) or expected_runtime_tab_id <= 0:
            raise ValueError("expected_runtime_tab_id must be a positive int")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        r = self._characterization_rpc(
            {
                "characterizeRetainedRouteIdentity": True,
                "conversationId": conversation.strip(),
                "expectedRuntimeTabId": expected_runtime_tab_id,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if r.get("retainedRouteIdentitySupported") is not True:
            raise RequestError("PR8_8_RETAINED_ROUTE_IDENTITY_NOT_SUPPORTED", request_stage="retained_route_identity")
        if _int(r.get("retainedRouteIdentitySchemaVersion")) != SCHEMA:
            raise RequestError("PR8_8_RETAINED_ROUTE_IDENTITY_SCHEMA_MISMATCH", request_stage="retained_route_identity")
        return {
            "conversation_id": _string(r.get("conversationId")),
            "expected_runtime_tab_id": _int(r.get("expectedRuntimeTabId")),
            "runtime_tab_id": _int(r.get("runtimeTabId")),
            "runtime_tab_id_after": _int(r.get("runtimeTabIdAfter")),
            "runtime_tab_retained": r.get("runtimeTabRetained") is True,
            "browser_authority_lease_id": _string(r.get("browserAuthorityLeaseId")),
            "lease_id_present": r.get("leaseIdPresent") is True,
            "zero_product_writes": r.get("zeroProductWrites") is True,
            "route_identity": self._route(r.get("routeIdentity")),
            "route_identity_after": self._route(r.get("routeIdentityAfter")),
            "route_identity_stable": r.get("routeIdentityStable") is True,
            "route_mismatch_characterized": r.get("routeMismatchCharacterized") is True,
            "dom_ax_inspection_performed": r.get("domAxInspectionPerformed") is True,
            "conversation_write_guard_observed": r.get("conversationWriteGuardObserved") is True,
            "conversation_write_count": _int(r.get("conversationWriteCount")),
            "tab_was_active": _bool(r.get("tabWasActive")),
            "tab_active_after": _bool(r.get("tabActiveAfter")),
            "tab_activated_during_probe": r.get("tabActivatedDuringProbe") is True,
            "foreground_activation_observed": r.get("foregroundActivationObserved") is True,
            "debugger_attached_before": _bool(r.get("debuggerAttachedBefore")),
            "debugger_attached_after": _bool(r.get("debuggerAttachedAfter")),
        }


class RetainedRouteIdentityRunner:
    def __init__(self, runtime: Any, *, provider: RetainedRouteIdentityProvider) -> None:
        self.runtime = runtime
        self.provider = provider

    @staticmethod
    def _health(health: Any) -> dict[str, Any]:
        fn = getattr(health, "to_dict", None)
        return fn() if callable(fn) else {}

    @staticmethod
    def _validate(record: dict[str, Any], conversation: str, tab_id: int) -> None:
        _require(record.get("conversation_id") == conversation, "PR8_8_ROUTE_EXPECTED_CONVERSATION_RECORD_MISMATCH")
        _require(record.get("runtime_tab_id") == tab_id == record.get("runtime_tab_id_after"), "PR8_8_ROUTE_RUNTIME_TAB_CHANGED")
        _require(record.get("runtime_tab_retained") is True, "PR8_8_ROUTE_RUNTIME_TAB_NOT_RETAINED")
        _require(record.get("zero_product_writes") is True, "PR8_8_ROUTE_ZERO_WRITE_BOUNDARY_VIOLATED")
        _require(record.get("lease_id_present") is True and bool(record.get("browser_authority_lease_id")), "PR8_8_ROUTE_LEASE_FENCE_NOT_AVAILABLE")
        _require(record.get("route_identity_stable") is True, "PR8_8_ROUTE_IDENTITY_CHANGED_DURING_PROBE")
        _require(record.get("dom_ax_inspection_performed") is False, "PR8_8_ROUTE_PROBE_UNEXPECTED_DOM_AX_INSPECTION")
        _require(record.get("conversation_write_guard_observed") is False and record.get("conversation_write_count") is None, "PR8_8_ROUTE_PROBE_WRITE_GUARD_INVALID")
        _require(record.get("tab_activated_during_probe") is False, "PR8_8_ROUTE_FOREGROUND_ACTIVATION_OCCURRED")
        _require(record.get("debugger_attached_before") == record.get("debugger_attached_after"), "PR8_8_ROUTE_DEBUGGER_STATE_CHANGED")
        route, after = record.get("route_identity") or {}, record.get("route_identity_after") or {}
        _require(route.get("expected_conversation_id") == conversation, "PR8_8_ROUTE_EXPECTED_CONVERSATION_MISMATCH")
        for item in (route, after):
            _require(not any(item.get(k) is True for k in ("raw_url_exported", "query_exported", "fragment_exported")), "PR8_8_ROUTE_PRIVACY_BOUNDARY_VIOLATED")
        if route.get("conversation_matches_expected") is True:
            _require(route.get("route_kind") == "CONVERSATION" and route.get("observed_conversation_id") == conversation and route.get("route_identity_status") == "EXPECTED_CONVERSATION_MATCH", "PR8_8_ROUTE_MATCHED_IDENTITY_INVALID")
            _require(record.get("route_mismatch_characterized") is False, "PR8_8_ROUTE_FALSE_MISMATCH_CLASSIFICATION")
        else:
            _require(record.get("route_mismatch_characterized") is True, "PR8_8_ROUTE_MISMATCH_NOT_CHARACTERIZED")
            _require(route.get("route_identity_status") in {"OTHER_CONVERSATION", "ROOT_ROUTE", "OTHER_CHATGPT_ROUTE"}, "PR8_8_ROUTE_MISMATCH_STATUS_INVALID")

    def run(self, *, conversation: str, expected_runtime_tab_id: int, timeout: float = DEFAULT_TIMEOUT, reconcile_close_after_forensics: bool = False) -> dict[str, Any]:
        conversation = conversation.strip()
        report = {
            "ok": False, "pr": "PR8.8",
            "probe_context": "retained_runtime_tab_route_identity_forensics_zero_write_evidence_preservation",
            "conversation": conversation, "expected_runtime_tab_id": expected_runtime_tab_id,
            "product_write_budget": 0, "write_attempts": 0, "write_completions": 0,
            "automatic_write_retry": False, "reconcile_close_requested": bool(reconcile_close_after_forensics),
            "reconcile_close_performed": False, "surface_forensics_performed": False,
            "failure_phase": None, "failure": None,
        }
        phase = "route_identity_support_preflight"
        try:
            support = self.provider.retained_route_identity_support()
            report["route_identity_support"] = support
            required = (
                support["retained_route_identity_supported"],
                support["retained_route_identity_schema_version"] == SCHEMA,
                support["retained_existing_tab_route_probe_supported"],
                support["conversation_mismatch_characterization_supported"],
                support["route_mismatch_dom_ax_suppression_supported"],
                support["raw_route_redaction_supported"],
                support["exact_match_surface_forensics_delegation_supported"],
                support["zero_product_writes"],
            )
            _require(all(x is True for x in required), "PR8_8_ROUTE_IDENTITY_EXTENSION_RELOAD_REQUIRED")

            phase = "retained_runtime_preflight"
            status = self.provider.characterization_status()
            report["initial_authority_status"] = status.to_dict()
            _require(status.supported and status.runtime_tab_release_supported, "PR8_8_ROUTE_BROWSER_AUTHORITY_SUPPORT_UNAVAILABLE")
            _require(status.runtime_tab_id == expected_runtime_tab_id, "PR8_8_ROUTE_EXPECTED_RETAINED_TAB_NOT_PRESENT")
            _require(status.lease_id_present is True, "PR8_8_ROUTE_RETAINED_LEASE_METADATA_MISSING")
            health = self.runtime.health(conversation)
            report["initial_runtime_health"] = self._health(health)
            _require(health.ready is True and health.canonical_status == "completed", "PR8_8_ROUTE_CANONICAL_CONVERSATION_NOT_STABLE_COMPLETED")
            _require(getattr(health, "runtime_tab_id", expected_runtime_tab_id) == expected_runtime_tab_id, "PR8_8_ROUTE_HEALTH_RUNTIME_TAB_MISMATCH")

            phase = "retained_route_identity_forensics"
            record = self.provider.retained_route_identity_forensics(conversation, expected_runtime_tab_id=expected_runtime_tab_id, timeout=timeout)
            report["route_identity_forensics"] = record
            self._validate(record, conversation, expected_runtime_tab_id)

            phase = "post_route_canonical_recheck"
            health = self.runtime.health(conversation)
            report["post_route_runtime_health"] = self._health(health)
            _require(health.ready is True and health.canonical_status == "completed", "PR8_8_ROUTE_POST_PROBE_CANONICAL_STATE_CHANGED")
            status = self.provider.status()
            report["post_route_bridge_status"] = {"available": status.available, "extension_connected": status.extension_connected, "runtime_tab_id": status.runtime_tab_id}
            _require(status.runtime_tab_id == expected_runtime_tab_id, "PR8_8_ROUTE_POST_PROBE_RUNTIME_TAB_CHANGED")

            route = record["route_identity"]
            report["route_identity_summary"] = {**route, "route_identity_stable": record["route_identity_stable"], "route_mismatch_characterized": record["route_mismatch_characterized"]}
            if route["conversation_matches_expected"] is not True:
                if reconcile_close_after_forensics:
                    phase = "route_mismatch_close_guard"
                    raise RuntimeError("PR8_8_ROUTE_MISMATCH_CLOSE_FORBIDDEN")
                report["evidence_preservation"] = {"route_mismatch_characterized": True, "dom_ax_surface_forensics_suppressed": True, "retained_tab_preserved": True, "browser_authority_lease_preserved": True, "product_writes_performed": 0}
                report["summary"] = {"route_identity_characterized": True, "conversation_matches_expected": False, "route_mismatch_characterized": True, "surface_forensics_performed": False, "retained_tab_left_untouched": True, "zero_product_writes": True}
                report["ok"] = True
                return report

            phase = "exact_match_surface_forensics_delegation"
            surface = RetainedPickerForensicsRunner(self.runtime, provider=self.provider).run(
                conversation=conversation, expected_runtime_tab_id=expected_runtime_tab_id,
                timeout=timeout, reconcile_close_after_forensics=reconcile_close_after_forensics,
            )
            report["surface_forensics"] = surface
            report["surface_forensics_performed"] = True
            report["reconcile_close_performed"] = surface.get("reconcile_close_performed") is True
            _require(surface.get("ok") is True, f"PR8_8_ROUTE_EXACT_MATCH_SURFACE_FORENSICS_FAILED:{surface.get('failure_phase')}:{_dict(surface.get('failure')).get('message')}")
            report["summary"] = {"route_identity_characterized": True, "conversation_matches_expected": True, "route_mismatch_characterized": False, "surface_forensics_performed": True, "retained_tab_left_untouched": surface.get("summary", {}).get("retained_tab_left_untouched"), "zero_product_writes": True}
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = {"type": type(error).__name__, "message": str(error), "automatic_retry_attempted": False}
            return report


def main() -> int:
    p = argparse.ArgumentParser(description="PR8.8 retained runtime-tab route identity forensics with conditional exact-match picker forensics")
    p.add_argument("--conversation", required=True)
    p.add_argument("--expected-runtime-tab-id", type=int, required=True)
    p.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--reconcile-close-after-forensics", action="store_true")
    a = p.parse_args()
    client = ChatGPTWebClient(auth_file=a.auth_file, auto_refresh_auth=True, auto_login=False, auto_sentinel=False)
    provider = RetainedRouteIdentityProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = RetainedRouteIdentityRunner(runtime, provider=provider).run(
        conversation=a.conversation, expected_runtime_tab_id=a.expected_runtime_tab_id,
        timeout=a.timeout, reconcile_close_after_forensics=a.reconcile_close_after_forensics,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
