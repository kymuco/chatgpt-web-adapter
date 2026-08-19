# PR8.8 — Orphaned Browser-Authority Lease Reconciliation After Manual Runtime-Tab Closure, Stale Resource-State Collapse and Zero-Write Clean-Baseline Governance

Live evidence after the retained tab was manually closed between sessions:

```text
runtime_tab_id = null
lease_id_present = true
```

The physical Browser Authority resource was gone, but logical lease metadata remained.

## Rule

Do not globally clear every lease whenever `runtime_tab_id == null`: a fresh turn stores its lease before tab provisioning necessarily completes. Instead use an explicit reconciliation RPC on the existing serialized Native Messaging turn lane.

```text
snapshot tab + lease
→ if live ChatGPT tab: LIVE_AUTHORITY_RETAINED
→ clear exact stale tab id if present
→ re-snapshot
→ if tab reappeared or lease changed: STATE_CHANGED_ABSTAINED
→ compare-and-clear exact initial lease
→ final snapshot
→ require runtime_tab_id=null and lease_id_present=false
```

The lease id is never exported. There is no automatic retry.

Clean statuses are `ALREADY_CLEAN`, `STALE_TAB_METADATA_CLEARED_NO_LEASE`, `ORPHAN_LEASE_CLEARED`, and `STALE_TAB_AND_ORPHAN_LEASE_CLEARED`. `LIVE_AUTHORITY_RETAINED`, `STATE_CHANGED_ABSTAINED`, and `POST_CLEAN_STATE_CHANGED` fail closed.

The worker has no product-write or browser-resource creation/close capability: no input dispatch, submit path, tab create/update/remove, or debugger attach. The CLI always reports product-write budget/attempts/completions as zero.

## Live gate

After extension Reload:

```powershell
python -c "from chatgpt_web_adapter.browser_authority_orphan_lease_reconciliation_pr8_8 import OrphanLeaseReconciliationProvider; import json; p=OrphanLeaseReconciliationProvider(); print(json.dumps(p.orphan_lease_reconciliation_support(), indent=2))"
```

Then:

```powershell
python -m chatgpt_web_adapter.browser_authority_orphan_lease_reconciliation_pr8_8 --timeout 5
```

For the observed orphan state the target is:

```text
ok = true
reconciliation_status = ORPHAN_LEASE_CLEARED
runtime_tab_id = null
lease_id_present = false
product_write_budget = 0
write_attempts = 0
write_completions = 0
```

Only after this clean baseline is proven should the Instant picker experiment be recreated on a fresh Browser Authority generation. The manually closed retained tab itself is no longer recoverable evidence.
