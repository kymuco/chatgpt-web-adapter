from __future__ import annotations
import argparse, json
from typing import Any
from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .exceptions import RequestError

SCHEMA = 1
CLEAN = {"ALREADY_CLEAN", "STALE_TAB_METADATA_CLEARED_NO_LEASE", "ORPHAN_LEASE_CLEARED", "STALE_TAB_AND_ORPHAN_LEASE_CLEARED"}

def _i(v: Any) -> int | None: return v if isinstance(v, int) and not isinstance(v, bool) else None
def _s(v: Any) -> str | None: return v if isinstance(v, str) and v else None
def _state(v: Any) -> dict[str, Any]:
    x = v if isinstance(v, dict) else {}
    return {"runtime_tab_id": _i(x.get("runtimeTabId")), "runtime_tab_state": _s(x.get("runtimeTabState")), "lease_id_present": x.get("leaseIdPresent") is True, "live_chatgpt_tab_observed": x.get("liveChatGPTTabObserved") is True}

class OrphanLeaseReconciliationProvider(BrowserAuthorityCharacterizationProvider):
    def orphan_lease_reconciliation_support(self) -> dict[str, Any]:
        r = self._characterization_rpc({"characterizeOrphanLeaseReconciliationSupport": True, "timeoutMs": 3000}, timeout=max(1.0, self.connect_timeout))
        return {"supported": r.get("orphanLeaseReconciliationSupported") is True, "schema": _i(r.get("orphanLeaseReconciliationSchemaVersion")), "serialized": r.get("serializedZeroWriteReconciliationSupported") is True, "lease_fence": r.get("exactLeaseCompareAndClearSupported") is True, "tab_fence": r.get("runtimeTabPresenceFenceSupported") is True, "abstention": r.get("stateChangeAbstentionSupported") is True, "lease_id_exported": r.get("leaseIdExported") is True, "zero_product_writes": r.get("zeroProductWrites") is True, "automatic_retry": r.get("automaticRetry") is True}

    def reconcile_orphaned_browser_authority_lease(self, *, timeout: float = 5.0) -> dict[str, Any]:
        if timeout <= 0: raise ValueError("timeout must be positive")
        r = self._characterization_rpc({"reconcileOrphanedBrowserAuthorityLease": True, "timeoutMs": int(timeout * 1000)}, timeout=timeout)
        if r.get("orphanLeaseReconciliationSupported") is not True: raise RequestError("PR8_8_ORPHAN_LEASE_RECONCILIATION_NOT_SUPPORTED", request_stage="orphan_lease_reconciliation")
        if _i(r.get("orphanLeaseReconciliationSchemaVersion")) != SCHEMA: raise RequestError("PR8_8_ORPHAN_LEASE_RECONCILIATION_SCHEMA_MISMATCH", request_stage="orphan_lease_reconciliation")
        return {"status": _s(r.get("reconciliationStatus")), "initial": _state(r.get("initialState")), "final": _state(r.get("finalState")), "clean_baseline": r.get("cleanBaseline") is True, "lease_id_exported": r.get("leaseIdExported") is True, "zero_product_writes": r.get("zeroProductWrites") is True, "automatic_retry": r.get("automaticRetry") is True, "state_changed_before_commit": r.get("stateChangedBeforeCommit") is True}

class OrphanLeaseReconciliationRunner:
    def __init__(self, *, provider: OrphanLeaseReconciliationProvider): self.provider = provider
    def run(self, *, timeout: float = 5.0) -> dict[str, Any]:
        out = {"ok": False, "pr": "PR8.8", "probe_context": "orphaned_browser_authority_lease_zero_write_clean_baseline", "product_write_budget": 0, "write_attempts": 0, "write_completions": 0, "automatic_write_retry": False, "failure_phase": None, "failure": None}
        phase = "support_preflight"
        try:
            support = self.provider.orphan_lease_reconciliation_support(); out["support"] = support
            if not (support["supported"] and support["schema"] == SCHEMA and support["serialized"] and support["lease_fence"] and support["tab_fence"] and support["abstention"] and not support["lease_id_exported"] and support["zero_product_writes"] and not support["automatic_retry"]): raise RuntimeError("PR8_8_ORPHAN_LEASE_RECONCILIATION_EXTENSION_RELOAD_REQUIRED")
            out["initial_authority_status"] = self.provider.characterization_status().to_dict()
            phase = "reconciliation"
            rec = self.provider.reconcile_orphaned_browser_authority_lease(timeout=timeout); out["reconciliation"] = rec
            phase = "outcome_validation"
            final = self.provider.characterization_status(); out["final_authority_status"] = final.to_dict()
            if rec["status"] not in CLEAN: raise RuntimeError(f"PR8_8_ORPHAN_LEASE_{rec['status'] or 'UNKNOWN'}")
            if not rec["clean_baseline"] or rec["lease_id_exported"] or not rec["zero_product_writes"] or rec["automatic_retry"]: raise RuntimeError("PR8_8_ORPHAN_LEASE_CLEAN_BASELINE_NOT_PROVEN")
            if final.runtime_tab_id is not None or final.lease_id_present: raise RuntimeError("PR8_8_ORPHAN_LEASE_FINAL_STATE_NOT_CLEAN")
            out["summary"] = {"reconciliation_status": rec["status"], "runtime_tab_id": None, "lease_id_present": False, "zero_product_writes": True}; out["ok"] = True
        except Exception as e:
            out["failure_phase"] = phase; out["failure"] = {"type": type(e).__name__, "message": str(e), "automatic_retry_attempted": False}
        return out

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(); p.add_argument("--timeout", type=float, default=5.0); a = p.parse_args(argv)
    r = OrphanLeaseReconciliationRunner(provider=OrphanLeaseReconciliationProvider()).run(timeout=a.timeout); print(json.dumps(r, indent=2)); return 0 if r["ok"] else 1
if __name__ == "__main__": raise SystemExit(main())
