# PR15.51 — Retire detached PR8.7 Temporary characterization source

## Purpose

PR15.15 detached the PR8.7 Temporary characterization chain from production
runtime assembly. PR15.49 later removed its final internal reassignment, and
PR15.50 proved that the entire chain was unreachable from the manifest-rooted
production worker graph.

After those proofs, retaining the old characterization workers inside the
extension package no longer provides runtime value:

```text
unreachable historical source
!= production capability
!= required release asset
```

PR15.51 therefore removes the detached characterization implementation from the
shipping tree. Git history and the PR15 engineering records remain the evidence
archive.

## Physically retired workers

```text
service_worker_temporary_chat.js
service_worker_temporary_snapshot_expression.js
service_worker_temporary_chat_state_semantics.js
service_worker_temporary_chat_ax_semantics.js
service_worker_temporary_chat_semantic_notice.js
service_worker_temporary_chat_turn_probe.js
service_worker_temporary_chat_history_probe.js
service_worker_temporary_chat_manual_ground_truth.js
```

These workers covered the old PR8.7 DOM/ARIA/AX/semantic characterization,
single-write research probe, history settling probe, and manual Temporary
ground-truth workflow. None is part of the current product runtime.

## Retired tests

The characterization-only source-contract suites are removed with the retired
implementation:

```text
tests/test_temporary_characterization_dispatch_pr15_2.py
tests/test_browser_native_temporary_probe_extension.py
tests/test_temporary_snapshot_expression_ownership_pr15_49.py
```

A new retirement regression replaces them and tests the boundary that matters
for the current product:

- none of the retired worker files is packaged;
- no remaining extension worker imports one of those names;
- the manifest still enters the reviewed production runtime;
- PR8.13.2 startup readiness still owns `_cwaTemporaryControlSnapshot`;
- production Temporary startup/product/lifecycle workers remain assembled.

## Stronger closure invariant

`tools/browser_worker_ownership_closure_gate.py` previously failed only if one
of the detached PR8.7 workers became reachable from production.

PR15.51 strengthens that rule:

```text
retired PR8.7 Temporary characterization worker present anywhere in extension tree
→ closure failure
```

This prevents the removed research implementation from silently returning as an
unreachable packaged asset and later becoming an accidental dependency.

## Preserved production semantics

- fresh/continuation Temporary write authority remains PR8.13 request-body proof;
- `history_and_training_disabled === true` remains authoritative;
- `_cwaTemporaryControlSnapshot` remains only a startup-readiness hint;
- Temporary lifecycle routing remains live/session-local;
- no product-write retry is introduced;
- Browser Authority and canonical finality are unchanged;
- `service_worker_temporary_chat_route_reopen_probe.js` remains the manifest
  bootstrap because it belongs to the current reviewed production runtime, not
  the retired PR8.7 characterization chain.

## Acceptance

```text
retired PR8.7 characterization workers in extension tree = 0
retired characterization-only test suites              = 0
imports of retired PR8.7 worker names                   = 0
production Temporary startup/product/lifecycle          = preserved
manifest-rooted ownership closure gate                  = green
```

After this slice, the remaining PR15 direction is the provider-neutral boundary
and minimal DeepSeek proof.

Tracking: #107
