from __future__ import annotations
from types import SimpleNamespace
from chatgpt_web_adapter.browser_authority_orphan_lease_reconciliation_pr8_8 import OrphanLeaseReconciliationRunner
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

class P:
    def __init__(self, status="ORPHAN_LEASE_CLEARED"):
        self.status=status; self.runtime_tab_id=None; self.lease_id_present=True
    def orphan_lease_reconciliation_support(self): return {"supported":True,"schema":1,"serialized":True,"lease_fence":True,"tab_fence":True,"abstention":True,"lease_id_exported":False,"zero_product_writes":True,"automatic_retry":False}
    def characterization_status(self): return SimpleNamespace(runtime_tab_id=self.runtime_tab_id, lease_id_present=self.lease_id_present, to_dict=lambda:{"runtime_tab_id":self.runtime_tab_id,"lease_id_present":self.lease_id_present})
    def reconcile_orphaned_browser_authority_lease(self, *, timeout):
        clean=self.status in {"ALREADY_CLEAN","STALE_TAB_METADATA_CLEARED_NO_LEASE","ORPHAN_LEASE_CLEARED","STALE_TAB_AND_ORPHAN_LEASE_CLEARED"}
        if clean: self.runtime_tab_id=None; self.lease_id_present=False
        return {"status":self.status,"initial":{},"final":{},"clean_baseline":clean,"lease_id_exported":False,"zero_product_writes":True,"automatic_retry":False,"state_changed_before_commit":self.status=="STATE_CHANGED_ABSTAINED"}

def test_extension_worker_is_additive_and_zero_write():
    root=browser_native_extension_dir(); obs=(root/"service_worker_observability.js").read_text(); worker=(root/"service_worker_orphan_lease_reconciliation_pr8_8.js").read_text()
    assert 'importScripts("service_worker_orphan_lease_reconciliation_pr8_8.js")' in obs
    for token in ("reconcileOrphanedBrowserAuthorityLease","STATE_CHANGED_ABSTAINED","LIVE_AUTHORITY_RETAINED","_pr88ClearLeaseIdIfMatches(initial.leaseId)","leaseIdExported: false"): assert token in worker
    for forbidden in ("Input.dispatchMouseEvent","Input.insertText","submitOfficialPageTurn(","executeOfficialPageTurn(","chrome.tabs.create(","chrome.tabs.update(","chrome.tabs.remove(","chrome.debugger.attach("): assert forbidden not in worker

def test_runner_clears_orphan_to_clean_baseline():
    r=OrphanLeaseReconciliationRunner(provider=P()).run(); assert r["ok"] is True; assert r["write_attempts"]==0; assert r["summary"]["runtime_tab_id"] is None; assert r["summary"]["lease_id_present"] is False

def test_runner_is_idempotent_when_clean():
    p=P("ALREADY_CLEAN"); p.lease_id_present=False; assert OrphanLeaseReconciliationRunner(provider=p).run()["ok"] is True

def test_runner_retains_live_authority_and_fails_closed():
    p=P("LIVE_AUTHORITY_RETAINED"); p.runtime_tab_id=123; r=OrphanLeaseReconciliationRunner(provider=p).run(); assert r["ok"] is False; assert "LIVE_AUTHORITY_RETAINED" in r["failure"]["message"]; assert r["write_attempts"]==0

def test_runner_abstains_on_state_change():
    p=P("STATE_CHANGED_ABSTAINED"); r=OrphanLeaseReconciliationRunner(provider=p).run(); assert r["ok"] is False; assert "STATE_CHANGED_ABSTAINED" in r["failure"]["message"]; assert p.lease_id_present is True
