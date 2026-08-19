# PR8.8 — Fresh Instant Failure Reproduction, Pre-Input Failure Record Persistence, Immediate Route/Picker Forensics and Evidence-Preserving Single-Write Governance

## Why this slice exists

The previous fresh-tab Instant repair proved that a fresh runtime tab for the fixed durable conversation can hydrate as `HIGH` and then fail while trying to discover the `Instant` picker option:

```text
PR8_8_INSTANT_SELECTION_OPTION_NOT_FOUND:instant_option_missing
```

The failure happens inside `locateAndFocusComposer()`, before the transport reaches its clear/input/submit sequence, but the existing selection record was persisted only after a successful `executeNativeTurn()`. The most useful partial state was therefore lost on failure.

This slice preserves that evidence and immediately composes the already-published retained route and picker forensics.

## Scope

The live runner budgets exactly one product-write attempt.

```text
clean baseline
runtime_tab_id = null
lease_id_present = false

→ zero-write fresh-tab mode preflight
→ clean baseline restored
→ one leased Instant write attempt
→ if locate/selection fails:
     persist bounded pre-input failure record
     rethrow the original exception unchanged
     no retry
     retain the runtime tab
     characterize route identity
     if exact expected conversation:
         characterize bounded DOM + Accessibility picker topology
     leave evidence-bearing tab and lease untouched
```

No selector is broadened in this slice.

## Additive worker

`service_worker_instant_failure_forensics_pr8_8.js` is loaded after the existing orphan-reconciliation layer.

It wraps the current global `locateAndFocusComposer()` only to catch an exception while the existing Instant-selection context is still live. It persists bounded failure code/reason enums, initial selected mode evidence, picker candidate count, Instant option candidate count, the existing model-selection network-class counters, and the existing conversation-write-during-selection counter.

The wrapper also records the source-order boundary:

```text
pre_input_failure_boundary_proven = true
prompt_insertion_reached = false
submit_reached = false
```

It does not insert text, submit, navigate, create/close tabs, attach the debugger, read response bodies, export raw DOM/error strings, or retry. The original exception is re-thrown unchanged.

## Failure-record privacy

The read-only failure-record RPC requires the exact expected Browser Authority lease ID for lookup, but the response does not export that token:

```text
lease_id_exported = false
raw_error_exported = false
```

Only bounded enums and existing numeric/boolean observability are returned.

## Generic runtime conservatism remains unchanged

The production runtime may still report:

```text
write_may_have_been_submitted = true
reconciliation_required = true
```

for a delegated browser-owned error.

This forensic slice does not weaken that generic contract. It adds narrower evidence for this exact failure path:

```text
pre_input_failure_boundary_proven = true
prompt_insertion_reached = false
submit_reached = false
conversation_write_count_during_selection = 0
```

No automatic retry is enabled.

## Immediate retained evidence

After a characterized failure, the runner resolves the retained runtime tab and performs the existing route-only forensic RPC.

If the route is the exact target conversation, it then performs the existing zero-write bounded DOM/Accessibility picker topology probe. If the route is not the target conversation, DOM/AX surface forensics are suppressed and the mismatch is preserved.

The retained tab is never closed by this runner.

## Live gate

Start only from the proven clean baseline:

```text
runtime_tab_id = null
lease_id_present = false
```

After extension Reload, run:

```powershell
python -m chatgpt_web_adapter.browser_authority_instant_failure_forensics_pr8_8 `
  --conversation 6a82dabf-65b8-83eb-b8d5-5a86c6ba635d `
  --acknowledge-live-writes `
  --confirm-instant-auto-switch-disabled `
  --timeout 150 `
  --forensics-timeout 20
```

Expected if the prior failure reproduces:

```text
ok = true
write_attempts = 1
write_completions = 0
target_failure_reproduced = true

instant_failure_record.failure_code = OPTION_NOT_FOUND
instant_failure_record.failure_reason = instant_option_missing
instant_failure_record.pre_input_failure_boundary_proven = true
instant_failure_record.prompt_insertion_reached = false
instant_failure_record.submit_reached = false
instant_failure_record.selection.conversation_write_count_during_selection = 0

route_forensics.route_identity.route_identity_status = EXPECTED_CONVERSATION_MATCH
surface_forensics_performed = true
```

The most important output after that is the bounded picker topology:

```text
topology_summary.picker_surface_open
topology_summary.recognized_modes
topology_summary.instant_dom_candidate_count
topology_summary.instant_ax_candidate_count
picker_surface_forensics.dom_topology.dom_candidates
picker_surface_forensics.accessibility_topology.candidates
```

Do not rerun the live writer after a failure. Preserve the retained tab until the topology is reviewed.

If the first write unexpectedly succeeds, the runner reports `write_outcome=SUCCEEDED`, performs no second write, and leaves the runtime tab intact.
