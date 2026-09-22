# PR15.17 — Retire PR8.8 selection forensics

Tracking: #107

## Purpose

PR15.17 removes the historical PR8.8 characterization/instrumentation layers that
surrounded the production Instant selection repair.

The accepted production owner remains:

```text
service_worker_instant_selection_repair_pr8_8.js
```

The retired layers collected route, picker, popup, trigger-timeline, failure, and
reasoning-effort research evidence. They did not grant write/retry/finality authority.

## Selection equivalence

The picker-trigger timeline layer replaced three selection helpers only to add
snapshots and persistence:

```text
_pr88SelectionPoint
_pr88SelectionRawClick
_pr88SelectionWaitForInstantOption
```

Its underlying point lookup and raw click delegated to the original helpers. Its
Instant-option polling retained the same timeout loop, poll interval, found condition,
and failure result as the base implementation.

The failure and popup layers wrapped `locateAndFocusComposer` as:

```text
try production selection
catch:
    persist bounded research evidence
    throw the same error
```

PR15.17 therefore removes those wrappers and restores the already-existing base
selection implementation as the direct production path.

## Deleted browser instrumentation

- retained picker forensics;
- retained route identity forensics;
- Instant failure-record forensics;
- popup-subtree forensics;
- picker-trigger identity/timeline/persistence;
- reasoning-effort topology/governance/geometry characterization.

## Deleted Python research surface

The dedicated Instant-failure, picker-trigger, retained-route/picker, and
reasoning-effort providers, runners, live gates, tests, and product-specific research
documents are removed from the shipping package/repository surface.

Git history remains the evidence archive.

## Preserved production behavior

PR15.17 preserves:

- Instant model requirement and selection decision;
- base picker lookup;
- base raw picker/option click behavior;
- base Instant-option polling interval and timeout;
- selected-Instant proof;
- conversation-write boundary observation;
- Browser Authority;
- prompt insertion and submit;
- no automatic retry;
- canonical finality.

What disappears is only extra research evidence on the failure path.

## Physical deletion

This slice removes 48 historical files from the branch diff. No replacement
telemetry framework is introduced; production falls back to the already-tested base
Instant-selection implementation.

## Acceptance

```text
PR8.8 retained picker/route diagnostic workers       = 0
PR8.8 failure/popup forensic workers                 = 0
PR8.8 picker-trigger instrumentation workers         = 0
PR8.8 reasoning-effort characterization workers      = 0
corresponding Python research modules                = 0
base Instant selection repair                        = preserved
selection helper implementation                      = single active owner
research-only locateAndFocusComposer wrappers        = 0
```
